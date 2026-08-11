"""Keep tests hermetic: never let a developer's real .env / exported keys leak in.

This runs at collection time (before app modules import), so `app.config` sees a clean
environment and the deterministic (rules) classifier + in-memory store are used.
"""

import os

os.environ["DOTENV_DISABLE"] = "1"
for _k in ("GEMINI_API_KEY", "LANGSMITH_API_KEY", "CHAT_DB_URL", "STORE_BACKEND", "RESULTS_DB_URL"):
    os.environ.pop(_k, None)
