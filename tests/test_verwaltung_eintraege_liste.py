import re
from datetime import date

import testdaten
from auswertung_daten import setze_projektstart, setze_zeit
from conftest import als_leitung

PFAD = "/verwaltung/eintraege"
MONTAG = "2026-11-30T17:40:00Z"


def _frisch(db, heute_ist, start=True):
    heute_ist(date(2026, 12, 2))
    if start:
        setze_projektstart(db, "2026-11-23")


def _liste(client, auftraggeberin, pfad=PFAD):
    text = als_leitung(client, auftraggeberin).get(pfad).text
    return text[text.index('id="eintraege"') :]


def test_runde_eine_karte(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    _, (frage_a, frage_b) = testdaten.lege_runde_an(
        db,
        titel="Runde Eins",
        fragen=(("freitext", "Frage A"), ("skala", "Frage B")),
    )
    skala = testdaten.lege_antwort_an(db, frage_b, lehrperson["id"], text=None, skalawert=4)
    frei = testdaten.lege_antwort_an(db, frage_a, lehrperson["id"], text="Text A")
    setze_zeit(db, "antworten", skala, MONTAG)
    setze_zeit(db, "antworten", frei, MONTAG)

    liste = _liste(client, auftraggeberin)

    assert liste.count('class="karte karte--eintrag"') == 1
    assert "Runde Eins" in liste
    assert "2 von 2 Fragen beantwortet" in liste
    stellen = [liste.index(s) for s in ("Frage A", "Text A", "Frage B", "4 von 5")]
    assert stellen == sorted(stellen)


def test_kopfzeile(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    _, (frage_a, frage_b) = testdaten.lege_runde_an(
        db, fragen=(("freitext", "Frage A"), ("freitext", "Frage B"))
    )
    erste = testdaten.lege_antwort_an(db, frage_a, lehrperson["id"])
    zweite = testdaten.lege_antwort_an(db, frage_b, lehrperson["id"])
    setze_zeit(db, "antworten", erste, MONTAG)
    setze_zeit(db, "antworten", zweite, "2026-12-01T06:15:00Z")

    liste = _liste(client, auftraggeberin)

    assert "Anna Beispiel · Woche 2 · Mo 30.11.2026, 18:40" in liste
    assert "zuletzt gespeichert Di 01.12.2026, 07:15" in liste
    assert "geändert" not in liste


def test_kopfzeile_tagebuch(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    geaendert = testdaten.lege_eintrag_an(db, lehrperson["id"], text="Eins")
    gleich = testdaten.lege_eintrag_an(db, lehrperson["id"], text="Zwei")
    setze_zeit(db, "tagebucheintraege", geaendert, MONTAG, "2026-12-01T06:15:00Z")
    setze_zeit(db, "tagebucheintraege", gleich, "2026-11-24T08:00:00Z")

    liste = _liste(client, auftraggeberin)

    assert liste.count("geändert") == 1
    assert "· geändert Di 01.12.2026, 07:15" in liste
    assert "zuletzt gespeichert" not in liste


def test_ohne_woche(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist, start=False)
    eintrag = testdaten.lege_eintrag_an(db, lehrperson["id"])
    setze_zeit(db, "tagebucheintraege", eintrag, MONTAG)

    liste = _liste(client, auftraggeberin)

    assert "Anna Beispiel · Mo 30.11.2026, 18:40" in liste
    assert "Woche" not in liste


def test_tagebuch_arten(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    anna = lehrperson["id"]
    leitfrage = testdaten.lege_leitfrage_an(db, "Was war heute wichtig?")
    impuls = testdaten.lege_impuls_an(db, "Alter Impulstext")
    for n, eintrag in enumerate(
        (
            testdaten.lege_eintrag_an(db, anna, text="Frei geschrieben"),
            testdaten.lege_eintrag_an(db, anna, art="leitfragen", leitfrage_id=leitfrage),
            testdaten.lege_eintrag_an(db, anna, art="impuls", impuls_id=impuls),
        ),
        start=1,
    ):
        setze_zeit(db, "tagebucheintraege", eintrag, f"2026-11-2{n}T08:00:00Z")
    db.execute("UPDATE impulse SET text = 'Neu'")

    liste = _liste(client, auftraggeberin)

    assert "Freier Eintrag" in liste
    assert "Zur Leitfrage" in liste
    assert "Was war heute wichtig?" in liste
    assert "Zum Impuls" in liste
    assert "Alter Impulstext" in liste
    assert "Neu" not in liste
    assert '<span class="marke">Impuls</span>' in liste
    assert '<span class="marke">Tagebuch</span>' in liste


def test_aufnahme(client, auftraggeberin, lehrperson, db, heute_ist, einstellungen):
    _frisch(db, heute_ist)
    anna = lehrperson["id"]
    aufnahme = testdaten.lege_aufnahme_an(db, anna, einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_eintrag_an(db, anna, art="aufnahme", text=None, aufnahme_id=aufnahme)

    liste = _liste(client, auftraggeberin)

    assert "Gesprochener Eintrag" in liste
    assert "<audio" in liste
    assert 'preload="none"' in liste
    assert f'src="/verwaltung/aufnahmen/{aufnahme}"' in liste
    assert "5 Sek." in liste
    assert "antwort__text" not in liste


def test_aufnahme_in_runde(client, auftraggeberin, lehrperson, db, heute_ist, einstellungen):
    _frisch(db, heute_ist)
    _, (frage,) = testdaten.lege_runde_an(db, fragen=(("freitext", "Frage A"),))
    aufnahme = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_antwort_an(db, frage, lehrperson["id"], text=None, aufnahme_id=aufnahme)

    liste = _liste(client, auftraggeberin)

    assert "<audio" in liste
    assert "antwort__text" not in liste


def test_escapt_unformatiert(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    testdaten.lege_eintrag_an(db, lehrperson["id"], text="<script>x</script> **fett**\nZeile 2")

    liste = _liste(client, auftraggeberin)

    assert "&lt;script&gt;" in liste
    assert "<script" not in liste
    assert "**fett**" in liste
    assert "<strong>fett" not in liste
    assert re.search(r'class="antwort__text">[^<]*\nZeile 2', liste)


def test_nicht_freigeschaltete_runde(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    runde, (frage,) = testdaten.lege_runde_an(db, fragen=(("freitext", "Frage A"),))
    testdaten.lege_antwort_an(db, frage, lehrperson["id"], text="Versteckte Antwort")
    db.execute("UPDATE runden SET freischaltdatum = '2026-12-31' WHERE id = ?", (runde,))

    assert "Versteckte Antwort" in _liste(client, auftraggeberin)


def test_filter_liste(client, auftraggeberin, lehrperson, zweite_lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    anna = lehrperson["id"]
    testdaten.lege_eintrag_an(db, anna, text="TextAnna")
    testdaten.lege_eintrag_an(db, zweite_lehrperson["id"], text="TextBen")

    als_leitung(client, auftraggeberin)
    gefiltert = client.get(f"{PFAD}?lehrperson={anna}").text
    alle = client.get(PFAD).text

    assert "TextAnna" in gefiltert
    assert "TextBen" not in gefiltert
    assert "Anna Beispiel ·" not in gefiltert
    assert "TextAnna" in alle and "TextBen" in alle
    assert "Anna Beispiel ·" in alle


def test_reihenfolge(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)
    for text, zeit in (
        ("Mittlerer", "2026-11-30T08:00:00Z"),
        ("Aeltester", "2026-11-24T08:00:00Z"),
        ("Neuester", "2026-12-01T08:00:00Z"),
    ):
        eintrag = testdaten.lege_eintrag_an(db, lehrperson["id"], text=text)
        setze_zeit(db, "tagebucheintraege", eintrag, zeit)

    liste = _liste(client, auftraggeberin)

    stellen = [liste.index(t) for t in ("Neuester", "Mittlerer", "Aeltester")]
    assert stellen == sorted(stellen)


def test_leer(client, auftraggeberin, lehrperson, db, heute_ist):
    _frisch(db, heute_ist)

    assert "Noch keine Einträge." in _liste(client, auftraggeberin)
