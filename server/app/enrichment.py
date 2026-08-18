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

from .config import settings
from .domain.models import Enrichment
from .http import client as make_client
from .pii import redact

# Cache ONLY successful resolutions — a transient failure must not disable enrichment for the
# life of the process (negative results are retried on the next call).
_PROJECT_IDS: dict[str, str] = {}


def _headers() -> dict:
    return {"x-api-key": settings.langsmith_api_key} if settings.langsmith_api_key else {}


def _project_id(name: str) -> str | None:
    """Resolve a LangSmith project name → id. None if not found / no key. Only truthy results
    are memoised, so one network/auth hiccup does not permanently skip enrichment."""
    if not name or not settings.langsmith_api_key:
        return None
    if name in _PROJECT_IDS:
        return _PROJECT_IDS[name]
    hc = make_client()
    try:
        # Filter server-side by name so accounts with >100 projects still resolve.
        r = hc.get(f"{settings.langsmith_base_url}/sessions", headers=_headers(),
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


def fetch_enrichment(conversation_id: str, region: str) -> Enrichment | None:
    """Fetch + build safe enrichment for one conversation, or None. Never raises."""
    if not settings.enrichment_enabled or not settings.langsmith_api_key or not conversation_id:
        return None
    project_id = _project_id(settings.langsmith_project_for(region))
    if not project_id:
        return None
    # LangSmith filter DSL: match metadata via has(metadata, '{"k": "v"}') — the JSON literal is
    # single-quoted (nested metadata_key("..") quoting is rejected by the parser).
    body = {
        "session": [project_id],
        "filter": "has(metadata, '%s')" % json.dumps({"conversation_id": conversation_id}),
        "is_root": True,  # per-turn top-level state runs (they carry intent/citations/reasoning)
        "limit": settings.enrichment_max_runs,
        "order": "asc",
    }
    hc = make_client()
    try:
        r = hc.post(f"{settings.langsmith_base_url}/runs/query", headers=_headers(), json=body)
        if r.status_code != 200:
            return None
        runs = r.json().get("runs", [])
    except Exception:  # noqa: BLE001 - best-effort; never break analysis
        return None
    finally:
        hc.close()
    return build_enrichment(runs) if runs else None


def _tag_value(tags: list, prefix: str) -> str | None:
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t[len(prefix):]
    return None


def _scrub(value) -> str:
    return redact(value) if isinstance(value, str) and value.strip() else ""


def build_enrichment(runs: list[dict]) -> Enrichment:
    """Aggregate a conversation's runs into one safe Enrichment. Pure — unit-testable."""
    e = Enrichment(langsmith_found=True)
    intents: list[str] = []
    agents: set[str] = set()
    resp_types: list[str] = []
    confidences: list[str] = []
    docs: list[str] = []
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
                docs.append(str(c["file_name"])[:160])  # doc identifier only, never the snippet
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
    e.retrieval_hit = (e.retrieved_count > 0) if used_rag else None
    e.reasoning_summary = " ".join(b for b in reasoning_bits if b)[:600]
    e.frustration_score = max(frustrations) if frustrations else None
    e.had_error = any(errors) if errors else None
    if e.response_type and e.response_type.lower() in ("refusal", "reject", "handoff"):
        e.guardrail = e.response_type
    e.turns = e.turns or len(runs)
    return e
