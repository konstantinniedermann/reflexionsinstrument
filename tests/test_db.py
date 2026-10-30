import sqlite3

import pytest

from app.db import migriere, verbinde


@pytest.fixture
def conn(tmp_path):
    c = verbinde(tmp_path / "t.db")
    yield c
    c.close()


@pytest.fixture
def db(conn):
    migriere(conn)
    return conn


def _konto(db, name="anna", rolle="lehrperson"):
    return db.execute(
        "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle)"
        " VALUES (?, ?, 'x', ?)",
        (name, name, rolle),
    ).lastrowid


def _runde_frage(db):
    runde = db.execute(
        "INSERT INTO runden (titel, freischaltdatum, reihenfolge) VALUES ('R', '2026-01-01', 1)"
    ).lastrowid
    frage = db.execute(
        "INSERT INTO fragen (runde_id, typ, text, reihenfolge) VALUES (?, 'freitext', 'F', 1)",
        (runde,),
    ).lastrowid
    return runde, frage


def _aufnahme(db, konto):
    return db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes)"
        " VALUES (?, 'a.webm', 'audio/webm', 10)",
        (konto,),
    ).lastrowid


def test_migration_legt_alle_tabellen_an(conn):
    assert migriere(conn) == 1
    namen = {
        r["name"]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert namen == {
        "konten",
        "einstellungen",
        "texte",
        "info_abschnitte",
        "runden",
        "fragen",
        "leitfragen",
        "impulse",
        "aufnahmen",
        "antworten",
        "tagebucheintraege",
    }
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1


def test_migration_ist_idempotent(conn):
    assert migriere(conn) == 1
    assert migriere(conn) == 1


def test_pragmas_aktiv(conn):
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_konto_loeschen_entfernt_eintraege(db):
    konto = _konto(db)
    _, frage = _runde_frage(db)
    aufnahme = _aufnahme(db, konto)
    db.execute(
        "INSERT INTO antworten (frage_id, konto_id, text) VALUES (?, ?, 'a')",
        (frage, konto),
    )
    db.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text) VALUES (?, 'frei', 't')",
        (konto,),
    )
    db.execute("DELETE FROM konten WHERE id = ?", (konto,))
    for tabelle in ("antworten", "tagebucheintraege", "aufnahmen"):
        assert db.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0] == 0
    assert aufnahme


def test_frage_mit_antwort_nicht_loeschbar(db):
    konto = _konto(db)
    _, frage = _runde_frage(db)
    db.execute(
        "INSERT INTO antworten (frage_id, konto_id, text) VALUES (?, ?, 'a')",
        (frage, konto),
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM fragen WHERE id = ?", (frage,))


def test_runde_mit_beantworteter_frage_nicht_loeschbar(db):
    konto = _konto(db)
    runde, frage = _runde_frage(db)
    db.execute(
        "INSERT INTO antworten (frage_id, konto_id, text) VALUES (?, ?, 'a')",
        (frage, konto),
    )
    with pytest.raises(sqlite3.IntegrityError):
        db.execute("DELETE FROM runden WHERE id = ?", (runde,))
    db.execute("DELETE FROM antworten")
    db.execute("DELETE FROM runden WHERE id = ?", (runde,))
    assert db.execute("SELECT COUNT(*) FROM fragen").fetchone()[0] == 0


def test_runde_ohne_antworten_loeschbar(db):
    runde, _ = _runde_frage(db)
    db.execute("DELETE FROM runden WHERE id = ?", (runde,))
    assert db.execute("SELECT COUNT(*) FROM fragen").fetchone()[0] == 0


def test_impuls_loeschen_behaelt_eintrag(db):
    konto = _konto(db)
    impuls = db.execute(
        "INSERT INTO impulse (text, sichtbar_ab) VALUES ('Platzhalter-Impuls', '2026-01-01')"
    ).lastrowid
    db.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text, impuls_id, impuls_text)"
        " VALUES (?, 'impuls', 't', ?, 'Platzhalter-Impuls')",
        (konto, impuls),
    )
    db.execute("DELETE FROM impulse WHERE id = ?", (impuls,))
    zeile = db.execute("SELECT impuls_id, impuls_text FROM tagebucheintraege").fetchone()
    assert zeile["impuls_id"] is None
    assert zeile["impuls_text"] == "Platzhalter-Impuls"


def test_benutzername_eindeutig_ohne_gross_klein(db):
    _konto(db, "Anna")
    with pytest.raises(sqlite3.IntegrityError):
        _konto(db, "anna")


def test_ungueltige_rolle_abgelehnt(db):
    with pytest.raises(sqlite3.IntegrityError):
        _konto(db, "gast1", rolle="gast")


def test_fehlerhafte_migration_rollt_zurueck(conn, tmp_path):
    verzeichnis = tmp_path / "mig"
    verzeichnis.mkdir()
    (verzeichnis / "001_ok.sql").write_text("CREATE TABLE a (x INTEGER);")
    (verzeichnis / "002_kaputt.sql").write_text("CREATE TABLE b (x INTEGER); SELEKT;")
    with pytest.raises(sqlite3.Error):
        migriere(conn, verzeichnis)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    tabellen = {
        r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "a" in tabellen
    assert "b" not in tabellen
