from io import BytesIO

import pytest

from app import aufnahmen
from app.db import transaktion
from tests import testdaten

WEBM = b"\x1aE\xdf\xa3" + bytes(60)
JETZT = "2026-11-24T10:00:00Z"
ALT = "2026-11-01T00:00:00Z"


@pytest.fixture
def verzeichnis(einstellungen):
    return einstellungen.aufnahmen_verzeichnis


@pytest.fixture
def frage_id(db):
    _, fragen = testdaten.lege_runde_an(
        db, titel="Runde", freischaltdatum="2026-10-01", fragen=(("freitext", "Frage 1"),)
    )
    db.commit()
    return fragen[0]


def neue_datei(verzeichnis):
    return aufnahmen.schreibe_datei(BytesIO(WEBM), verzeichnis)


def mit_aufnahme(db, verzeichnis, frage_id, konto_id, text="Getippt"):
    datei = neue_datei(verzeichnis)
    with transaktion(db):
        aufnahme_id = aufnahmen.lege_aufnahme_an(db, konto_id, datei, 5)
        antwort_id = testdaten.lege_antwort_an(
            db, frage_id, konto_id, text=text, aufnahme_id=aufnahme_id
        )
    return antwort_id, aufnahme_id, datei


def antwort(db, frage_id, konto_id):
    return db.execute(
        "SELECT * FROM antworten WHERE frage_id = ? AND konto_id = ?", (frage_id, konto_id)
    ).fetchone()


def anzahl_aufnahmen(db, konto_id):
    return db.execute("SELECT COUNT(*) FROM aufnahmen WHERE konto_id = ?", (konto_id,)).fetchone()[
        0
    ]


def test_neue_antwort_nur_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    aufnahmen.haenge_an_antwort(db, kid, frage_id, neue_datei(verzeichnis), 7, verzeichnis, JETZT)
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] is None
    assert zeile["skalawert"] is None
    assert zeile["aufnahme_id"] is not None
    assert zeile["erstellt"] == zeile["geaendert"] == JETZT
    assert aufnahmen.aufnahme_der_antwort(db, kid, frage_id)["dauer_sekunden"] == 7


def test_textantwort_erhaelt_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    testdaten.lege_antwort_an(db, frage_id, kid, text="Getippt")
    db.execute("UPDATE antworten SET erstellt = ?, geaendert = ?", (ALT, ALT))
    db.commit()
    aufnahmen.haenge_an_antwort(
        db, kid, frage_id, neue_datei(verzeichnis), None, verzeichnis, JETZT
    )
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert zeile["geaendert"] == JETZT
    assert zeile["erstellt"] == ALT
    assert zeile["aufnahme_id"] is not None


def test_ersetzen_loescht_alte_datei(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    erste = neue_datei(verzeichnis)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, erste, 1, verzeichnis, JETZT)
    # Text setzen, damit er den Ersatz ueberlebt
    db.execute("UPDATE antworten SET text = 'Getippt' WHERE konto_id = ?", (kid,))
    db.commit()
    zweite = neue_datei(verzeichnis)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, zweite, 2, verzeichnis, JETZT)
    assert anzahl_aufnahmen(db, kid) == 1
    assert not (verzeichnis / erste.name).exists()
    assert (verzeichnis / zweite.name).exists()
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert aufnahmen.aufnahme_der_antwort(db, kid, frage_id)["dateiname"] == zweite.name


def test_loeschen_text_bleibt(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    *_, datei = mit_aufnahme(db, verzeichnis, frage_id, kid)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert zeile["aufnahme_id"] is None
    assert not (verzeichnis / datei.name).exists()
    assert anzahl_aufnahmen(db, kid) == 0


def test_loeschen_nur_aufnahme_loescht_zeile(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    _, _, datei = mit_aufnahme(db, verzeichnis, frage_id, kid, text=None)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    assert antwort(db, frage_id, kid) is None
    assert not (verzeichnis / datei.name).exists()


def test_loeschen_ohne_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    testdaten.lege_antwort_an(db, frage_id, kid, text="Nur Text")
    db.commit()
    vorher = testdaten.abzug(db)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is False
    assert testdaten.abzug(db) == vorher


def test_fremde_antwort_unberuehrt(db, verzeichnis, frage_id, lehrperson, zweite_lehrperson):
    kid, zid = lehrperson["id"], zweite_lehrperson["id"]
    mit_aufnahme(db, verzeichnis, frage_id, zid)
    dateien = sorted(p.name for p in verzeichnis.iterdir())
    fremd_vorher = antwort(db, frage_id, zid)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, neue_datei(verzeichnis), 3, verzeichnis, JETZT)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    assert tuple(antwort(db, frage_id, zid)) == tuple(fremd_vorher)
    assert anzahl_aufnahmen(db, zid) == 1
    assert all((verzeichnis / n).exists() for n in dateien)


def test_in_laufender_transaktion(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    datei = neue_datei(verzeichnis)
    with transaktion(db):
        with pytest.raises(RuntimeError):
            aufnahmen.haenge_an_antwort(db, kid, frage_id, datei, None, verzeichnis, JETZT)
        with pytest.raises(RuntimeError):
            aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT)


def test_datenbankfehler_alte_aufnahme_bleibt(db, verzeichnis, frage_id, lehrperson, monkeypatch):
    kid = lehrperson["id"]
    *_, alt = mit_aufnahme(db, verzeichnis, frage_id, kid)
    vorher = testdaten.abzug(db)

    def kaputt(*args, **kwargs):
        raise RuntimeError("Datenbankfehler")

    monkeypatch.setattr(aufnahmen, "lege_aufnahme_an", kaputt)
    neu = neue_datei(verzeichnis)
    with pytest.raises(RuntimeError, match="Datenbankfehler"):
        aufnahmen.haenge_an_antwort(db, kid, frage_id, neu, None, verzeichnis, JETZT)
    assert testdaten.abzug(db) == vorher
    assert (verzeichnis / alt.name).exists()
