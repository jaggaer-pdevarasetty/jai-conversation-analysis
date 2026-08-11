"""Runtime configuration from environment (no secrets in code; ADR-0001)."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    # Chat DB — READ ONLY (SELECT). Empty in dev → analyzer runs on fixtures.
    chat_db_url: str = os.getenv("CHAT_DB_URL", "")
    # LangSmith (read) — authoritative tokens/latency.
    langsmith_base_url: str = os.getenv("LANGSMITH_BASE_URL", "https://api.smith.langchain.com")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "jai-orchestrator")
    # Gemini classifier (empty → deterministic rules fallback).
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    # Common store: "memory" (default) or "sql" (SQLite locally / Postgres via URL).
    store_backend: str = os.getenv("STORE_BACKEND", "memory")
    results_db_url: str = os.getenv("RESULTS_DB_URL", "sqlite:///./data/analysis.db")
    # RBAC gate for the reviewer API (off in dev/tests).
    rbac_enabled: bool = os.getenv("RBAC_ENABLED", "false").lower() == "true"


settings = Settings()
