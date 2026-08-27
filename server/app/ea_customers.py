"""Early Access (EA) customer roster.

Mirrors the Confluence page "EA Customers" (CDAOAgenti / 1682931724). Confluence is the source
of truth; this static config exists because the app has no Confluence credentials — update BOTH
together when the roster changes. Matching is by tenant NAME (the source `tenants.name`), since
that is the only stable handle we share with the roster.
"""

from __future__ import annotations

import re

# key (matched as a whole word, case-insensitive, in the tenant name) -> metadata shown in the UI.
EA_CUSTOMERS: dict[str, dict] = {
    "enel": {"label": "ENEL", "product": "JI", "status": "active",
             "privacy": "RoPA / ISO 42001 — review data handling with Legal before changes"},
    "orano": {"label": "Orano", "product": "JA", "status": "blocked", "privacy": ""},
    "emirates": {"label": "Emirates", "product": "JA", "status": "blocked", "privacy": ""},
    "vista": {"label": "Vista", "product": "JA", "status": "blocked", "privacy": ""},
    "bosch": {"label": "Bosch", "product": "JA", "status": "blocked", "privacy": ""},
}


def ea_info(tenant_name: str | None) -> dict | None:
    """EA metadata for a tenant name, else None. Whole-word, case-insensitive match so
    'ENEL S.p.A.' → enel but 'Panelco' does not falsely match."""
    if not tenant_name:
        return None
    name = tenant_name.lower()
    for key, meta in EA_CUSTOMERS.items():
        if re.search(rf"\b{re.escape(key)}\b", name):
            return {"key": key, "privacy_sensitive": bool(meta["privacy"]), **meta}
    return None
