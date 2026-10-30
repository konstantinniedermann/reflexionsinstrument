import time
from dataclasses import replace
from typing import Annotated

import pytest
from fastapi import Depends
from fastapi.responses import PlainTextResponse
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.db import hole_db, verbinde
from app.konten import finde_konto, lege_konto_an, loesche_konto, setze_passwort
from app.main import erstelle_app
from app.sitzung import (
    DAUER_KURZ,
    DAUER_LANG,
    VERLAENGERN_AB,
    anmelden,
    braucht_auftraggeberin,
    braucht_lehrperson,
)
from app.vorlagen import templates


@pytest.fixture
def uhr(monkeypatch):
    """Stellt die Uhr vor; wirkt auf Erzeugung und Pruefung der Signatur."""
    echt = time.time
    versatz = [0]
    monkeypatch.setattr(time, "time", lambda: echt() + versatz[0])

    def vorstellen(sekunden):
        versatz[0] += sekunden

    return vorstellen


@pytest.fixture
def app(einstellungen):
    app = erstelle_app(einstellungen)

    @app.post("/t/anmelden/{konto_id}")
    def t_anmelden(
        request: Request, konto_id: int, db: Annotated[object, Depends(hole_db)], dauerhaft: int = 0
    ):
        anmelden(request, finde_konto(db, konto_id), bool(dauerhaft))
        return PlainTextResponse("ok")

    @app.get("/t/lp")
    def t_lp(konto: Annotated[object, Depends(braucht_lehrperson)]):
        return PlainTextResponse(konto.benutzername)

    @app.get("/t/ag")
    def t_ag(konto: Annotated[object, Depends(braucht_auftraggeberin)]):
        return PlainTextResponse(konto.benutzername)

    @app.get("/t/seite")
    def t_seite(request: Request, konto: Annotated[object, Depends(braucht_lehrperson)]):
        return templates.TemplateResponse(request, "start.html", {})

    return app


@pytest.fixture
def client(app):
    with TestClient(app, follow_redirects=False) as c:
        yield c


@pytest.fixture
def db(client, einstellungen):
    conn = verbinde(einstellungen.db_pfad)
    yield conn
    conn.close()


@pytest.fixture
def lp(db):
    return lege_konto_an(db, "Anna", "lp.anna", "geheim-passwort")


@pytest.fixture
def ag(db):
    return lege_konto_an(
        db, "Projektleitung", "projektleitung", "geheim-passwort", "auftraggeberin"
    )


def sitzungs_wert(antwort) -> str:
    cookie = next(c for c in antwort.headers.get_list("set-cookie") if c.startswith("sitzung="))
    return cookie.split(";")[0].removeprefix("sitzung=")


def anmelden_roh(client, konto, dauerhaft=True) -> str:
    """Meldet an und gibt den Cookie-Wert zurueck; der Cookie-Speicher bleibt leer.

    So haengt der Test nicht von der Uhr des Cookie-Speichers ab.
    """
    antwort = client.post(f"/t/anmelden/{konto.id}?dauerhaft={int(dauerhaft)}")
    client.cookies.clear()
    return sitzungs_wert(antwort)


def hole(client, pfad, wert):
    return client.get(pfad, headers={"cookie": f"sitzung={wert}"})


def test_ohne_cookie_umleitung_auf_start(client):
    antwort = client.get("/t/lp")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"


def test_angemeldet_kommt_durch(client, lp):
    wert = anmelden_roh(client, lp)
    antwort = hole(client, "/t/lp", wert)
    assert antwort.status_code == 200
    assert antwort.text == "lp.anna"


def test_falsche_rolle_403(client, lp, ag):
    wert_lp = anmelden_roh(client, lp)
    antwort = hole(client, "/t/ag", wert_lp)
    assert antwort.status_code == 403
    assert "Kein Zugriff" in antwort.text
    wert_ag = anmelden_roh(client, ag)
    antwort = hole(client, "/t/lp", wert_ag)
    assert antwort.status_code == 403
    assert "Kein Zugriff" in antwort.text


def test_sitzungscookie_attribute(client, lp):
    dauerhaft = client.post(f"/t/anmelden/{lp.id}?dauerhaft=1").headers.get_list("set-cookie")
    cookie = next(c for c in dauerhaft if c.startswith("sitzung="))
    assert "Max-Age=2592000" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=Lax" in cookie
    assert "Path=/" in cookie
    assert "Secure" not in cookie
    kurz = client.post(f"/t/anmelden/{lp.id}?dauerhaft=0").headers.get_list("set-cookie")
    cookie = next(c for c in kurz if c.startswith("sitzung="))
    assert "Max-Age" not in cookie
    assert "HttpOnly" in cookie


def test_sitzungscookie_secure_in_produktion(einstellungen, tmp_path):
    produktiv = replace(einstellungen, produktion=True, geheimer_schluessel="y" * 40)
    app = erstelle_app(produktiv)

    @app.post("/t/anmelden")
    def t_anmelden(request: Request):
        anmelden(
            request,
            lege_konto_an(verbinde(produktiv.db_pfad), "A", "lp.zett", "geheim-passwort"),
            True,
        )
        return PlainTextResponse("ok")

    with TestClient(app) as c:
        cookies = c.post("/t/anmelden").headers.get_list("set-cookie")
    assert "Secure" in next(x for x in cookies if x.startswith("sitzung="))


def test_anmelden_erneuert_csrf(client, lp):
    erste = client.get("/t/lp").headers.get_list("set-cookie")
    assert any(c.startswith("csrf=") for c in erste)
    zweite = client.post(f"/t/anmelden/{lp.id}?dauerhaft=1").headers.get_list("set-cookie")
    csrf = [c for c in zweite if c.startswith("csrf=")]
    assert len(csrf) == 1
    assert csrf[0].split(";")[0] != next(c for c in erste if c.startswith("csrf=")).split(";")[0]


def test_manipuliertes_cookie_ungueltig(client, lp):
    wert = anmelden_roh(client, lp)
    assert hole(client, "/t/lp", wert[:-2] + "xx").status_code == 303
    assert hole(client, "/t/lp", "muell").status_code == 303


def test_kurze_sitzung_nach_12h_ungueltig(client, lp, uhr):
    wert = anmelden_roh(client, lp, dauerhaft=False)
    uhr(DAUER_KURZ - 60)
    assert hole(client, "/t/lp", wert).status_code == 200
    uhr(120)
    assert hole(client, "/t/lp", wert).status_code == 303


def test_lange_sitzung_nach_30_tagen_ungueltig(client, lp, uhr):
    wert = anmelden_roh(client, lp)
    uhr(DAUER_LANG + 60)
    assert hole(client, "/t/lp", wert).status_code == 303


def test_lange_sitzung_nach_2_tagen_wird_verlaengert(client, lp, uhr):
    wert = anmelden_roh(client, lp)
    assert "sitzung=" not in "".join(hole(client, "/t/lp", wert).headers.get_list("set-cookie"))
    uhr(2 * VERLAENGERN_AB)
    antwort = hole(client, "/t/lp", wert)
    assert antwort.status_code == 200
    neu = sitzungs_wert(antwort)
    assert neu != wert
    cookie = next(c for c in antwort.headers.get_list("set-cookie") if c.startswith("sitzung="))
    assert "Max-Age=2592000" in cookie
    # Der neue Wert gilt ab jetzt, auch kurz vor Ablauf des alten.
    uhr(DAUER_LANG - 3 * VERLAENGERN_AB)
    assert hole(client, "/t/lp", neu).status_code == 200


def test_kurze_sitzung_wird_nicht_verlaengert(client, lp, uhr):
    wert = anmelden_roh(client, lp, dauerhaft=False)
    uhr(DAUER_KURZ - 60)
    assert "sitzung=" not in "".join(hole(client, "/t/lp", wert).headers.get_list("set-cookie"))


def test_versionswechsel_beendet_sitzung(client, lp, db):
    wert = anmelden_roh(client, lp)
    setze_passwort(db, lp.id, "neues-passwort")
    assert hole(client, "/t/lp", wert).status_code == 303


def test_geloeschtes_konto_beendet_sitzung(client, lp, db, einstellungen):
    wert = anmelden_roh(client, lp)
    loesche_konto(db, lp.id, einstellungen.aufnahmen_verzeichnis)
    assert hole(client, "/t/lp", wert).status_code == 303


def test_altes_cookie_nach_neuanlage_mit_gleicher_id_ungueltig(client, lp, db, einstellungen):
    wert = anmelden_roh(client, lp)
    loesche_konto(db, lp.id, einstellungen.aufnahmen_verzeichnis)
    neu = lege_konto_an(db, "Berta", "lp.berta", "geheim-passwort")
    assert neu.id == lp.id
    assert hole(client, "/t/lp", wert).status_code == 303


def test_ungueltiges_cookie_wird_geloescht(client):
    antwort = hole(client, "/t/lp", "muell")
    assert antwort.status_code == 303
    cookie = next(c for c in antwort.headers.get_list("set-cookie") if c.startswith("sitzung="))
    assert cookie.startswith('sitzung=""')
    assert "Max-Age=0" in cookie


def test_cookie_mit_falschem_inhalt_ist_abgemeldet(client, app, lp):
    from itsdangerous import URLSafeTimedSerializer

    s = URLSafeTimedSerializer(app.state.einstellungen.geheimer_schluessel, salt="sitzung")
    for inhalt in ([1, 2, 3], "text", {"k": "x", "v": 1, "d": True}, {"k": lp.id}, None):
        assert hole(client, "/t/lp", s.dumps(inhalt)).status_code == 303


def test_kopf_zeigt_anzeigename_und_abmelden(client, lp):
    wert = anmelden_roh(client, lp)
    html = hole(client, "/t/seite", wert).text
    assert "Anna" in html
    assert 'action="/abmelden"' in html
    assert 'name="csrf"' in html
    assert 'action="/abmelden"' not in client.get("/").text
