"""LangSmith-as-source — boundary mocked (httpx MockTransport), no live calls."""

import httpx

from app import sources


def _handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/api/v1/sessions":
        return httpx.Response(200, json=[{"id": "sess-1", "name": "jai-orchestrator"}])
    if request.url.path == "/api/v1/runs/query":
        return httpx.Response(
            200,
            json={
                "runs": [
                    {
                        "id": "r1", "name": "gemini-2.5-flash",
                        "start_time": "2026-01-01T00:00:00Z",
                        "first_token_time": "2026-01-01T00:00:00.300Z",
                        "end_time": "2026-01-01T00:00:01Z",
                        "inputs": {"messages": [{"content": "where is my order"}]},
                        "outputs": {"content": "Please share the order id."},
                        "prompt_tokens": 10, "completion_tokens": 5,
                        "extra": {"metadata": {"conversation_id": "c-1", "tenant_id": "20256789"}},
                    },
                    {
                        "id": "r2", "name": "gemini-2.5-flash",
                        "start_time": "2026-01-01T00:01:00Z",
                        "end_time": "2026-01-01T00:01:01Z",
                        "inputs": {"messages": [{"content": "still waiting"}]},
                        "outputs": {"content": "It shipped today."},
                        "prompt_tokens": 8, "completion_tokens": 4,
                        "extra": {"metadata": {"conversation_id": "c-1", "tenant_id": "20256789"}},
                    },
                ]
            },
        )
    return httpx.Response(404)


def _client() -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(_handler))


def test_langsmith_runs_group_into_one_conversation():
    convs = sources.load_from_langsmith(http_client=_client())
    assert len(convs) == 1
    conv = convs[0]
    assert conv.id == "c-1"
    # 2 runs → 2 user + 2 assistant messages, in order
    assert [m.role for m in conv.messages] == ["user", "assistant", "user", "assistant"]
    assert conv.messages[0].content == "where is my order"


def test_langsmith_maps_authoritative_metrics():
    conv = sources.load_from_langsmith(http_client=_client())[0]
    first_assistant = next(m for m in conv.messages if m.role == "assistant")
    assert first_assistant.ttft_ms == 300  # first_token_time - start_time
    assert first_assistant.output_tokens == 5
    # tenant_id is present on the SOURCE side (dropped later by de-identification)
    assert conv.tenant_id == "20256789"


def test_runs_to_conversations_handles_missing_first_token_time():
    conv = sources.runs_to_conversations(
        [{"id": "x", "start_time": "2026-01-01T00:00:00Z", "outputs": {"content": "hi"},
          "extra": {"metadata": {"conversation_id": "c-2"}}}]
    )[0]
    assistant = next(m for m in conv.messages if m.role == "assistant")
    assert assistant.ttft_ms is None  # unavailable, not zero (AC-7)
