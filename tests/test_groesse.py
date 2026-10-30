import asyncio

import pytest
from conftest import csrf_von
from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.groesse import GRENZE, GRENZE_UPLOAD, GroessenGrenze, ZuGross, grenze_fuer

UPLOAD = "/lehrperson/tagebuch/neu/aufnahme"


@pytest.mark.parametrize(
    ("pfad", "erwartet"),
    [
        (UPLOAD, GRENZE_UPLOAD),
        ("/lehrperson/runden/3/fragen/12/aufnahme", GRENZE_UPLOAD),
        ("/anmelden", GRENZE),
        ("/lehrperson/runden/3", GRENZE),
        (UPLOAD + "/x", GRENZE),
        ("/x" + UPLOAD, GRENZE),
    ],
)
def test_grenze_fuer(pfad, erwartet):
    assert grenze_fuer(pfad) == erwartet


def _zu_gross(client):
    return client.post(
        "/anmelden",
        data={"csrf": csrf_von(client), "benutzername": "a" * GRENZE, "passwort": "x"},
    )


def test_anmelden_zu_gross(client):
    antwort = _zu_gross(client)
    assert antwort.status_code == 413
    assert "Zu gross" in antwort.text
    assert "stimmt nicht" not in antwort.text


def test_ohne_content_length_gezaehlt(client):
    def stuecke():
        yield b"benutzername=" + b"a" * 1011
        for _ in range(1100):  # zusammen gut 1 MiB, ohne Content-Length
            yield b"a" * 1024

    antwort = client.post(
        "/anmelden",
        content=stuecke(),
        headers={"content-type": "application/x-www-form-urlencoded"},
    )
    assert antwort.status_code == 413


def test_knapp_unter_grenze(client):
    antwort = client.post(
        "/anmelden",
        data={"csrf": csrf_von(client), "benutzername": "a" * 60 * 1024, "passwort": "x"},
    )
    assert antwort.status_code == 400
    assert "Benutzername oder Passwort stimmt nicht." in antwort.text


def test_laenge_keine_zahl():
    async def app(scope, receive, send):
        await receive()

    scope = {
        "type": "http",
        "path": "/anmelden",
        "headers": [(b"content-length", b"abc")],
    }

    async def ablauf():
        await GroessenGrenze(app)(scope, None, None)

    with pytest.raises(ZuGross):
        asyncio.run(ablauf())


def test_upload_pfad_grosse_grenze():
    app = FastAPI()

    @app.exception_handler(StarletteHTTPException)
    async def fehler(request: Request, exc: StarletteHTTPException):
        return PlainTextResponse("fehler", status_code=exc.status_code)

    @app.post(UPLOAD)
    async def upload(request: Request):
        await request.body()
        return PlainTextResponse("ok")

    @app.post("/andere")
    async def andere(request: Request):
        await request.body()
        return PlainTextResponse("ok")

    app.add_middleware(GroessenGrenze)
    with TestClient(app) as c:
        assert c.post(UPLOAD, content=b"a" * (1024 * 1024)).status_code == 200
        assert c.post("/andere", content=b"a" * (1024 * 1024 + 1)).status_code == 413
        assert c.post(UPLOAD, content=b"a" * (GRENZE_UPLOAD + 1)).status_code == 413


def test_413_mit_sicherheits_headern(client):
    antwort = _zu_gross(client)
    assert "content-security-policy" in antwort.headers
    assert antwort.headers["cache-control"] == "no-store"


def test_get_unberuehrt(client):
    assert client.get("/").status_code == 200
