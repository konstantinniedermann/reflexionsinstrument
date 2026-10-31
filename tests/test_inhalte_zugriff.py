"""Akzeptanzkriterium: Nur die Auftraggeberin kann Inhalte aendern."""

import re

import pytest
from conftest import als_lehrperson, als_leitung, csrf_von
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import erstelle_app

PRAEFIX = "/verwaltung/inhalte"
TABELLEN = (
    "einstellungen",
    "texte",
    "info_abschnitte",
    "runden",
    "fragen",
    "leitfragen",
    "impulse",
    "antworten",
    "tagebucheintraege",
)
FORMULAR = {
    "titel": "Geändert",
    "inhalt": "Geändert",
    "text": "Geändert",
    "begruessung": "Geändert",
    "projektstart": "2026-12-01",
    "freischaltdatum": "2026-12-01",
    "sichtbar_ab": "2026-12-01",
    "typ": "freitext",
    "fallbeispiel": "Geändert",
    "skala_min_text": "Geändert",
    "skala_max_text": "Geändert",
    "richtung": "runter",
}


@pytest.fixture
def beispielinhalte(db):
    db.execute(
        "INSERT INTO info_abschnitte (id, titel, inhalt, reihenfolge) VALUES (1, 'T', 'I', 1)"
    )
    db.execute("INSERT INTO runden (id, titel, freischaltdatum) VALUES (1, 'R', '2026-11-23')")
    db.execute(
        "INSERT INTO fragen (id, runde_id, text, typ, reihenfolge) VALUES (1, 1, 'F', 'freitext', 1)"
    )
    db.execute("INSERT INTO leitfragen (id, text, reihenfolge) VALUES (1, 'L', 1)")
    db.execute("INSERT INTO impulse (id, text, sichtbar_ab) VALUES (1, 'I', '2026-11-23')")
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('titel', 'Vorher')")
    db.execute("INSERT INTO texte (schluessel, inhalt) VALUES ('hinweis_tagebuch', 'Vorher')")


def routen(einstellungen, methode):
    app = erstelle_app(einstellungen)
    pfade = set()
    for r in iter_route_contexts(app.routes):
        if (
            isinstance(r.original_route, APIRoute)
            and methode in (r.methods or ())
            and r.path.startswith(PRAEFIX)
        ):
            pfad = r.path.replace("{schluessel}", "hinweis_tagebuch")
            pfade.add(re.sub(r"\{\w+_id\}", "1", pfad))
    return sorted(pfade)


def abzug(db):
    return {t: sorted(tuple(z) for z in db.execute(f"SELECT * FROM {t}")) for t in TABELLEN}


def test_lehrperson_kann_keine_inhalte_aendern(
    client, einstellungen, db, lehrperson, beispielinhalte
):
    als_lehrperson(client, lehrperson)
    vorher = abzug(db)
    for pfad in routen(einstellungen, "GET"):
        antwort = client.get(pfad)
        assert antwort.status_code == 403, pfad
        assert "Kein Zugriff" in antwort.text, pfad
    token = csrf_von(client, "/lehrperson/info")
    for pfad in routen(einstellungen, "POST"):
        antwort = client.post(pfad, data={"csrf": token, **FORMULAR})
        assert antwort.status_code == 403, pfad
        assert "Kein Zugriff" in antwort.text, pfad
    assert abzug(db) == vorher


def test_kontrolle_auftraggeberin_aendert(client, db, auftraggeberin, beispielinhalte):
    als_leitung(client, auftraggeberin)
    vorher = abzug(db)
    pfad = PRAEFIX + "/allgemein"
    antwort = client.post(pfad, data={"csrf": csrf_von(client, pfad), **FORMULAR})
    assert antwort.status_code == 303
    assert abzug(db) != vorher


def test_inventar_inhalte_nicht_leer(einstellungen):
    gets = routen(einstellungen, "GET")
    assert PRAEFIX in gets and PRAEFIX + "/allgemein" in gets
    assert PRAEFIX + "/allgemein" in routen(einstellungen, "POST")
