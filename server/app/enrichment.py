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
from .sources import _post_with_retry

# Strip URLs before storing/showing (compliance: no internal/service URLs survive — ADR-0021).
_URL = re.compile(r"https?://\S+", re.IGNORECASE)

# Cache ONLY successful resolutions — a transient failure must not disable enrichment for the
# life of the process (negative results are retried on the next call).
_PROJECT_IDS: dict[tuple[str, str], str] = {}


def _api_key(env: str = "uit", region: str | None = None) -> str:
    try:
        return settings.langsmith_api_key_for(env, region)
    except TypeError:
        return settings.langsmith_api_key_for(env)


def _workspace_id(region: str | None = None, env: str = "uit") -> str:
    fn = getattr(settings, "langsmith_workspace_id_for", None)
    return fn(region, env) if callable(fn) else ""


_ORG_ID = ""


def _langsmith_org_id() -> str:
    """Cached LangSmith organization id (from /workspaces) — used to build trace UI links."""
    global _ORG_ID
    if _ORG_ID:
        return _ORG_ID
    try:
        hc = make_client()
        try:
            r = hc.get(f"{settings.langsmith_base_url}/workspaces", headers=_headers("uit"))
            if r.status_code == 200:
                for w in r.json():
                    if isinstance(w, dict) and w.get("organization_id"):
                        _ORG_ID = str(w["organization_id"])
                        break
        finally:
            hc.close()
    except Exception:  # noqa: BLE001 - best-effort; link building just skips
        pass
    return _ORG_ID


def _headers(env: str = "uit", region: str | None = None, include_workspace: bool = False) -> dict:
    key = _api_key(env, region)
    if not key:
        return {}
    headers = {"x-api-key": key}
    # Service keys (lsv2_sk_...) are already bound to a single workspace (UIT, PROD_US, or PROD_EU_UK);
    # only send X-Tenant-Id for org-wide PATs (lsv2_pt_...) or when explicitly requested.
    use_ws = include_workspace or key.startswith("lsv2_pt_")
    workspace_id = _workspace_id(region, env) if use_ws else ""
    if workspace_id:
        headers["X-Tenant-Id"] = workspace_id
    return headers


def _project_id(name: str, env: str = "uit", region: str | None = None) -> str | None:
    """Resolve a LangSmith project name → id. None if not found / no key. Only truthy results
    are memoised, so one network/auth hiccup does not permanently skip enrichment."""
    if not name or not _api_key(env, region):
        return None
    ws_group = "eu_uk" if (region or "").lower() in {"eu", "uk"} and env == "prod" else (region or "").lower()
    cache_key = (f"{env}:{ws_group}" if ws_group else env, name)
    if cache_key in _PROJECT_IDS:
        return _PROJECT_IDS[cache_key]
    hc = make_client()
    try:
        for include_ws in (False, True):
            headers = _headers(env, region, include_workspace=include_ws)
            r = hc.get(
                f"{settings.langsmith_base_url}/sessions",
                headers=headers,
                params={"name": name, "limit": 100},
            )
            if r.status_code != 200:
                continue
            data = r.json()
            items = data if isinstance(data, list) else data.get("sessions", [])
            for p in items:
                if isinstance(p, dict) and p.get("name") == name and p.get("id"):
                    _PROJECT_IDS[cache_key] = p["id"]
                    return p["id"]
    except Exception:  # noqa: BLE001 - best-effort
        return None
    finally:
        hc.close()
    return None


def _query_runs(hc, project_id: str, conversation_id: str, env: str, extra: dict, region: str | None = None) -> list[dict]:
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
        r = _post_with_retry(hc, f"{settings.langsmith_base_url}/runs/query", _headers(env, region), body)
        return r.json().get("runs", [])
    except Exception:  # noqa: BLE001 - best-effort; never break analysis
        return []


def _infer_platform(
    tenant_id: str | None = None,
    tenant_name: str | None = None,
    user_app: str | None = None,
    tenant_app: str | None = None,
    region: str | None = None,
    text_hint: str = "",
) -> str:
    for candidate in (user_app, tenant_app):
        if candidate and str(candidate).strip():
            return str(candidate).strip().upper()[:32]
    try:
        from .ea_customers import ea_info

        ea = ea_info(tenant_name, tenant_id)
        if isinstance(ea, dict) and ea.get("product"):
            return str(ea["product"]).strip().upper()[:32]
    except Exception:  # noqa: BLE001
        pass
    tid = str(tenant_id or "").strip()
    if tid.startswith(("10020", "20020")):
        return "JI"
    if tid.startswith(("10010", "10040", "20010", "20040")):
        return "JA"
    if tid.startswith(("10030", "20030")):
        return "JD"
    lowered = text_hint.lower()
    if any(k in lowered for k in ("shopblue", "sciquest", "punch-out", "punchout", "spartanmart")):
        return "JI"
    if any(k in lowered for k in ("bravosolution", "esop", "tender", "pqq", "itt", "rfq")):
        return "JA"
    if (region or "").lower() == "us":
        return "JI"
    if (region or "").lower() in {"eu", "uk"}:
        return "JA"
    return "JA"


def _compute_chatdb_frustration(rows: list[dict]) -> list[float]:
    """Mirror orchestrator _compute_frustration across assistant turns when trace score is absent."""
    frustration = 0
    scores: list[float] = []
    for index, row in enumerate(rows):
        content = str(row.get("content") or "").strip()
        lowered = content.lower()
        is_empty = not content
        is_escalation = (
            "i notice you've been asking about this topic" in lowered
            or "sorry the previous answer didn't resolve your issue" in lowered
        )
        is_refusal_or_clarify = (
            "only help with procurement-related questions" in lowered
            or "only help with jaggaer login and access issues" in lowered
            or "ecco cosa posso fare per te" in lowered
            or "couldn't find an answer in the available documents" in lowered
            or "couldn't find relevant information" in lowered
        )
        if index == 0:
            frustration = 1 if is_empty else 0
        elif is_escalation:
            frustration = max(frustration + 1, 2)
        elif is_empty or is_refusal_or_clarify:
            frustration = min(6, frustration + 1)
        else:
            frustration = min(6, frustration + 1)
        scores.append(float(frustration))
    return scores


def _chatdb_runs_from_metadata(
    rows: list[dict],
    platform: str | None = None,
    region: str | None = None,
) -> list[dict]:
    """Convert chat-DB assistant message rows into synthetic run dicts for build_enrichment."""
    runs: list[dict] = []
    turn = 0
    first_row = rows[0] if rows else {}
    resolved_platform = platform or _infer_platform(
        tenant_id=first_row.get("tenant_id"),
        tenant_name=first_row.get("tenant_name"),
        user_app=first_row.get("user_app"),
        tenant_app=first_row.get("tenant_app"),
        region=region,
        text_hint=" ".join(str(r.get("content") or "") for r in rows),
    )
    frustration_scores = _compute_chatdb_frustration(rows)
    for idx, row in enumerate(rows):
        meta = row.get("metadata") if isinstance(row.get("metadata"), dict) else {}
        content = str(row.get("content") or "").strip()
        lowered = content.lower()
        status = str(row.get("status") or "").lower()
        user_id = str(row.get("user_id") or "").strip()
        turn += 1
        citations = meta.get("citations") if isinstance(meta.get("citations"), list) else []
        reasoning = meta.get("reasoning") if isinstance(meta.get("reasoning"), str) else ""
        is_deep = bool(reasoning and "**" in reasoning and not citations) or ("```dr-table" in lowered or "```vega-lite" in lowered)
        is_live_chat = bool(
            meta.get("live_chat_conversation_id")
            or meta.get("handoff")
            or "connect you with a live agent" in lowered
            or "live agent" in lowered
        )
        is_ticket = bool(meta.get("ticket_response") or meta.get("ticket_form_data") or "ticket status" in lowered)
        is_prelogin = user_id == "1" or "only help with jaggaer login and access issues" in lowered
        is_reject = (
            "only help with procurement-related questions" in lowered
            or "only help with jaggaer login and access issues" in lowered
        )
        is_empty = not content
        is_no_docs = (
            "couldn't find an answer in the available documents" in lowered
            or "couldn't find relevant information" in lowered
            or "no results found" in lowered
        )
        agent = (
            "deep-research"
            if is_deep
            else "live_chat"
            if is_live_chat
            else "ticket"
            if is_ticket
            else "prelogin"
            if is_prelogin
            else "rag"
            if citations or "renumber_map" in meta or is_no_docs
            else "router"
        )
        intent = (
            "live_chat"
            if is_live_chat
            else "ticket"
            if is_ticket
            else "reject"
            if is_reject
            else "knowledge_search"
            if agent in {"rag", "prelogin"}
            else "data_analysis"
            if is_deep
            else "general"
        )
        fallback_reasoning = (
            reasoning
            or (
                "Assistant turn produced an empty response before completion."
                if is_empty
                else "Request fell outside scope and was declined by the router guardrail."
                if is_reject
                else "Escalated or offered handoff to a live support agent."
                if is_live_chat
                else "Knowledge search returned no matching documents."
                if is_no_docs
                else f"Answered via {agent} ({len(citations)} retrieved document(s))."
                if citations
                else f"Handled by {agent}."
            )
        )
        runs.append(
            {
                "name": "chat_turn" if is_deep else "prelogin_chat" if is_prelogin else "chatdb_message",
                "is_root": True,
                "status": "error" if is_empty or status in {"failed", "error"} else "success",
                "outputs": {
                    "intent": intent,
                    "agent_used": agent,
                    "platform": resolved_platform,
                    "response_type": "handoff" if is_live_chat else "reject" if is_reject else "answer",
                    "citations": citations,
                    "thinking": fallback_reasoning if is_deep else None,
                    "reasoning": fallback_reasoning if not is_deep else None,
                    "frustration_score": frustration_scores[idx],
                    "turn_count": turn,
                    "had_error": bool(meta.get("stopped")) or is_empty or status in {"failed", "error"},
                },
            }
        )
    return runs


def fetch_chatdb_enrichment(
    conversation_id: str, region: str, env: str = "uit", with_snippets: bool = False
) -> Enrichment | None:
    """Fallback enrichment from chat-DB assistant messages when LangSmith trace is absent."""
    if not region or not conversation_id:
        return None
    try:
        from sqlalchemy import text

        from . import dashboard

        with dashboard._connect(region, env) as (c, sch):
            if dashboard._platform_layout(c, sch):
                return None
            rows = (
                c.execute(
                    text(
                        f'select conv.tenant_id::text as tenant_id, conv.user_id::text as user_id, '
                        f't.name as tenant_name, coalesce(u.app_id, u.issuing_application) as user_app, '
                        f'(select coalesce(u2.app_id, u2.issuing_application) from "{sch}".users u2 '
                        f' where u2.tenant_id = conv.tenant_id and coalesce(u2.app_id, u2.issuing_application) is not null limit 1) as tenant_app, '
                        f'm.content, m.status, m.metadata '
                        f'from "{sch}".conversations conv '
                        f'join "{sch}".messages m on m.conversation_id = conv.id '
                        f'left join "{sch}".tenants t on t.tenant_id = conv.tenant_id '
                        f'left join "{sch}".users u on u.user_id = conv.user_id and u.tenant_id = conv.tenant_id '
                        f'where conv.id::text = :cid and m.role = \'assistant\' '
                        f'order by m.sequence_num'
                    ),
                    {"cid": conversation_id},
                )
                .mappings()
                .all()
            )
        if not rows:
            return None
        row_dicts = [dict(r) for r in rows]
        platform = _infer_platform(
            tenant_id=row_dicts[0].get("tenant_id"),
            tenant_name=row_dicts[0].get("tenant_name"),
            user_app=row_dicts[0].get("user_app"),
            tenant_app=row_dicts[0].get("tenant_app"),
            region=region,
            text_hint=" ".join(str(r.get("content") or "") for r in row_dicts),
        )
        runs = _chatdb_runs_from_metadata(row_dicts, platform=platform, region=region)
        return build_enrichment(runs, with_snippets=with_snippets) if runs else None
    except Exception:  # noqa: BLE001
        return None


def fetch_enrichment(
    conversation_id: str, region: str, env: str = "uit", with_prompt: bool = False
) -> Enrichment | None:
    """Fetch + build safe enrichment for one conversation, or None. Never raises.

    with_prompt (Tier-2 / feedback) additionally pulls the actual invocation prompt from the LLM
    child runs — PII/quasi-id scrubbed + size bounded before it is stored (ADR-0021)."""
    if not settings.enrichment_enabled or not conversation_id:
        return None
    if not _api_key(env, region):
        return fetch_chatdb_enrichment(conversation_id, region, env, with_snippets=with_prompt)
    extra_projects = ("deep-research", "prelogin_prod") if env == "prod" else ("deep-research", "prelogin_uit")
    project_names = dict.fromkeys((settings.langsmith_project_for(region, env), *extra_projects))
    def _resolve(name: str) -> str | None:
        try:
            return _project_id(name, env, region)
        except TypeError:
            return _project_id(name, env)

    projects = [project_id for name in project_names if (project_id := _resolve(name))]
    if not projects:
        return fetch_chatdb_enrichment(conversation_id, region, env, with_snippets=with_prompt)
    hc = make_client()
    try:
        runs: list[dict] = []
        prompts: list[dict] = []
        first_trace_id = ""
        first_trace_project = ""
        for project_id in projects:
            try:
                roots = _query_runs(hc, project_id, conversation_id, env, {"is_root": True, "order": "asc"}, region)
            except TypeError:
                roots = _query_runs(hc, project_id, conversation_id, env, {"is_root": True, "order": "asc"})
            trace_ids = [t for r in roots if (t := r.get("trace_id"))]
            if trace_ids and not first_trace_id:
                first_trace_id = trace_ids[0]
                first_trace_project = project_id
            runs.extend(roots)
            try:
                runs.extend(_query_agent_by_traces(hc, project_id, trace_ids, env, region))
            except TypeError:
                runs.extend(_query_agent_by_traces(hc, project_id, trace_ids, env))
            if with_prompt and settings.enrich_prompt:
                try:
                    prompts.extend(_query_llm_by_traces(hc, project_id, trace_ids, env, region))
                except TypeError:
                    prompts.extend(_query_llm_by_traces(hc, project_id, trace_ids, env))
        if not runs:
            return fetch_chatdb_enrichment(conversation_id, region, env, with_snippets=with_prompt)
        e = build_enrichment(runs, with_snippets=with_prompt)
        if first_trace_id:
            e.trace_id = first_trace_id
            org = _langsmith_org_id()
            if org and first_trace_project:
                e.trace_url = f"https://smith.langchain.com/o/{org}/projects/p/{first_trace_project}?peek={first_trace_id}"
        if not e.platform or e.frustration_score is None:
            fallback = fetch_chatdb_enrichment(conversation_id, region, env, with_snippets=False)
            if fallback:
                e.platform = e.platform or fallback.platform
                if e.frustration_score is None:
                    e.frustration_score = fallback.frustration_score
            e.platform = e.platform or _infer_platform(region=region)
            if e.frustration_score is None:
                e.frustration_score = 0.0
        if prompts:
            e.invocation_prompt = build_invocation_prompt(prompts)
        return e
    finally:
        hc.close()


def _query_agent_by_traces(hc, project_id: str, trace_ids: list[str], env: str, region: str | None = None) -> list[dict]:
    tids = [t for t in trace_ids if t][: settings.enrichment_max_runs]
    if not tids:
        return []
    clauses = ", ".join('eq(trace_id, "%s")' % t for t in tids)
    traces = "or(%s)" % clauses if len(tids) > 1 else clauses
    body = {
        "session": [project_id],
        "filter": f'and({traces}, eq(name, "rag_agent"))',
        "run_type": "chain",
        "limit": settings.enrichment_max_runs,
        "order": "asc",
    }
    try:
        r = _post_with_retry(hc, f"{settings.langsmith_base_url}/runs/query", _headers(env, region), body)
        return r.json().get("runs", [])
    except Exception:
        return []


def _query_llm_by_traces(hc, project_id: str, trace_ids: list[str], env: str, region: str | None = None) -> list[dict]:
    """LLM child runs across the given traces. Uses trace_id (always present on children) so the
    prompt fetch is robust even if conversation_id metadata is stamped only on root runs. [] on failure."""
    tids = [t for t in trace_ids if t][: settings.enrichment_max_runs]
    if not tids:
        return []
    clauses = ", ".join('eq(trace_id, "%s")' % t for t in tids)
    filt = "or(%s)" % clauses if len(tids) > 1 else clauses
    body = {
        "session": [project_id], "filter": filt, "run_type": "llm",
        "limit": settings.enrichment_max_runs, "order": "desc",
    }
    try:
        r = _post_with_retry(hc, f"{settings.langsmith_base_url}/runs/query", _headers(env, region), body)
        return r.json().get("runs", [])
    except Exception:  # noqa: BLE001 - best-effort; never break analysis
        return []


def _tag_value(tags: list, prefix: str) -> str | None:
    for t in tags:
        if isinstance(t, str) and t.startswith(prefix):
            return t[len(prefix):]
    return None


def _scrub(value) -> str:
    """Strip URLs, then PII + quasi-identifiers. The single boundary for free text we store/show."""
    return redact(_URL.sub("[url]", value)) if isinstance(value, str) and value.strip() else ""


def build_enrichment(runs: list[dict], with_snippets: bool = True) -> Enrichment:
    """Aggregate a conversation's runs into one safe Enrichment. Pure — unit-testable.

    with_snippets gates retrieved-document snippets to Tier-2 (feedback) conversations (ADR-0021),
    so the stored PII surface is not widened to every conversation. Doc file NAMES are always kept
    (low-risk identifiers)."""
    e = Enrichment(langsmith_found=True)
    intents: list[str] = []
    agents: set[str] = set()
    platforms: list[str] = []
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
        meta = run.get("metadata") if isinstance(run.get("metadata"), dict) else {}
        resp_meta = out.get("response_metadata") if isinstance(out.get("response_metadata"), dict) else {}
        req_meta = out.get("request") if isinstance(out.get("request"), dict) else {}
        deep_research = run.get("name") == "chat_turn"
        prelogin = run.get("name") == "prelogin_chat"

        intent = (
            out.get("intent")
            or ins.get("intent")
            or resp_meta.get("intent")
            or resp_meta.get("router_decision")
            or (resp_meta.get("routing_status") or {}).get("mapped_intent")
            or _tag_value(tags, "intent:")
        )
        if intent:
            intents.append(str(intent))
        if ins.get("secondary_intent") and not e.secondary_intent:
            e.secondary_intent = str(ins["secondary_intent"])
        agent = (
            out.get("agent_used")
            or out.get("agent_name")
            or ins.get("agent_used")
            or ins.get("agent_name")
            or resp_meta.get("node_executed")
            or _tag_value(tags, "agent:")
            or ("deep-research" if deep_research else None)
            or ("prelogin" if prelogin else None)
        )
        if agent:
            agents.add(str(agent))
            if str(agent).lower() == "rag":
                used_rag = True
        platform = (
            out.get("platform")
            or out.get("core_app")
            or ins.get("platform")
            or ins.get("core_app")
            or req_meta.get("app_id")
            or meta.get("core_app")
            or _tag_value(tags, "app:")
        )
        if platform:
            platforms.append(str(platform).upper()[:32])
        rtype = (
            out.get("response_type")
            or ins.get("response_type")
            or _tag_value(tags, "response_type:")
            or ("answer" if (deep_research and out.get("answer")) or (prelogin and out.get("response")) else None)
        )
        if rtype:
            resp_types.append(str(rtype))
        conf = (
            out.get("confidence")
            or out.get("agent_confidence")
            or ins.get("confidence")
            or ins.get("agent_confidence")
            or (resp_meta.get("routing_status") or {}).get("routing_level")
            or _tag_value(tags, "confidence:")
        )
        if conf:
            confidences.append(str(conf).replace("ConfidenceLevel.", ""))
        for c in (out.get("citations") or ins.get("citations") or []):
            if isinstance(c, dict) and c.get("file_name"):
                docs.append(str(c["file_name"])[:160])  # doc identifier
            # Snippet = retrieved doc TEXT (ADR-0021): Tier-2 only, PII/quasi-id scrubbed + bounded.
            if with_snippets and settings.enrich_snippets and isinstance(c, dict) and c.get("snippet"):
                snip = _scrub(str(c["snippet"]))[: settings.snippet_max_chars]
                if snip:
                    snippets.append(snip)
        reasoning = ins.get("reasoning") or out.get("reasoning") or out.get("thinking") or resp_meta.get("llm_reasoning")
        if reasoning:
            reasoning_bits.append(_scrub(str(reasoning)))
        if run.get("error"):
            reasoning_bits.append(_scrub(f"Run error: {run.get('error')}"))
        fs = out.get("frustration_score")
        if isinstance(fs, (int, float)):
            frustrations.append(float(fs))
        he = out.get("has_error")
        if he is not None:
            errors.append(bool(he))
        elif run.get("status") == "error" or bool(run.get("error")):
            errors.append(True)
        tc = out.get("turn_count") or ins.get("turn_count")
        if isinstance(tc, int):
            e.turns = max(e.turns or 0, tc)
        elif run.get("is_root") and (deep_research or prelogin):
            e.turns = (e.turns or 0) + 1

    e.intent = intents[-1] if intents else None
    e.agent_used = ",".join(sorted(agents)) or None
    e.platform = platforms[-1] if platforms else None
    agent_names = {agent.lower() for agent in agents}
    if "deep-research" in agent_names:
        e.interaction_mode = "Deep Research"
    elif agent_names & {"live_agent", "live_chat"}:
        e.interaction_mode = "Live Chat"
    elif agents or intents:
        e.interaction_mode = "Ask"
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
