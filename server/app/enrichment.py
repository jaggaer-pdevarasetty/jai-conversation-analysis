"""Per-conversation enrichment from LangSmith traces (ADR-0018) — READ-ONLY + PII-safe.

Given a conversation_id + region we look up that conversation's LangSmith runs and extract ONLY
safe, structured signals: router intent, retrieval hit/miss + doc names, agent used, response
type, agent confidence, reasoning, frustration score, and errors.

Hard rules:
- We NEVER read `run.extra.metadata` (that is where the JWT token + app_context/URLs live),
  and we never read tokens, keys, or URLs. Only an allow-list of safe keys is touched.
- Every free-text field (reasoning) is PII + quasi-identifier scrubbed before it leaves here.
- Best-effort: any error / missing key / no match returns None and analysis continues unchanged.
"""

from __future__ import annotations

import json
import re

from .config import settings
from .domain.models import Enrichment
from .http import client as make_client
from .pii import redact

# Strip URLs before storing/showing (compliance: no internal/service URLs survive — ADR-0021).
_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# Cache ONLY successful resolutions — a transient failure must not disable enrichment for the
# life of the process (negative results are retried on the next call).
_PROJECT_IDS: dict[str, str] = {}


def _headers(env: str = "uit") -> dict:
    key = settings.langsmith_api_key_for(env)
    return {"x-api-key": key} if key else {}


def _project_id(name: str, env: str = "uit") -> str | None:
    """Resolve a LangSmith project name → id. None if not found / no key. Only truthy results
    are memoised, so one network/auth hiccup does not permanently skip enrichment."""
    if not name or not settings.langsmith_api_key_for(env):
        return None
    if name in _PROJECT_IDS:
        return _PROJECT_IDS[name]
    hc = make_client()
    try:
        # Filter server-side by name so accounts with >100 projects still resolve.
        r = hc.get(f"{settings.langsmith_base_url}/sessions", headers=_headers(env),
                   params={"name": name, "limit": 100})
        if r.status_code != 200:
            return None
        data = r.json()
        items = data if isinstance(data, list) else data.get("sessions", [])
        for p in items:
            if isinstance(p, dict) and p.get("name") == name and p.get("id"):
                _PROJECT_IDS[name] = p["id"]  # memoise success only
                return p["id"]
    except Exception:  # noqa: BLE001 - best-effort
        return None
    finally:
        hc.close()
    return None


def _query_runs(hc, project_id: str, conversation_id: str, env: str, extra: dict) -> list[dict]:
    """POST /runs/query for one conversation with the given extra filters. [] on any failure."""
    body = {
        "session": [project_id],
        # LangSmith filter DSL: match metadata via has(metadata, '{"k": "v"}') — the JSON literal is
        # single-quoted (nested metadata_key("..") quoting is rejected by the parser).
        "filter": "has(metadata, '%s')" % json.dumps({"conversation_id": conversation_id}),
        "limit": settings.enrichment_max_runs,
        **extra,
    }
    try:
        r = hc.post(f"{settings.langsmith_base_url}/runs/query", headers=_headers(env), json=body)
        return r.json().get("runs", []) if r.status_code == 200 else []
    except Exception:  # noqa: BLE001 - best-effort; never break analysis
        return []


def fetch_enrichment(
    conversation_id: str, region: str, env: str = "uit", with_prompt: bool = False
) -> Enrichment | None:
    """Fetch + build safe enrichment for one conversation, or None. Never raises.

    with_prompt (Tier-2 / feedback) additionally pulls the actual invocation prompt from the LLM
    child runs — PII/quasi-id scrubbed + size bounded before it is stored (ADR-0021)."""
    if not settings.enrichment_enabled or not settings.langsmith_api_key_for(env) or not conversation_id:
        return None
    project_id = _project_id(settings.langsmith_project_for(region, env), env)
    if not project_id:
        return None
    hc = make_client()
    try:
        # per-turn top-level state runs (they carry intent/citations/reasoning + snippets)
        runs = _query_runs(hc, project_id, conversation_id, env, {"is_root": True, "order": "asc"})
        if not runs:
            return None
        e = build_enrichment(runs)
        if with_prompt and settings.enrich_prompt:
            llm_runs = _query_runs(hc, project_id, conversation_id, env, {"run_type": "llm", "order": "desc"})
            e.invocation_prompt = build_invocation_prompt(llm_runs)
        return e
    finally:
        hc.close()


def _tag_value(tags: list, prefix: str) -> str | None:
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t[len(prefix):]
    return None


def _scrub(value) -> str:
    """Strip URLs, then PII + quasi-identifiers. The single boundary for free text we store/show."""
    return redact(_URL.sub("[url]", value)) if isinstance(value, str) and value.strip() else ""


def build_enrichment(runs: list[dict]) -> Enrichment:
    """Aggregate a conversation's runs into one safe Enrichment. Pure — unit-testable."""
    e = Enrichment(langsmith_found=True)
    intents: list[str] = []
    agents: set[str] = set()
    resp_types: list[str] = []
    confidences: list[str] = []
    docs: list[str] = []
    snippets: list[str] = []
    reasoning_bits: list[str] = []
    frustrations: list[float] = []
    errors: list[bool] = []
    used_rag = False

    for run in runs:
        # SAFE allow-list only. Deliberately NOT reading run["extra"] (JWT/app_context/URLs).
        out = run.get("outputs") or {}
        ins = run.get("inputs") or {}
        tags = run.get("tags") or []

        intent = out.get("intent") or ins.get("intent") or _tag_value(tags, "intent:")
        if intent:
            intents.append(str(intent))
        if ins.get("secondary_intent") and not e.secondary_intent:
            e.secondary_intent = str(ins["secondary_intent"])
        agent = out.get("agent_used") or _tag_value(tags, "agent:")
        if agent:
            agents.add(str(agent))
            if str(agent).lower() == "rag":
                used_rag = True
        rtype = out.get("response_type") or ins.get("response_type") or _tag_value(tags, "response_type:")
        if rtype:
            resp_types.append(str(rtype))
        conf = out.get("confidence") or ins.get("confidence") or _tag_value(tags, "confidence:")
        if conf:
            confidences.append(str(conf).replace("ConfidenceLevel.", ""))
        for c in (out.get("citations") or ins.get("citations") or []):
            if isinstance(c, dict) and c.get("file_name"):
                docs.append(str(c["file_name"])[:160])  # doc identifier
            # Snippet = retrieved doc TEXT (ADR-0021): PII/quasi-id scrubbed + bounded before storing.
            if settings.enrich_snippets and isinstance(c, dict) and c.get("snippet"):
                snip = _scrub(str(c["snippet"]))[: settings.snippet_max_chars]
                if snip:
                    snippets.append(snip)
        reasoning = ins.get("reasoning") or out.get("reasoning")
        if reasoning:
            reasoning_bits.append(_scrub(str(reasoning)))
        fs = out.get("frustration_score")
        if isinstance(fs, (int, float)):
            frustrations.append(float(fs))
        he = out.get("has_error")
        if he is not None:
            errors.append(bool(he))
        tc = out.get("turn_count")
        if isinstance(tc, int):
            e.turns = max(e.turns or 0, tc)

    e.intent = intents[-1] if intents else None
    e.agent_used = ",".join(sorted(agents)) or None
    e.response_type = resp_types[-1] if resp_types else None
    e.source_confidence = confidences[-1] if confidences else None
    uniq_docs = list(dict.fromkeys(docs))
    e.retrieved_docs = uniq_docs[:10]
    e.retrieved_count = len(uniq_docs)
    e.retrieved_snippets = list(dict.fromkeys(snippets))[:10]  # scrubbed, deduped, bounded
    e.retrieval_hit = (e.retrieved_count > 0) if used_rag else None
    e.reasoning_summary = " ".join(b for b in reasoning_bits if b)[:600]
    e.frustration_score = max(frustrations) if frustrations else None
    e.had_error = any(errors) if errors else None
    if e.response_type and e.response_type.lower() in ("refusal", "reject", "handoff"):
        e.guardrail = e.response_type
    e.turns = e.turns or len(runs)
    return e


def _prompt_text_from_run(run: dict) -> str:
    """Best-effort: assemble the prompt text from an LLM run's inputs (messages / prompts).

    Reads ONLY inputs (never run.extra, where the JWT lives). Handles both plain messages
    ({"role","content"}) and LangChain-serialized ones ({"id":[...,"SystemMessage"],
    "kwargs":{"content": ...}}); content may be a string or a list of parts ({"text": ...})."""
    ins = run.get("inputs") or {}
    chunks: list[str] = []

    def add(content, role: str = ""):
        if isinstance(content, str) and content.strip():
            chunks.append(f"{role}: {content}" if role else content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and isinstance(part.get("text"), str):
                    chunks.append(part["text"])
                elif isinstance(part, str):
                    chunks.append(part)

    def walk(node):
        if isinstance(node, dict):
            kwargs = node.get("kwargs")
            if isinstance(kwargs, dict) and "content" in kwargs:  # LangChain-serialized message
                idp = node.get("id")
                role = str(idp[-1]).replace("Message", "").lower() if isinstance(idp, list) and idp else ""
                add(kwargs.get("content"), role)
            else:
                role = node.get("role") or node.get("type") or ""
                add(node.get("content"), role if isinstance(role, str) else "")
        elif isinstance(node, list):
            for x in node:
                walk(x)
        elif isinstance(node, str):
            chunks.append(node)

    walk(ins.get("messages"))
    for p in ins.get("prompts") or []:
        if isinstance(p, str):
            chunks.append(p)
    return "\n".join(c for c in chunks if c)


def build_invocation_prompt(llm_runs: list[dict]) -> str:
    """Pick the richest LLM prompt across runs, then scrub (URLs + PII) + size-bound. Pure."""
    best = ""
    for run in llm_runs:
        text = _prompt_text_from_run(run)
        if len(text) > len(best):
            best = text
    return _scrub(best)[: settings.prompt_max_chars]
