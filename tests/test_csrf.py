import re
from dataclasses import replace

import pytest
from fastapi import Depends
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.csrf import csrf_feld, pruefe_csrf
from app.main import erstelle_app

SCHLUESSEL_PRODUKTION = "x" * 40


def baue_app(einstellungen):
    app = erstelle_app(einstellungen)

    @app.get("/t/formular")
    def formular(request: Request):
        return HTMLResponse(str(csrf_feld(request)))

    @app.post("/t/senden", dependencies=[Depends(pruefe_csrf)])
    def senden():
        return {"ok": True}

    return app


def lies_token(antwort) -> str:
    return re.search(r'name="csrf" value="([0-9a-f]+)"', antwort.text).group(1)


@pytest.fixture
def app_client(einstellungen):
    with TestClient(baue_app(einstellungen)) as c:
        yield c


def test_erste_seite_hat_gueltiges_csrf(app_client):
    antwort = app_client.get("/t/formular")
    assert "csrf" in app_client.cookies
    antwort = app_client.post("/t/senden", data={"csrf": lies_token(antwort)})
    assert antwort.status_code == 200


def test_post_ohne_token_403(app_client):
    app_client.get("/t/formular")
    antwort = app_client.post("/t/senden", data={})
    assert antwort.status_code == 403
    assert "abgelaufen" in antwort.text


def test_post_mit_falschem_token_403(app_client):
    app_client.get("/t/formular")
    assert app_client.post("/t/senden", data={"csrf": "abc"}).status_code == 403


def test_token_eines_anderen_cookies_403(einstellungen):
    app = baue_app(einstellungen)
    with TestClient(app) as eins, TestClient(app) as zwei:
        token = lies_token(eins.get("/t/formular"))
        zwei.get("/t/formular")
        assert zwei.post("/t/senden", data={"csrf": token}).status_code == 403


def csrf_set_cookie(antwort) -> str:
    return next(c for c in antwort.headers.get_list("set-cookie") if c.startswith("csrf="))


def test_csrf_cookie_attribute(app_client):
    cookie = csrf_set_cookie(app_client.get("/t/formular"))
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Max-Age=2592000" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie


def test_csrf_cookie_secure_in_produktion(einstellungen):
    produktiv = replace(einstellungen, produktion=True, geheimer_schluessel=SCHLUESSEL_PRODUKTION)
    with TestClient(baue_app(produktiv)) as c:
        assert "Secure" in csrf_set_cookie(c.get("/t/formular"))


def test_vorhandenes_cookie_wird_nicht_neu_gesetzt(app_client):
    app_client.get("/t/formular")
    antwort = app_client.get("/t/formular")
    assert not antwort.headers.get_list("set-cookie")
