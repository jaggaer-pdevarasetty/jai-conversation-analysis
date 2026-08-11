"""Runtime configuration from environment (no secrets in code; ADR-0001)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load the repo-root .env before reading settings (real env vars still win; override=False).
# Tests set DOTENV_DISABLE=1 (conftest) so a developer's real .env never leaks into them.
if os.getenv("DOTENV_DISABLE") != "1":
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# Guard: a CA-bundle env var pointing at a missing file breaks libraries that read it
# directly (requests / google-genai). Drop it (with a warning) so they fall back to certifi
# / the OS trust store. This never disables TLS verification.
for _ca_var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
    _p = os.environ.get(_ca_var)
    if _p and not os.path.isfile(os.path.expanduser(os.path.expandvars(_p))):
        print(f"[warn] {_ca_var} points to a missing file ({_p}); ignoring it", flush=True)
        os.environ.pop(_ca_var, None)


@dataclass(frozen=True)
class Settings:
    # Chat DB — READ ONLY (SELECT). Empty in dev → analyzer runs on fixtures.
    chat_db_url: str = os.getenv("CHAT_DB_URL", "")
    # The real conversations live in DB `jai_agentos_uit`, schema `jai_agentos_schema_uit`.
    # We override the database name so a CHAT_DB_URL that points at the schema name still works.
    chat_db_name: str = os.getenv("CHAT_DB_NAME", "jai_agentos_uit")
    chat_db_schema: str = os.getenv("CHAT_DB_SCHEMA", "jai_agentos_schema_uit")
    chatdb_limit: int = int(os.getenv("CHATDB_LIMIT", "200"))

    # LangSmith (read) — authoritative tokens/latency + source of real conversations.
    langsmith_base_url: str = os.getenv("LANGSMITH_BASE_URL", "https://api.smith.langchain.com")
    langsmith_api_key: str = os.getenv("LANGSMITH_API_KEY", "")
    langsmith_project: str = os.getenv("LANGSMITH_PROJECT", "jai-orchestrator")
    langsmith_limit: int = int(os.getenv("LANGSMITH_LIMIT", "1000"))  # total runs cap (paginated)

    # Conversation source: "fixtures" (samples) | "chatdb" (REAL, canonical) | "langsmith".
    source: str = os.getenv("SOURCE", "fixtures")

    # Gemini via VERTEX AI only (enterprise). Vertex uses OAuth2 (service account / ADC via
    # GOOGLE_APPLICATION_CREDENTIALS) + project + location — NOT an API key. Classification
    # is enabled only when project + location are set; otherwise deterministic rules run.
    vertex_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    vertex_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    # Conversations classified per LLM call (batching cuts API calls ~batch_size-fold).
    batch_size: int = int(os.getenv("BATCH_SIZE", "10"))
    # On-demand (re)analyse cap per conversation per day (prevents abuse / runaway cost).
    max_analyses_per_day: int = int(os.getenv("MAX_ANALYSES_PER_DAY", "3"))
    # Lazy analyse: auto-analyse a user's un-analysed conversations when a reviewer opens them.
    lazy_analyze: bool = os.getenv("LAZY_ANALYZE", "true").lower() == "true"
    # Scheduled sweep cadence in hours (enqueues eligible convos). 0 disables (AC-1: every 4h).
    schedule_hours: float = float(os.getenv("SCHEDULE_HOURS", "4"))

    # Common store: "memory" (default, for tests/no-DB) or "sql" (Postgres — ADR-0009).
    # SQLite is intentionally NOT supported for storing data; use Postgres (podman/Docker).
    store_backend: str = os.getenv("STORE_BACKEND", "memory")
    results_db_url: str = os.getenv(
        "RESULTS_DB_URL", "postgresql+psycopg://jai:jai@localhost:5433/analysis"
    )

    # RBAC gate for the reviewer API (off in dev/tests).
    rbac_enabled: bool = os.getenv("RBAC_ENABLED", "false").lower() == "true"

    @property
    def vertex_configured(self) -> bool:
        return bool(self.vertex_project and self.vertex_location)


settings = Settings()
