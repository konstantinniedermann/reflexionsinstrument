"""Benachrichtigungen: Manifest, Service Worker, Abo-Routen und Senden in der Verwaltung (#37).

Hier ist die Funktion eingerichtet (VAPID-Schlüssel gesetzt); ohne Schlüssel siehe
test_benachrichtigung_aus.py.
"""

from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von
from test_push_abos import AUTH, P256DH

from app.config import Einstellungen
from app.push import Ergebnis, erzeuge_vapid_schluessel
from app.push_abos import alle_abos, anzahl_abos

ENDPUNKT = "https://fcm.googleapis.com/fcm/send/abc"


@pytest.fixture
def einstellungen(tmp_path):
    return Einstellungen(
        daten_verzeichnis=tmp_path / "daten",
        geheimer_schluessel="test-schluessel",
        produktion=False,
        vapid_schluessel=erzeuge_vapid_schluessel(),
    )


def _abo_daten(client, pfad, endpunkt=ENDPUNKT):
    return {"csrf": csrf_von(client, pfad), "endpunkt": endpunkt, "p256dh": P256DH, "auth": AUTH}


@pytest.fixture
def lp(client, lehrperson):
    return als_lehrperson(client, lehrperson)


@pytest.fixture
def leitung(client, auftraggeberin):
    return als_leitung(client, auftraggeberin)


def test_manifest(client, db):
    antwort = client.get("/manifest.webmanifest")
    assert antwort.status_code == 200
    assert antwort.headers["content-type"].startswith("application/manifest+json")
    manifest = antwort.json()
    assert manifest["start_url"] == "/"
    assert manifest["scope"] == "/"
    assert manifest["display"] == "standalone"
    assert manifest["name"]
    groessen = {s["sizes"] for s in manifest["icons"]}
    assert groessen == {"180x180", "192x192", "512x512"}
    for symbol in manifest["icons"]:
        assert client.get(symbol["src"]).status_code == 200


def test_service_worker_ohne_anmeldung(client):
    antwort = client.get("/sw.js")
    assert antwort.status_code == 200
    assert "javascript" in antwort.headers["content-type"]
    assert "showNotification" in antwort.text
    assert "notificationclick" in antwort.text


def test_abo_lehrperson(lp, db, lehrperson):
    antwort = lp.post("/benachrichtigung/abo", data=_abo_daten(lp, "/lehrperson"))
    assert antwort.status_code == 204
    zeile = db.execute("SELECT konto_id, endpunkt FROM push_abos").fetchone()
    assert tuple(zeile) == (lehrperson["id"], ENDPUNKT)


def test_abo_auftraggeberin(leitung, db):
    antwort = leitung.post("/benachrichtigung/abo", data=_abo_daten(leitung, "/verwaltung"))
    assert antwort.status_code == 204
    assert anzahl_abos(db) == 1


def test_abo_ohne_anmeldung(client, db):
    antwort = client.post("/benachrichtigung/abo", data=_abo_daten(client, "/"))
    assert antwort.status_code == 303
    assert anzahl_abos(db) == 0


def test_abo_ohne_csrf(lp, db):
    daten = _abo_daten(lp, "/lehrperson")
    daten["csrf"] = "falsch"
    assert lp.post("/benachrichtigung/abo", data=daten).status_code == 403
    assert anzahl_abos(db) == 0


def test_abo_fremde_adresse(lp, db):
    daten = _abo_daten(lp, "/lehrperson", "https://127.0.0.1/push")
    assert lp.post("/benachrichtigung/abo", data=daten).status_code == 400
    assert anzahl_abos(db) == 0


def test_abo_loeschen(lp, db):
    lp.post("/benachrichtigung/abo", data=_abo_daten(lp, "/lehrperson"))
    daten = {"csrf": csrf_von(lp, "/lehrperson"), "endpunkt": ENDPUNKT}
    antwort = lp.post("/benachrichtigung/abo/loeschen", data=daten)
    assert antwort.status_code == 204
    assert anzahl_abos(db) == 0


def test_verwaltung_nur_auftraggeberin(lp):
    assert lp.get("/verwaltung/benachrichtigung").status_code == 403


def test_verwaltung_vorbelegt_mit_impuls(leitung, db, heute_ist):
    testdaten.lege_impuls_an(db, "Was hat dich heute überrascht?", "2026-11-23")
    heute_ist(date(2026, 11, 24))
    seite = leitung.get("/verwaltung/benachrichtigung").text
    assert "Was hat dich heute überrascht?</textarea>" in seite
    assert "0 Geräte" in seite


def test_verwaltung_leerer_text(leitung, monkeypatch):
    aufrufe = []
    monkeypatch.setattr("app.routen.benachrichtigung.verschicke_an_alle", aufrufe.append)
    daten = {"csrf": csrf_von(leitung, "/verwaltung/benachrichtigung"), "text": "  "}
    antwort = leitung.post("/verwaltung/benachrichtigung", data=daten)
    assert antwort.status_code == 400
    assert "Bitte einen Text eingeben." in antwort.text
    assert aufrufe == []


def test_verwaltung_zu_langer_text(leitung, monkeypatch):
    aufrufe = []
    monkeypatch.setattr("app.routen.benachrichtigung.verschicke_an_alle", aufrufe.append)
    daten = {"csrf": csrf_von(leitung, "/verwaltung/benachrichtigung"), "text": "x" * 501}
    antwort = leitung.post("/verwaltung/benachrichtigung", data=daten)
    assert antwort.status_code == 400
    assert aufrufe == []


def test_verwaltung_senden(leitung, monkeypatch):
    gesendet = []

    def ersatz(db, vapid, titel, text):
        gesendet.append((titel, text))
        return Ergebnis(gesendet=2, entfernt=1, nicht_erreicht=1)

    monkeypatch.setattr("app.routen.benachrichtigung.verschicke_an_alle", ersatz)
    daten = {"csrf": csrf_von(leitung, "/verwaltung/benachrichtigung"), "text": " Hallo "}
    antwort = leitung.post("/verwaltung/benachrichtigung", data=daten)
    assert antwort.status_code == 303
    assert gesendet == [("Reflexionsinstrument", "Hallo")]
    seite = leitung.get(antwort.headers["location"]).text
    assert "Gesendet an 2 Geräte." in seite
    assert "1 Gerät war nicht mehr erreichbar und ist entfernt." in seite
    assert "1 Gerät hat nicht geantwortet." in seite


def test_verwaltung_ergebnis_aus_adresse_nur_zahlen(leitung):
    seite = leitung.get("/verwaltung/benachrichtigung?gesendet=<b>x</b>").text
    assert "<b>x</b>" not in seite
    assert "Gesendet an" not in seite


def test_alle_abos_bleiben_beim_anzeigen(leitung, db):
    leitung.get("/verwaltung/benachrichtigung")
    assert alle_abos(db) == []


def test_nach_dem_senden_feld_leer(leitung, db, heute_ist):
    testdaten.lege_impuls_an(db, "Was hat dich heute überrascht?", "2026-11-23")
    heute_ist(date(2026, 11, 24))
    seite = leitung.get("/verwaltung/benachrichtigung?gesendet=1&entfernt=0&nicht=0").text
    assert "Gesendet an 1 Gerät." in seite
    assert "Was hat dich heute überrascht?" not in seite
