"""Routen-Inventar: Jede Route der App ist geschuetzt, auch kuenftige."""

import re

import pytest
from conftest import anmelden, csrf_von
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import erstelle_app

# Ohne Anmeldung erreichbar. #19 ergaenzt `/gast...`; neue Ausnahmen nur mit Begruendung.
OEFFENTLICH = {"/", "/healthz"}
# Nur zum Anmelden selbst gedacht: laeuft ohne Sitzung, aber mit CSRF-Schutz.
OHNE_SITZUNG = {"/anmelden"}


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
