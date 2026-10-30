"""Akzeptanzkriterium aus #14: Eine zweite Lehrperson sieht und aendert nichts der ersten."""

import re

import pytest
import testdaten
from conftest import anmelden, csrf_von
from fastapi.routing import APIRoute, iter_route_contexts

from app.main import erstelle_app


@pytest.fixture
def daten_der_ersten(db, lehrperson, einstellungen, heute_ist):
    from datetime import date

    rid, (f1, _) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    imp = testdaten.lege_impuls_an(db, "Impuls Eins", "2026-11-23")
    leit = testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    k = lehrperson["id"]
    testdaten.lege_antwort_an(db, f1, k, "GeheimA")
    aid = testdaten.lege_aufnahme_an(db, k, einstellungen.aufnahmen_verzeichnis)
    ids = [
        testdaten.lege_eintrag_an(db, k, "frei", "GeheimT"),
        testdaten.lege_eintrag_an(db, k, "impuls", "GeheimT", impuls_id=imp),
        testdaten.lege_eintrag_an(db, k, "leitfragen", "GeheimT", leitfrage_id=leit),
        testdaten.lege_eintrag_an(db, k, "aufnahme", "GeheimT", aufnahme_id=aid),
    ]
    db.commit()
    heute_ist(date(2026, 11, 24))
    return {"runde": rid, "frage": f1, "eintraege": ids}


@pytest.fixture
def als_zweite(client, zweite_lehrperson):
    client.cookies.clear()
    anmelden(client, zweite_lehrperson["benutzername"], zweite_lehrperson["passwort"])
    return client


def _ordner(einstellungen):
    return sorted(p.name for p in einstellungen.aufnahmen_verzeichnis.iterdir())


def test_fremde_eintraege_404(als_zweite, daten_der_ersten, db, einstellungen):
    vorher = testdaten.abzug(db)
    dateien = _ordner(einstellungen)
    csrf = csrf_von(als_zweite, "/lehrperson")
    for eid in daten_der_ersten["eintraege"]:
        seite = f"/lehrperson/tagebuch/{eid}"
        assert als_zweite.get(seite).status_code == 404
        assert als_zweite.post(seite, data={"csrf": csrf, "text": "X"}).status_code == 404
        assert als_zweite.get(seite + "/loeschen").status_code == 404
        assert als_zweite.post(seite + "/loeschen", data={"csrf": csrf}).status_code == 404
    assert testdaten.abzug(db) == vorher
    assert _ordner(einstellungen) == dateien


def test_alle_routen_mit_eintrag_id(als_zweite, daten_der_ersten, db, einstellungen):
    app = erstelle_app(einstellungen)
    routen = [
        (r.path, m)
        for r in iter_route_contexts(app.routes)
        if isinstance(r.original_route, APIRoute)
        and r.path.startswith("/lehrperson")
        and "{eintrag_id}" in r.path
        for m in (r.methods or ())
        if m in ("GET", "POST")
    ]
    assert routen
    vorher = testdaten.abzug(db)
    csrf = csrf_von(als_zweite, "/lehrperson")
    eid = daten_der_ersten["eintraege"][0]
    for pfad, methode in routen:
        ziel = pfad.replace("{eintrag_id}", str(eid))
        if methode == "GET":
            antwort = als_zweite.get(ziel)
        else:
            antwort = als_zweite.post(ziel, data={"csrf": csrf, "text": "X"})
        assert antwort.status_code == 404, (methode, pfad)
    assert testdaten.abzug(db) == vorher


def test_fremde_antworten_unsichtbar(als_zweite, daten_der_ersten, db):
    rid = daten_der_ersten["runde"]
    for pfad in (f"/lehrperson/runden/{rid}", "/lehrperson", "/lehrperson/eintraege"):
        text = als_zweite.get(pfad).text
        assert "GeheimA" not in text and "GeheimT" not in text, pfad
    vorher = testdaten.abzug(db)
    pfad = f"/lehrperson/runden/{rid}/loeschen"
    antwort = als_zweite.post(pfad, data={"csrf": csrf_von(als_zweite, pfad)})
    assert antwort.status_code == 303
    assert testdaten.abzug(db) == vorher
    assert db.execute("SELECT text FROM antworten").fetchone()[0] == "GeheimA"
    assert re.search("Noch keine Einträge", als_zweite.get("/lehrperson/eintraege").text)
