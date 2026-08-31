"""Early Access (EA) customer roster.

Mirrors the Confluence page "EA Customers" (CDAOAgenti / 1682931724). Confluence is the source
of truth; this static config exists because the app has no Confluence credentials — update BOTH
together when the roster changes.

Matching: prefer an exact `tenant_id` match (unambiguous) when the roster carries ids; otherwise
fall back to a whole-word, case-insensitive match on the source `tenants.name`. Name matching is
heuristic — a generic word like "vista"/"bosch" could in theory match an unrelated tenant, so add
the real tenant ids to `tenant_ids` to eliminate any ambiguity.
"""

from __future__ import annotations

import re

# key (whole-word, case-insensitive, in the tenant name) -> metadata shown in the UI.
# `tenant_ids`: known source tenant ids for exact matching (fill in to remove name ambiguity).
EA_CUSTOMERS: dict[str, dict] = {
    "enel": {"label": "ENEL", "product": "JI", "status": "active",
             "privacy": "RoPA / ISO 42001 — review data handling with Legal before changes",
             "tenant_ids": ()},
    "orano": {"label": "Orano", "product": "JA", "status": "blocked", "privacy": "", "tenant_ids": ()},
    "emirates": {"label": "Emirates", "product": "JA", "status": "blocked", "privacy": "", "tenant_ids": ()},
    "vista": {"label": "Vista", "product": "JA", "status": "blocked", "privacy": "", "tenant_ids": ()},
    "bosch": {"label": "Bosch", "product": "JA", "status": "blocked", "privacy": "", "tenant_ids": ()},
}


def _badge(key: str, meta: dict) -> dict:
    """UI-facing badge (never includes the internal tenant_ids)."""
    return {
        "key": key,
        "label": meta["label"],
        "product": meta["product"],
        "status": meta["status"],
        "privacy": meta["privacy"],
        "privacy_sensitive": bool(meta["privacy"]),
    }


def ea_info(tenant_name: str | None, tenant_id: str | None = None) -> dict | None:
    """EA metadata for a tenant, else None. Exact tenant_id match takes precedence (unambiguous);
    otherwise a whole-word, case-insensitive name match ('ENEL S.p.A.' → enel, but 'Panelco' does
    not falsely match)."""
    if tenant_id is not None:
        tid = str(tenant_id)
        for key, meta in EA_CUSTOMERS.items():
            if tid in {str(x) for x in meta.get("tenant_ids", ())}:
                return _badge(key, meta)
    if tenant_name:
        name = tenant_name.lower()
        for key, meta in EA_CUSTOMERS.items():
            if re.search(rf"\b{re.escape(key)}\b", name):
                return _badge(key, meta)
    return None
