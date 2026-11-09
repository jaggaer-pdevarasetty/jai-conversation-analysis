"""LangSmith enrichment: extract only SAFE fields; never leak JWT/URLs/PII (ADR-0018/0021)."""

from app import enrichment
from app.enrichment import build_enrichment, build_invocation_prompt, fetch_enrichment

# A realistic LangSmith run that INCLUDES the dangerous stuff we must never surface.
JWT = "eyJhbGciOiJSUzI1NiJ9.eyJ0ZW5hbnRfaWQiOiIyMDAyMDAwMDgwOCJ9.sig"
DIRTY_RUN = {
    "run_type": "chain",
    "name": "knowledge_search | 20020000808",
    "tags": ["intent:knowledge_search", "agent:rag", "confidence:ConfidenceLevel.HIGH", "response_type:answer"],
    "inputs": {
        "intent": "knowledge_search",
        "secondary_intent": None,
        "reasoning": "User john.doe@buffalo.edu at Crofts Hall asked about req 12345678 for $3,703.85.",
        "app_context": {"api_domains": {"JI": "https://ji-us-uit-api-internal.example/secret"}},
        "user_query": "how do I approve",
    },
    "outputs": {
        "agent_used": "rag",
        "response_type": "answer",
        "confidence": "HIGH",
        "has_error": False,
        "frustration_score": 0.1,
        "turn_count": 3,
        "citations": [
            {"citation_number": 1, "file_name": "administrative-services_shopblue_assign-approver.html",
             "snippet": "contact jane.roe@buffalo.edu"},
        ],
    },
    "extra": {"metadata": {"_user_jwt_token": JWT, "tenant_id": "20020000808", "user_id": "9464669"}},
}


def _flat(e) -> str:
    from dataclasses import asdict
    return str(asdict(e))


def test_extracts_safe_signals():
    e = build_enrichment([DIRTY_RUN])
    assert e.intent == "knowledge_search"
    assert e.agent_used == "rag"
    assert e.response_type == "answer"
    assert e.source_confidence == "HIGH"
    assert e.retrieval_hit is True and e.retrieved_count == 1
    assert e.retrieved_docs and "assign-approver" in e.retrieved_docs[0]
    assert e.had_error is False
    assert e.langsmith_found is True
    # ADR-0021: snippet captured, but scrubbed (the email in it is gone).
    assert e.retrieved_snippets and "[email]" in e.retrieved_snippets[0]


def test_no_secret_or_pii_survives():
    e = build_enrichment([DIRTY_RUN])
    blob = _flat(e)
    # secrets / internal urls must never appear
    assert JWT not in blob and "_user_jwt_token" not in blob
    assert "api-internal" not in blob and "https://" not in blob
    # personal data in the reasoning must be scrubbed
    for leak in ("john.doe@buffalo.edu", "jane.roe@buffalo.edu", "12345678", "3,703.85"):
        assert leak not in blob, f"{leak!r} leaked into enrichment"
    # the reasoning is still present, just scrubbed
    assert "[email]" in e.reasoning_summary or "[id]" in e.reasoning_summary or "[amount]" in e.reasoning_summary


def test_snippets_are_tier2_only():
    # Tier-1 (with_snippets=False): keep doc NAMES (low-risk) but store NO snippet text,
    # so the PII surface is not widened to every conversation (ADR-0021 review fix).
    e1 = build_enrichment([DIRTY_RUN], with_snippets=False)
    assert e1.retrieved_docs and e1.retrieved_snippets == []
    # Tier-2 (default): snippets captured (and scrubbed).
    e2 = build_enrichment([DIRTY_RUN])
    assert e2.retrieved_snippets


def test_invocation_prompt_scrubbed_and_bounded():
    # The actual LLM prompt (ADR-0021) may carry URLs + PII + the retrieved context. It must be
    # URL/PII scrubbed before we store it, and never expose secrets.
    dirty_llm_run = {
        "run_type": "llm",
        "inputs": {
            "messages": [[
                {"role": "system", "content": "Answer only from context. See https://internal.example/x"},
                {"role": "user", "content": "email me at john.doe@ucsc.edu about req 12345678"},
            ]],
        },
    }
    prompt = build_invocation_prompt([dirty_llm_run])
    assert prompt, "prompt should be extracted"
    assert "https://" not in prompt and "internal.example" not in prompt
    assert "[url]" in prompt
    assert "john.doe@ucsc.edu" not in prompt and "12345678" not in prompt
    # the useful instruction text survives
    assert "Answer only from context" in prompt
    # empty / no-llm-runs is safe
    assert build_invocation_prompt([]) == ""


def test_invocation_prompt_handles_langchain_serialized_messages():
    # Real LangSmith LLM runs serialize messages as {"id":[...,"SystemMessage"],"kwargs":{"content":...}}.
    lc_run = {
        "run_type": "llm",
        "inputs": {"messages": [[
            {"id": ["langchain", "schema", "messages", "SystemMessage"],
             "kwargs": {"content": "Use only the provided context to answer."}, "lc": 1, "type": "constructor"},
            {"id": ["langchain", "schema", "messages", "HumanMessage"],
             "kwargs": {"content": "what form for a service?"}, "lc": 1, "type": "constructor"},
        ]]},
    }
    prompt = build_invocation_prompt([lc_run])
    assert "Use only the provided context" in prompt
    assert "what form for a service?" in prompt


def test_maps_rag_agent_field_aliases():
    state_run = {
        "name": "rag_agent",
        "tags": ["app:JI"],
        "inputs": {"intent": "knowledge_search", "reasoning": "The user needs contract instructions.", "turn_count": 2},
        "outputs": {
            "agent_name": "rag",
            "agent_confidence": "HIGH",
            "citations": [{"file_name": "Contracts Guide.pdf", "snippet": "Create a contract entry."}],
        },
    }

    e = build_enrichment([state_run])

    assert e.agent_used == "rag"
    assert e.platform == "JI"
    assert e.interaction_mode == "Ask"
    assert e.source_confidence == "HIGH"
    assert e.reasoning_summary == "The user needs contract instructions."
    assert e.turns == 2
    assert e.retrieval_hit is True
    assert e.retrieved_docs == ["Contracts Guide.pdf"]


def test_fetch_combines_root_and_rag_agent_runs(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        enrichment_enabled=True,
        langsmith_api_key_for=lambda env="uit": "k",
        langsmith_base_url="https://x",
        enrichment_max_runs=20,
        langsmith_project_for=lambda region, env="uit": "uit_us",
        enrich_snippets=True,
        snippet_max_chars=400,
    )
    root = {"trace_id": "trace-1", "outputs": {"intent": "knowledge_search", "agent_used": "rag"}}
    child = {"inputs": {"reasoning": "The child run explains the routing decision."}}

    class Client:
        def close(self):
            pass

    monkeypatch.setattr(enrichment, "settings", fake)
    monkeypatch.setattr(enrichment, "_project_id", lambda name, env="uit": "project-1" if name == "uit_us" else None)
    monkeypatch.setattr(enrichment, "make_client", Client)
    monkeypatch.setattr(enrichment, "_query_runs", lambda *args: [root])
    monkeypatch.setattr(enrichment, "_query_agent_by_traces", lambda *args: [child], raising=False)

    e = fetch_enrichment("conversation-1", "us")

    assert e is not None
    assert e.reasoning_summary == "The child run explains the routing decision."


def test_maps_deep_research_chat_turn():
    run = {
        "name": "chat_turn",
        "tags": ["app:JD"],
        "inputs": {"question": "Show the latest activity."},
        "outputs": {
            "answer": "Here is the latest activity.",
            "thinking": "I should query the permitted analytics source and summarize the result.",
            "stages": ["planning", "query", "answer"],
        },
    }

    e = build_enrichment([run])

    assert e.agent_used == "deep-research"
    assert e.platform == "JD"
    assert e.interaction_mode == "Deep Research"
    assert e.response_type == "answer"
    assert e.reasoning_summary == "I should query the permitted analytics source and summarize the result."
    assert e.retrieval_hit is None
    assert e.retrieved_docs == []
    assert e.turns == 1


def test_fetch_combines_regional_and_deep_research_projects(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        enrichment_enabled=True,
        langsmith_api_key_for=lambda env="uit": "k",
        langsmith_base_url="https://x",
        enrichment_max_runs=20,
        langsmith_project_for=lambda region, env="uit": "uit_us",
        enrich_snippets=True,
        snippet_max_chars=400,
    )
    projects = {"uit_us": "regional", "deep-research": "deep"}
    roots = {
        "regional": [{"trace_id": "regional-trace", "outputs": {"agent_used": "rag", "citations": [{"file_name": "Regional.pdf"}]}}],
        "deep": [{"trace_id": "deep-trace", "outputs": {"agent_used": "rag", "citations": [{"file_name": "Deep.pdf"}]}}],
    }

    class Client:
        def close(self):
            pass

    monkeypatch.setattr(enrichment, "settings", fake)
    monkeypatch.setattr(enrichment, "_project_id", lambda name, env="uit": projects.get(name))
    monkeypatch.setattr(enrichment, "make_client", Client)
    monkeypatch.setattr(enrichment, "_query_runs", lambda _hc, project_id, *_args: roots[project_id])
    monkeypatch.setattr(
        enrichment,
        "_query_agent_by_traces",
        lambda _hc, _project_id, trace_ids, _env: [{"inputs": {"reasoning": trace_ids[0]}}],
    )

    e = fetch_enrichment("conversation-1", "us")

    assert e is not None
    assert e.retrieved_docs == ["Regional.pdf", "Deep.pdf"]
    assert "regional-trace" in e.reasoning_summary
    assert "deep-trace" in e.reasoning_summary


def test_fetch_disabled_returns_none():
    # No LangSmith key configured in tests → enrichment is off → None, never a network call.
    assert fetch_enrichment("some-id", "us") is None


def test_project_id_cache_is_isolated_by_environment(monkeypatch):
    from types import SimpleNamespace

    calls = []

    class Response:
        status_code = 200

        def __init__(self, project_id):
            self.project_id = project_id

        def json(self):
            return [{"name": "deep-research", "id": self.project_id}]

    class Client:
        def get(self, _url, headers, params):
            calls.append((headers["x-api-key"], params["name"]))
            return Response(f'{headers["x-api-key"]}-project')

        def close(self):
            pass

    fake = SimpleNamespace(
        langsmith_base_url="https://x",
        langsmith_api_key_for=lambda env="uit": f"key-{env}",
    )
    monkeypatch.setattr(enrichment, "settings", fake)
    monkeypatch.setattr(enrichment, "make_client", Client)
    enrichment._PROJECT_IDS.clear()

    assert enrichment._project_id("deep-research", "uit") == "key-uit-project"
    assert enrichment._project_id("deep-research", "prod") == "key-prod-project"
    assert calls == [("key-uit", "deep-research"), ("key-prod", "deep-research")]


def test_fetch_never_raises_on_bad_project(monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(
        enrichment_enabled=True, langsmith_api_key="k",
        langsmith_api_key_for=lambda env="uit": "k",
        langsmith_base_url="https://x", enrichment_max_runs=5,
        langsmith_project_for=lambda region, env="uit": "uit_us",
    )
    monkeypatch.setattr(enrichment, "settings", fake)
    monkeypatch.setattr(enrichment, "_project_id", lambda name, env="uit": None)  # project not found
    assert fetch_enrichment("id", "us") is None
