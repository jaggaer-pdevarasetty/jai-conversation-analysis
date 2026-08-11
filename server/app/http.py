"""Shared HTTP client honouring corporate proxy + CA settings from the environment.

For networks behind a TLS-inspecting proxy (e.g. Zscaler): point REQUESTS_CA_BUNDLE (or
SSL_CERT_FILE) at the proxy's root CA and set HTTPS_PROXY. We NEVER disable verification —
this is a safe, env-driven trust of the corporate CA, not `verify=False`.
"""

from __future__ import annotations

import os

import httpx


def _verify() -> str | bool:
    # A CA bundle path if provided (trust the corporate root CA); else default (certifi).
    return os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or True


def client(*, timeout: float = 15.0) -> httpx.Client:
    # trust_env=True → honour HTTPS_PROXY / HTTP_PROXY / NO_PROXY from the environment.
    return httpx.Client(verify=_verify(), trust_env=True, timeout=timeout)
