import csv
import io
import zipfile
from datetime import date

import testdaten
from auswertung_daten import setze_projektstart, setze_zeit
from conftest import als_lehrperson, als_leitung

TABELLE = "/verwaltung/eintraege/tabelle.csv"
EXPORT = "/verwaltung/eintraege/gesamtexport.zip"
ZEIT = "2026-11-30T17:40:00Z"


def _daten(db, einstellungen, konto_id):
    """Runde mit zwei Antworten (eine mit Aufnahme), zwei Tagebucheintraege (einer mit Aufnahme)."""
    verzeichnis = einstellungen.aufnahmen_verzeichnis
    setze_projektstart(db, "2026-11-23")
    _, (frage_a, frage_b) = testdaten.lege_runde_an(
        db, fragen=(("freitext", "A"), ("freitext", "B"))
    )
    a1 = testdaten.lege_aufnahme_an(db, konto_id, verzeichnis)
    a2 = testdaten.lege_aufnahme_an(db, konto_id, verzeichnis)
    antwort_1 = testdaten.lege_antwort_an(db, frage_a, konto_id, aufnahme_id=a1)
    antwort_2 = testdaten.lege_antwort_an(db, frage_b, konto_id)
    frei = testdaten.lege_eintrag_an(db, konto_id, "frei", "Zeile 1\r\nZeile 2 äöü")
    stimme = testdaten.lege_eintrag_an(db, konto_id, "aufnahme", None, aufnahme_id=a2)
    setze_zeit(db, "antworten", antwort_1, ZEIT)
    setze_zeit(db, "antworten", antwort_2, "2026-11-30T17:41:00Z")
    setze_zeit(db, "tagebucheintraege", frei, "2026-12-01T08:00:00Z")
    setze_zeit(db, "tagebucheintraege", stimme, "2026-12-01T09:00:00Z")
    return a1, a2


def _dateiname(db, aufnahme_id):
    return db.execute("SELECT dateiname FROM aufnahmen WHERE id = ?", (aufnahme_id,)).fetchone()[0]


def _zeilen(text):
    return list(csv.DictReader(io.StringIO(text.lstrip("﻿"), newline=""), delimiter=";"))


def _zip(antwort):
    return zipfile.ZipFile(io.BytesIO(antwort.content))


def _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist):
    heute_ist(date(2026, 12, 18))
    ids = _daten(db, einstellungen, lehrperson["id"])
    als_leitung(client, auftraggeberin)
    return ids


def test_tabelle_kopfzeilen(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist):
    _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist)
    antwort = client.get(TABELLE)
    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "text/csv; charset=utf-8"
    assert (
        antwort.headers["content-disposition"]
        == 'attachment; filename="reflexion-tabelle-2026-12-18.csv"'
    )
    assert antwort.headers["cache-control"] == "no-store"


def test_tabelle_inhalt(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist):
    a1, a2 = _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist)
    zeilen = _zeilen(client.get(TABELLE).content.decode("utf-8"))
    assert len(zeilen) == 4
    mit = sorted(z["Aufnahme"] for z in zeilen if z["Aufnahme"])
    assert mit == sorted(f"http://testserver/verwaltung/aufnahmen/{i}" for i in (a1, a2))
    assert sum(1 for z in zeilen if not z["Aufnahme"]) == 2
    assert "Zeile 1\nZeile 2 äöü" in [z["Antwort"] for z in zeilen]


def test_gesamtexport_kopfzeilen(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist):
    _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist)
    antwort = client.get(EXPORT)
    assert antwort.status_code == 200
    assert antwort.headers["content-type"] == "application/zip"
    assert "reflexion-gesamtexport-2026-12-18.zip" in antwort.headers["content-disposition"]
    assert antwort.headers["cache-control"] == "no-store"


def test_gesamtexport_inhalt(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist):
    ids = _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist)
    zf = _zip(client.get(EXPORT))
    assert zf.testzip() is None
    namen = zf.namelist()
    assert namen[-1] == "eintraege.csv"
    dateien = [n for n in namen if n.startswith("aufnahmen/")]
    assert len(dateien) == 2
    for n in dateien:
        assert zf.read(n).startswith(testdaten.WEBM_ANFANG)
    originale = sorted(
        (einstellungen.aufnahmen_verzeichnis / _dateiname(db, i)).read_bytes() for i in ids
    )
    assert sorted(zf.read(n) for n in dateien) == originale
    zeilen = _zeilen(zf.read("eintraege.csv").decode("utf-8"))
    assert len(zeilen) == 4
    assert sorted(z["Aufnahme"] for z in zeilen if z["Aufnahme"]) == sorted(dateien)


def test_gesamtexport_datei_geloescht(
    client, auftraggeberin, lehrperson, db, einstellungen, heute_ist
):
    a1, _ = _bereit(client, auftraggeberin, lehrperson, db, einstellungen, heute_ist)
    (einstellungen.aufnahmen_verzeichnis / _dateiname(db, a1)).unlink()
    antwort = client.get(EXPORT)
    assert antwort.status_code == 200
    zf = _zip(antwort)
    assert zf.testzip() is None
    assert len([n for n in zf.namelist() if n.startswith("aufnahmen/")]) == 1
    zeilen = _zeilen(zf.read("eintraege.csv").decode("utf-8"))
    assert [z["Aufnahme"] for z in zeilen].count("Datei fehlt") == 1


def test_downloads_ohne_eintraege(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    tabelle = client.get(TABELLE).content.decode("utf-8")
    assert tabelle.startswith("﻿")
    assert tabelle.count("\r\n") == 1 and tabelle.endswith("\r\n")
    assert _zip(client.get(EXPORT)).namelist() == ["eintraege.csv"]


def test_downloads_zugriff(client, lehrperson):
    for pfad in (TABELLE, EXPORT):
        antwort = client.get(pfad)
        assert antwort.status_code == 303
        assert antwort.headers["location"] == "/"
    als_lehrperson(client, lehrperson)
    for pfad in (TABELLE, EXPORT):
        assert client.get(pfad).status_code == 403
