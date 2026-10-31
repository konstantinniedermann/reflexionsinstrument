import re
from datetime import date
from pathlib import Path

import pytest
import testdaten
from auswertung_daten import setze_projektstart, setze_zeit
from conftest import als_lehrperson, als_leitung

PFAD = "/verwaltung/eintraege"
TAG = "2026-11-23T08:00:00Z"


def _frisch(db, heute_ist):
    heute_ist(date(2026, 11, 24))
    setze_projektstart(db, "2026-11-23")


def _runde(db, konto_id, anzahl_fragen, beantwortet):
    fragen = tuple(("freitext", f"Frage {n}") for n in range(1, anzahl_fragen + 1))
    _, frage_ids = testdaten.lege_runde_an(db, freischaltdatum="2026-11-23", fragen=fragen)
    for frage_id in frage_ids[:beantwortet]:
        antwort_id = testdaten.lege_antwort_an(db, frage_id, konto_id)
        setze_zeit(db, "antworten", antwort_id, TAG)


def _anna_mit_daten(db, anna, einstellungen):
    _runde(db, anna, 2, 2)
    _runde(db, anna, 2, 1)
    impuls = testdaten.lege_impuls_an(db)
    aufnahme = testdaten.lege_aufnahme_an(db, anna, einstellungen.aufnahmen_verzeichnis)
    frei = testdaten.lege_eintrag_an(db, anna)
    mit_impuls = testdaten.lege_eintrag_an(db, anna, art="impuls", impuls_id=impuls)
    gesprochen = testdaten.lege_eintrag_an(
        db, anna, art="aufnahme", text=None, aufnahme_id=aufnahme
    )
    setze_zeit(db, "tagebucheintraege", frei, TAG)
    setze_zeit(db, "tagebucheintraege", mit_impuls, TAG)
    setze_zeit(db, "tagebucheintraege", gesprochen, TAG, "2026-11-24T18:00:00Z")


def test_uebersicht_personen(
    client, auftraggeberin, lehrperson, zweite_lehrperson, db, heute_ist, einstellungen
):
    _frisch(db, heute_ist)
    _runde(db, zweite_lehrperson["id"], 0, 0)  # Runde ohne Fragen zaehlt nicht
    _anna_mit_daten(db, lehrperson["id"], einstellungen)

    antwort = als_leitung(client, auftraggeberin).get(PFAD)

    assert antwort.status_code == 200
    text = antwort.text
    assert "Woche 1" in text
    assert "<h1>Einträge</h1>" in text
    assert "Runden 1 von 2" in text
    assert "1 angefangen" in text
    assert "3 Tagebucheinträge" in text
    assert "zuletzt Di 24.11." in text
    assert "Runden 0 von 2" in text
    assert "noch nichts" in text
    assert f"lehrperson={lehrperson['id']}#eintraege" in text


def test_uebersicht_einzahl(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    eintrag = testdaten.lege_eintrag_an(db, lehrperson["id"])
    setze_zeit(db, "tagebucheintraege", eintrag, TAG)

    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert "1 Tagebucheintrag<" in text


def test_uebersicht_ohne_runde(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)

    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert "Noch keine Runde offen" in text


def test_uebersicht_ohne_zugaenge(client, auftraggeberin):
    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert "Noch keine Zugänge." in text
    assert 'href="/verwaltung/zugaenge"' in text
    assert "Jetzt: 0 Zeilen, keine Aufnahmen." in text
    assert "/verwaltung/eintraege/tabelle.csv" in text
    assert "/verwaltung/eintraege/gesamtexport.zip" in text
    assert 'class="chips"' not in text
    assert '<p class="ueberzeile">' not in text


def test_export_karte(client, auftraggeberin, lehrperson, db, heute_ist, einstellungen):
    _frisch(db, heute_ist)
    _, frage_ids = testdaten.lege_runde_an(
        db, freischaltdatum="2026-11-23", fragen=(("freitext", "A"), ("freitext", "B"))
    )
    aufnahme = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_antwort_an(db, frage_ids[0], lehrperson["id"])
    testdaten.lege_antwort_an(db, frage_ids[1], lehrperson["id"], text=None, aufnahme_id=aufnahme)

    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert 'id="export"' in text
    assert "Jetzt: 2 Zeilen, 1 Aufnahme (weniger als 1 MB)." in text
    assert "Tabelle herunterladen (Excel)" in text
    assert "Gesamtexport herunterladen (ZIP)" in text
    assert "nicht über private Cloud-Dienste teilen" in text
    assert "Die Links in der Tabelle öffnen die Aufnahme, wenn du angemeldet bist." in text


def test_filter(client, auftraggeberin, lehrperson, zweite_lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    anna = lehrperson["id"]
    als_leitung(client, auftraggeberin)

    gefiltert = client.get(f"{PFAD}?lehrperson={anna}").text
    aktiv = re.findall(r'<a[^>]*class="[^"]*ist-aktiv[^"]*"[^>]*>', gefiltert)
    assert len(aktiv) == 2  # Personen-Karte und Chip
    assert all(f"lehrperson={anna}#eintraege" in a and 'aria-current="page"' in a for a in aktiv)
    assert "Einträge von Anna Beispiel" in gefiltert

    alle = client.get(PFAD).text
    aktiv = re.findall(r'<a[^>]*class="[^"]*ist-aktiv[^"]*"[^>]*>', alle)
    assert len(aktiv) == 1
    assert "Alle" in re.search(r"<a[^>]*ist-aktiv[^>]*>(.*?)</a>", alle, re.DOTALL).group(1)
    assert 'href="/verwaltung/eintraege#eintraege"' in aktiv[0]


@pytest.mark.parametrize(
    "wert", ["abc", "0", "-1", "99999999999999999999", "", "999", "AUFTRAGGEBERIN"]
)
def test_filter_404(client, auftraggeberin, lehrperson, wert):
    if wert == "AUFTRAGGEBERIN":
        wert = str(auftraggeberin["id"])

    antwort = als_leitung(client, auftraggeberin).get(f"{PFAD}?lehrperson={wert}")

    assert antwort.status_code == 404
    assert "Nicht gefunden" in antwort.text


def test_uebersicht_escapt_namen(client, auftraggeberin, lehrperson, db):
    db.execute("UPDATE konten SET anzeigename = '<b>X</b>' WHERE id = ?", (lehrperson["id"],))

    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert "&lt;b&gt;X&lt;/b&gt;" in text
    assert "<b>X" not in text


def test_zugriff(client, lehrperson):
    antwort = client.get(PFAD)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"

    assert als_lehrperson(client, lehrperson).get(PFAD).status_code == 403


def test_verwaltung_links(client, auftraggeberin):
    text = als_leitung(client, auftraggeberin).get("/verwaltung/inhalte").text

    assert text.count('href="/verwaltung/eintraege"') == 1  # Navigation
    assert "Vorschau" in text

    vorlagen = Path(__file__).parent.parent / "app" / "templates" / "verwaltung"
    quelltext = (vorlagen / "rahmen.html").read_text(encoding="utf-8")
    reihenfolge = [quelltext.index(m) for m in ("{# #18:", "{# Trennzeile", "{# #19:")]
    assert reihenfolge == sorted(reihenfolge)


def test_kein_inline(client, auftraggeberin, lehrperson, db, heute_ist, einstellungen):
    _frisch(db, heute_ist)
    _anna_mit_daten(db, lehrperson["id"], einstellungen)

    text = als_leitung(client, auftraggeberin).get(PFAD).text

    assert "style=" not in text
    assert "<script" not in text
    assert not re.search(r"<[^>]* on[a-z]+=", text)
