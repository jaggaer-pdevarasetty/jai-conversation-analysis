"""Shared HTTP client that verifies TLS behind a corporate proxy (e.g. Zscaler) — safely.

Order of trust (verification is NEVER disabled):
1. An explicit CA bundle if REQUESTS_CA_BUNDLE / SSL_CERT_FILE points at a real file.
2. Else the OS trust store via `truststore` (macOS Keychain / Windows store) — this trusts
   the Zscaler root the OS already trusts, and tolerates corporate CAs that stricter
   OpenSSL rejects (e.g. "Basic Constraints not marked critical").
3. Else certifi defaults.
Proxies are honoured from the environment (HTTPS_PROXY / NO_PROXY) via trust_env.
"""

from __future__ import annotations

import os
import ssl

import httpx


def _verify() -> "str | ssl.SSLContext | bool":
    ca = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    if ca:
        path = os.path.expanduser(os.path.expandvars(ca))
        if os.path.isfile(path):
            return path
        print(f"[warn] CA bundle not found ({path}); falling back to the OS trust store", flush=True)
    try:
        import truststore

        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    except ImportError:
        return True


def client(*, timeout: float = 15.0) -> httpx.Client:
    # trust_env=True → honour HTTPS_PROXY / HTTP_PROXY / NO_PROXY from the environment.
    return httpx.Client(verify=_verify(), trust_env=True, timeout=timeout)
