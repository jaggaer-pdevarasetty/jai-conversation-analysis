"""Select the common-store backend from config (ADR-0009)."""

from __future__ import annotations

from .config import settings
from .store import CommonStore


def make_store():
    if settings.store_backend == "sql":
        from .store_sql import SqlResultStore

        return SqlResultStore(settings.results_db_url)
    return CommonStore()
