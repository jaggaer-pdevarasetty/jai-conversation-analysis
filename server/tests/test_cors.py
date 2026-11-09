"""CORS: the reviewer UI must work from loopback AND the host's private LAN IP.

Regression: opening the UI at http://10.19.8.252:3000 was blocked ("No 'Access-Control-Allow-Origin'
header is present") because the allowlist was loopback-only.
"""

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _allowed(origin: str) -> bool:
    """True if the server echoes the CORS allow-origin header for this origin."""
    res = client.get("/api/analysis/regions", headers={"Origin": origin})
    return res.headers.get("access-control-allow-origin") is not None


def test_loopback_origins_allowed():
    assert _allowed("http://localhost:3000")
    assert _allowed("http://127.0.0.1:3000")


def test_private_lan_origins_allowed():
    # RFC1918 ranges — the machine's LAN IP, any port (this is an internal tool).
    assert _allowed("http://10.19.8.252:3000")
    assert _allowed("http://192.168.1.50:3000")
    assert _allowed("http://172.16.4.9:3000")


def test_public_origin_is_still_rejected():
    assert not _allowed("https://evil.example.com")
    # a public IP that merely starts with the same digits must not slip through
    assert not _allowed("http://110.19.8.252:3000")


def test_preflight_succeeds_for_a_lan_origin():
    res = client.options(
        "/api/analysis/regions",
        headers={
            "Origin": "http://10.19.8.252:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert res.status_code in (200, 204)
    assert res.headers.get("access-control-allow-origin") == "http://10.19.8.252:3000"
