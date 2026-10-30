from dataclasses import replace

from fastapi.testclient import TestClient

from app.main import erstelle_app

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
    "media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def test_header_gesetzt(client):
    h = client.get("/").headers
    assert h["content-security-policy"] == CSP
    assert h["x-content-type-options"] == "nosniff"
    assert h["referrer-policy"] == "no-referrer"
    assert h["permissions-policy"] == "microphone=(self), camera=(), geolocation=()"
    assert h["x-frame-options"] == "DENY"


def test_kein_hsts_ohne_produktion(client):
    assert "strict-transport-security" not in client.get("/").headers


def test_hsts_in_produktion(einstellungen):
    produktiv = replace(einstellungen, produktion=True)
    with TestClient(erstelle_app(produktiv)) as c:
        h = c.get("/").headers
    assert h["strict-transport-security"] == "max-age=31536000"


def test_header_auch_bei_404(client):
    antwort = client.get("/gibt-es-nicht")
    assert antwort.status_code == 404
    assert antwort.headers["content-security-policy"] == CSP


def test_header_auch_bei_statischen_dateien(client):
    antwort = client.get("/static/css/style.css")
    assert antwort.headers["x-frame-options"] == "DENY"
