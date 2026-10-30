from datetime import date

import testdaten
from auswertung_daten import setze_zeit, zeile

from app.auswertung import (
    Exportstand,
    Karte,
    exportstand,
    groesse_text,
    karten,
    personenkarten,
)
from app.eintraege import alle_zeilen, gruppiere

START = date(2026, 11, 23)


def _runde_mit_antworten(db, konto_id, datum, anzahl_fragen, beantwortet):
    fragen = tuple(("freitext", f"Frage {n}") for n in range(1, anzahl_fragen + 1))
    _, frage_ids = testdaten.lege_runde_an(db, freischaltdatum=datum, fragen=fragen)
    for frage_id in frage_ids[:beantwortet]:
        testdaten.lege_antwort_an(db, frage_id, konto_id)


def test_personenkarten_runden(db, lehrperson):
    _runde_mit_antworten(db, lehrperson["id"], "2026-11-23", 2, 2)
    _runde_mit_antworten(db, lehrperson["id"], "2026-11-23", 2, 1)
    _runde_mit_antworten(db, lehrperson["id"], "2026-11-23", 0, 0)
    _runde_mit_antworten(db, lehrperson["id"], "2026-12-07", 1, 1)  # noch nicht freigeschaltet

    karte = personenkarten(db, date(2026, 11, 24), alle_zeilen(db))[0]

    assert karte.runden == 2
    assert karte.beantwortet == 1
    assert karte.angefangen == 1


def test_personenkarten_keine_runde_offen(db, lehrperson):
    _runde_mit_antworten(db, lehrperson["id"], "2026-11-23", 0, 0)

    karte = personenkarten(db, date(2026, 11, 24), alle_zeilen(db))[0]

    assert karte.runden == 0
    assert karte.beantwortet == 0
    assert karte.angefangen == 0


def test_personenkarten_tagebuch_und_zuletzt(db, lehrperson, zweite_lehrperson, einstellungen):
    anna = lehrperson["id"]
    impuls = testdaten.lege_impuls_an(db)
    aufnahme = testdaten.lege_aufnahme_an(db, anna, einstellungen.aufnahmen_verzeichnis)
    frei = testdaten.lege_eintrag_an(db, anna)
    mit_impuls = testdaten.lege_eintrag_an(db, anna, art="impuls", impuls_id=impuls)
    gesprochen = testdaten.lege_eintrag_an(
        db, anna, art="aufnahme", text=None, aufnahme_id=aufnahme
    )
    for eintrag_id in (frei, mit_impuls):
        setze_zeit(db, "tagebucheintraege", eintrag_id, "2026-11-23T08:00:00Z")
    # 23:30 UTC ist in Zuerich schon der 25.11.
    setze_zeit(db, "tagebucheintraege", gesprochen, "2026-11-23T08:00:00Z", "2026-11-24T23:30:00Z")

    karten_ = personenkarten(db, date(2026, 11, 30), alle_zeilen(db))

    assert [k.anzeigename for k in karten_] == ["Anna Beispiel", "Ben Beispiel"]
    assert karten_[0].tagebucheintraege == 3
    assert karten_[0].zuletzt == date(2026, 11, 25)
    assert karten_[1].tagebucheintraege == 0
    assert karten_[1].zuletzt is None


def test_karten_woche():
    eintraege = gruppiere(
        [
            zeile(id=1, erstellt="2026-11-24T08:00:00Z", geaendert="2026-11-24T08:00:00Z"),
            zeile(
                id=2,
                frage_id=2,
                erstellt="2026-12-01T08:00:00Z",
                geaendert="2026-12-01T08:00:00Z",
                runde_id=2,
            ),
        ]
    )

    mit_start = karten(eintraege, START)
    assert sorted(k.woche for k in mit_start) == [1, 2]
    assert all(isinstance(k, Karte) for k in mit_start)
    assert {k.woche for k in karten(eintraege, None)} == {None}


def test_exportstand(tmp_path):
    (tmp_path / ("a" * 32 + ".webm")).write_bytes(bytes(1500))
    zeilen = [
        zeile(id=1),
        zeile(id=2, aufnahme_id=1, aufnahme_dateiname="a" * 32 + ".webm"),
        zeile(id=3, aufnahme_id=2, aufnahme_dateiname="b" * 32 + ".webm"),  # Datei fehlt
    ]
    assert exportstand(zeilen, tmp_path) == Exportstand(3, 2, 1500)

    ohne_muster = [zeile(id=4, aufnahme_id=3, aufnahme_dateiname="../x.webm")]
    assert exportstand(ohne_muster, tmp_path) == Exportstand(1, 1, 0)


def test_groesse_text():
    assert groesse_text(0) == "weniger als 1 MB"
    assert groesse_text(999_999) == "weniger als 1 MB"
    assert groesse_text(1_000_000) == "etwa 1 MB"
    assert groesse_text(18_400_000) == "etwa 18 MB"
