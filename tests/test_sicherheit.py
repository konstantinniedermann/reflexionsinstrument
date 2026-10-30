from dataclasses import replace

import pytest
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


def test_no_store_auf_seiten(client):
    assert client.get("/").headers["cache-control"] == "no-store"
    assert client.get("/gibt-es-nicht").headers["cache-control"] == "no-store"


def test_static_ohne_no_store(client):
    assert "cache-control" not in client.get("/static/css/style.css").headers


def test_404_ist_html_fehlerseite(client):
    antwort = client.get("/gibt-es-nicht")
    assert antwort.status_code == 404
    assert "text/html" in antwort.headers["content-type"]
    assert "Diese Seite gibt es nicht." in antwort.text
    assert "content-security-policy" in antwort.headers


@pytest.mark.parametrize(("methode", "pfad"), [("post", "/lehrperson"), ("delete", "/")])
def test_405_zeigt_fehlerseite_mit_headern(client, methode, pfad):
    antwort = getattr(client, methode)(pfad)
    assert antwort.status_code == 405
    assert antwort.headers["content-type"].startswith("text/html")
    assert "Diese Seite gibt es so nicht." in antwort.text
    assert "allow" in antwort.headers
    assert antwort.headers["x-content-type-options"] == "nosniff"


def test_robots_header(client):
    for pfad in ("/", "/gast", "/gibt-es-nicht"):
        assert client.get(pfad).headers["x-robots-tag"] == "noindex, nofollow"
