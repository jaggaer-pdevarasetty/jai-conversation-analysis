"""RFC 7807 Problem Details for HTTP errors."""

from __future__ import annotations

from fastapi.responses import JSONResponse

PROBLEM_CONTENT_TYPE = "application/problem+json"


def problem_response(status: int, title: str, detail: str | None = None) -> JSONResponse:
    body: dict[str, object] = {"type": "about:blank", "title": title, "status": status}
    if detail:
        body["detail"] = detail
    return JSONResponse(status_code=status, content=body, media_type=PROBLEM_CONTENT_TYPE)
