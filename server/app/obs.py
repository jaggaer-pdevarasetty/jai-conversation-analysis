"""Minimal structured (JSON) event logging for observability — dependency-free.

One line of JSON per event on stderr, so logs are greppable/ingestable (Cloud Logging,
Loki, etc.) without a logging framework. Use for lifecycle events: run completed, analysis
failed, dead-letter, etc.
"""

from __future__ import annotations

import json
import sys
import time


def log_event(event: str, **fields) -> None:
    record = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "event": event, **fields}
    print(json.dumps(record, default=str), file=sys.stderr, flush=True)
