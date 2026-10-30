from datetime import date

import testdaten

from app.sichtbar import (
    aktueller_impuls,
    naechste_freischaltung,
    sichtbare_runde,
    sichtbare_runden,
    sichtbarer_impuls,
)


def _drei_runden(db):
    return [
        testdaten.lege_runde_an(db, "A", "2026-11-23")[0],
        testdaten.lege_runde_an(db, "B", "2026-11-30")[0],
        testdaten.lege_runde_an(db, "C", "2026-11-23")[0],
    ]


def test_sichtbare_runden_grenze(db):
    a, b, c = _drei_runden(db)
    assert sichtbare_runden(db, date(2026, 11, 22)) == []
    zeilen = sichtbare_runden(db, date(2026, 11, 23))
    assert [z["id"] for z in zeilen] == [a, c]
    assert [z["id"] for z in sichtbare_runden(db, date(2026, 11, 30))] == [a, c, b]
    assert zeilen[0]["anzahl_fragen"] == 2


def test_naechste_freischaltung(db):
    assert naechste_freischaltung(db, date(2026, 11, 23)) is None
    _drei_runden(db)
    assert naechste_freischaltung(db, date(2026, 11, 23)) == date(2026, 11, 30)
    assert naechste_freischaltung(db, date(2026, 11, 30)) is None


def test_sichtbare_runde(db):
    a, b, _ = _drei_runden(db)
    assert sichtbare_runde(db, b, date(2026, 11, 23)) is None
    assert sichtbare_runde(db, 9999, date(2026, 11, 23)) is None
    assert sichtbare_runde(db, a, date(2026, 11, 23))["titel"] == "A"


def test_aktueller_impuls(db):
    a = testdaten.lege_impuls_an(db, "a", "2026-11-23")
    testdaten.lege_impuls_an(db, "b", "2026-11-30")
    c = testdaten.lege_impuls_an(db, "c", "2026-11-30")
    assert aktueller_impuls(db, date(2026, 11, 22)) is None
    assert aktueller_impuls(db, date(2026, 11, 29))["id"] == a
    assert aktueller_impuls(db, date(2026, 11, 30))["id"] == c
    assert aktueller_impuls(db, date(2026, 12, 31))["id"] == c


def test_sichtbarer_impuls(db):
    a = testdaten.lege_impuls_an(db, "a", "2026-11-23")
    testdaten.lege_impuls_an(db, "b", "2026-11-30")
    spaeter = testdaten.lege_impuls_an(db, "d", "2026-12-07")
    assert sichtbarer_impuls(db, a, date(2026, 11, 30))["id"] == a
    assert sichtbarer_impuls(db, spaeter, date(2026, 11, 30)) is None
