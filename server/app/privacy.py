"""Privacy governance: switch between the authorised admin view and the AC-10 pooled view.

- `admin` (default): tenant/user identity is shown (internal reviewer dashboard).
- `pooled`  (ADR-0007 / AC-10): NO tenant/user identity leaves the API — names become stable
  pseudonyms (so grouping still works without revealing who), ids/titles are dropped, and the
  per-tenant drill-down endpoints are disabled.

Stable pseudonyms let you still say "these 5 chats are the same tenant" without knowing which.
"""

from __future__ import annotations

import hashlib

from .config import settings


def is_pooled() -> bool:
    return settings.privacy_mode.lower() == "pooled"


def _pseudo(prefix: str, value) -> str | None:
    if value is None:
        return None
    digest = hashlib.sha256(f"{prefix}:{value}".encode()).hexdigest()[:8]
    return f"{prefix}-{digest}"


def apply_meta(meta: dict) -> dict:
    """Redact source metadata to pseudonyms in pooled mode; pass through in admin mode."""
    if not is_pooled():
        return meta
    return {
        **meta,
        "tenant_name": _pseudo("tenant", meta.get("tenant_id")),
        "user_name": _pseudo("user", meta.get("user_id")),
        "tenant_id": None,
        "user_id": None,
        "title": None,  # conversation titles can carry company/PII
        "ea": None,  # the EA badge's label names the tenant → drop it in pooled mode (AC-10)
    }
