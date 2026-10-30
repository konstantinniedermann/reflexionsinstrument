"""Routen-Inventar: Jede Route der App ist geschuetzt, auch kuenftige."""

import re

import pytest
from conftest import anmelden, csrf_von
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import erstelle_app

# Gast-Ansicht (#19): ohne Anmeldung erreichbar, speichert nichts (Datenbank nur lesend,
# Nachweis in test_gast.py). Jede /gast-Route steht einzeln hier; eine neue braucht eine
# bewusste Ergaenzung mit Begruendung im Pull Request.
GAST_GET = {
    "/gast",
    "/gast/info",
    "/gast/runden/1",
    "/gast/tagebuch/neu",
    "/gast/tagebuch/neu/frei",
    "/gast/tagebuch/neu/impuls/1",
    "/gast/tagebuch/neu/leitfrage/1",
}
GAST_POST = {
    "/gast/runden/1",
    "/gast/tagebuch/neu/frei",
    "/gast/tagebuch/neu/impuls/1",
    "/gast/tagebuch/neu/leitfrage/1",
}
OEFFENTLICH = {"/", "/healthz"} | GAST_GET
# Laeuft ohne Sitzung, aber mit CSRF-Schutz: Anmelden und die Formulare der Gast-Ansicht.
OHNE_SITZUNG = {"/anmelden"} | GAST_POST


def inventar(einstellungen, methode):
    # Neuere FastAPI-Versionen fassen eingebundene Router zusammen; so werden sie aufgeloest.
    app = erstelle_app(einstellungen)
    pfade = {
        re.sub(r"\{[^}]+\}", "1", r.path)
        for r in iter_route_contexts(app.routes)
        if isinstance(r.original_route, APIRoute) and methode in (r.methods or ())
    }
    return sorted(pfade)


def rolle_von(pfad):
    if pfad.startswith("/verwaltung"):
        return "auftraggeberin"
    return "lehrperson"


@pytest.fixture
def konten(lehrperson, auftraggeberin):
    return {"lehrperson": lehrperson, "auftraggeberin": auftraggeberin}


def test_inventar_nicht_leer(einstellungen):
    gets = inventar(einstellungen, "GET")
    posts = inventar(einstellungen, "POST")
    assert "/lehrperson" in gets
    assert "/anmelden" in posts
    assert "/abmelden" in posts


def test_nur_bekannte_methoden(einstellungen):
    app = erstelle_app(einstellungen)
    for r in iter_route_contexts(app.routes):
        if isinstance(r.original_route, APIRoute):
            fremd = set(r.methods or ()) - {"GET", "HEAD", "POST"}
            assert not fremd, (
                f"{r.path} nutzt {sorted(fremd)}: Das Inventar prueft nur GET und POST. "
                "Erst die Tests unten erweitern, dann die Methode zulassen."
            )


def test_einziger_mount_ist_static(einstellungen):
    app = erstelle_app(einstellungen)
    andere = [
        r.path
        for r in iter_route_contexts(app.routes)
        if not isinstance(r.original_route, APIRoute) and r.path != "/static"
    ]
    assert andere == [], (
        f"Weitere Mounts oder Routen ohne Inventar: {andere}. "
        "Sie waeren ohne Anmeldung erreichbar, bis das Inventar sie pruefen kann."
    )


def test_gast_liste_deckt_sich_mit_den_routen(einstellungen):
    assert {p for p in inventar(einstellungen, "GET") if p.startswith("/gast")} == GAST_GET
    assert {p for p in inventar(einstellungen, "POST") if p.startswith("/gast")} == GAST_POST


def test_get_routen_brauchen_anmeldung(client, einstellungen):
    for pfad in inventar(einstellungen, "GET"):
        if pfad in OEFFENTLICH:
            continue
        antwort = client.get(pfad)
        assert antwort.status_code == 303, pfad
        assert antwort.headers["location"] == "/", pfad


def test_post_routen_brauchen_csrf(client, einstellungen, konten):
    for pfad in inventar(einstellungen, "POST"):
        client.cookies.clear()
        if pfad not in OHNE_SITZUNG:
            konto = konten[rolle_von(pfad)]
            assert anmelden(client, konto["benutzername"], konto["passwort"]).status_code == 303
        antwort = client.post(pfad, data={})
        assert antwort.status_code == 403, pfad
        assert "Formular abgelaufen" in antwort.text, pfad


def test_post_ohne_anmeldung_leitet_um(client, einstellungen):
    for pfad in inventar(einstellungen, "POST"):
        if pfad in OHNE_SITZUNG:
            continue
        client.cookies.clear()
        antwort = client.post(pfad, data={"csrf": csrf_von(client)})
        assert antwort.status_code == 303, pfad
        assert antwort.headers["location"] == "/", pfad


def test_lehrperson_erreicht_keine_verwaltung(client, einstellungen, konten):
    lp, ag = konten["lehrperson"], konten["auftraggeberin"]
    gets = inventar(einstellungen, "GET")
    anmelden(client, lp["benutzername"], lp["passwort"])
    for pfad in (p for p in gets if p.startswith("/verwaltung")):
        assert client.get(pfad).status_code == 403, pfad
    client.cookies.clear()
    anmelden(client, ag["benutzername"], ag["passwort"])
    for pfad in (p for p in gets if p.startswith("/lehrperson")):
        assert client.get(pfad).status_code == 403, pfad
