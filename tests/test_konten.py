import re
import secrets

import pytest

from app.db import migriere, verbinde
from app.konten import (
    EingabeFehler,
    finde_hash,
    finde_konto,
    hash_passwort,
    lege_konto_an,
    lehrpersonen,
    loesche_konto,
    normalisiere_benutzername,
    passwort_stimmt,
    passwort_vorschlag,
    pruefe_neues_passwort,
    setze_passwort,
    zaehle_daten,
)


@pytest.fixture
def db(tmp_path):
    conn = verbinde(tmp_path / "test.db")
    migriere(conn)
    yield conn
    conn.close()


def test_konto_anlegen_normalisiert_benutzername(db):
    konto = lege_konto_an(db, "Anna", " Lp.Anna ", "geheim123")
    assert konto.benutzername == "lp.anna"
    assert konto.rolle == "lehrperson"
    assert normalisiere_benutzername("  AbC ") == "abc"


@pytest.mark.parametrize("name", ["ab", "anna maria", "anna_x", "a" * 41])
def test_benutzername_ungueltig(db, name):
    with pytest.raises(EingabeFehler) as fehler:
        lege_konto_an(db, "Anna", name, "geheim123")
    assert fehler.value.feld == "benutzername"


def test_benutzername_doppelt(db):
    lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    with pytest.raises(EingabeFehler) as fehler:
        lege_konto_an(db, "Anna 2", "LP.ANNA", "geheim123")
    assert fehler.value.feld == "benutzername"
    assert str(fehler.value) == "Diesen Benutzernamen gibt es schon."


def test_passwort_zu_kurz(db):
    with pytest.raises(EingabeFehler) as fehler:
        lege_konto_an(db, "Anna", "lp.anna", "1234567")
    assert fehler.value.feld == "passwort"


def test_passwort_zu_lang_in_bytes(db):
    with pytest.raises(EingabeFehler) as fehler:
        lege_konto_an(db, "Anna", "lp.anna", "ä" * 37)
    assert fehler.value.feld == "passwort"
    lege_konto_an(db, "Anna", "lp.anna", "ä" * 36)


@pytest.mark.parametrize("name", ["  ", "a" * 61])
def test_anzeigename_leer_oder_zu_lang(db, name):
    with pytest.raises(EingabeFehler) as fehler:
        lege_konto_an(db, name, "lp.anna", "geheim123")
    assert fehler.value.feld == "anzeigename"


def test_passwort_stimmt():
    h = hash_passwort("geheim123")
    assert passwort_stimmt("geheim123", h)
    assert not passwort_stimmt("falsch", h)
    assert not passwort_stimmt("x" * 100, h)
    assert not passwort_stimmt("geheim123", None)


def test_neues_konto_startet_mit_zufaelliger_version(db, tmp_path, monkeypatch):
    werte = iter([41, 99])
    monkeypatch.setattr(secrets, "randbelow", lambda _n: next(werte))
    erstes = lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    loesche_konto(db, erstes.id, tmp_path / "aufnahmen")
    zweites = lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    assert zweites.id == erstes.id
    assert erstes.sitzungsversion == 42
    assert zweites.sitzungsversion == 100


def test_setze_passwort_erhoeht_version_und_wechselt_hash(db):
    konto = lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    _, alter_hash = finde_hash(db, "lp.anna")
    setze_passwort(db, konto.id, "neues-passwort")
    neu, neuer_hash = finde_hash(db, " LP.Anna ")
    assert neu.sitzungsversion == konto.sitzungsversion + 1
    assert neuer_hash != alter_hash
    assert passwort_stimmt("neues-passwort", neuer_hash)
    with pytest.raises(EingabeFehler):
        setze_passwort(db, konto.id, "kurz")
    assert finde_hash(db, "unbekannt") is None
    assert finde_konto(db, konto.id).benutzername == "lp.anna"
    assert finde_konto(db, 9999) is None


def _daten_anlegen(db, konto_id, dateiname):
    db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes)"
        " VALUES (?, ?, 'audio/webm', 3)",
        (konto_id, dateiname),
    )
    db.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text) VALUES (?, 'frei', 'x')",
        (konto_id,),
    )


def test_loesche_konto_entfernt_dateien_und_zeilen(db, tmp_path):
    ordner = tmp_path / "aufnahmen"
    ordner.mkdir()
    aussen = tmp_path / "x"
    aussen.write_text("bleibt")
    a = lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    b = lege_konto_an(db, "Berta", "lp.berta", "geheim123")
    _daten_anlegen(db, a.id, "abc.webm")
    _daten_anlegen(db, a.id, "../x")
    _daten_anlegen(db, a.id, "fehlt.webm")
    _daten_anlegen(db, b.id, "def.webm")
    (ordner / "abc.webm").write_bytes(b"123")
    (ordner / "x").write_bytes(b"123")
    (ordner / "def.webm").write_bytes(b"123")

    loesche_konto(db, a.id, ordner)

    assert not (ordner / "abc.webm").exists()
    assert not (ordner / "x").exists()
    assert aussen.read_text() == "bleibt"
    assert (ordner / "def.webm").exists()
    assert finde_konto(db, a.id) is None
    assert db.execute("SELECT COUNT(*) FROM aufnahmen").fetchone()[0] == 1
    assert db.execute("SELECT COUNT(*) FROM tagebucheintraege").fetchone()[0] == 1


def test_zaehle_daten(db):
    a = lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    assert zaehle_daten(db, a.id) == {"antworten": 0, "tagebucheintraege": 0, "aufnahmen": 0}
    _daten_anlegen(db, a.id, "abc.webm")
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('R', '2026-01-01')")
    db.execute("INSERT INTO fragen (runde_id, typ, text) VALUES (1, 'freitext', 'F')")
    db.execute("INSERT INTO antworten (frage_id, konto_id, text) VALUES (1, ?, 't')", (a.id,))
    assert zaehle_daten(db, a.id) == {"antworten": 1, "tagebucheintraege": 1, "aufnahmen": 1}


def test_lehrpersonen_sortiert_ohne_auftraggeberin(db):
    lege_konto_an(db, "Berta", "lp.berta", "geheim123")
    lege_konto_an(db, "Anna", "lp.anna", "geheim123")
    lege_konto_an(db, "Leitung", "projektleitung", "geheim123", rolle="auftraggeberin")
    zeilen = lehrpersonen(db)
    assert [z["anzeigename"] for z in zeilen] == ["Anna", "Berta"]
    assert set(zeilen[0].keys()) == {"id", "anzeigename", "benutzername", "erstellt"}


def test_passwort_vorschlag_format():
    for _ in range(20):
        vorschlag = passwort_vorschlag()
        assert re.fullmatch(r"[a-z]{4}-[a-z]{4}-[a-z]{4}-\d{2}", vorschlag)
        pruefe_neues_passwort(vorschlag)
