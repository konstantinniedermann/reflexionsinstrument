import shutil
import sqlite3

import pytest
import testdaten

from app.db import MIGRATIONEN, migriere, verbinde


def test_version_spalte_indizes(db):
    assert db.execute("PRAGMA user_version").fetchone()[0] == 4
    spalten = [z[1] for z in db.execute("PRAGMA table_info(aufnahmen)")]
    assert "dauer_sekunden" in spalten
    indizes = {z[0] for z in db.execute("SELECT name FROM sqlite_master WHERE type = 'index'")}
    assert {"idx_antworten_aufnahme", "idx_tagebucheintraege_aufnahme", "idx_aufnahmen_konto"} <= (
        indizes
    )


def test_migration_erhaelt_daten(tmp_path):
    ordner = tmp_path / "alt"
    ordner.mkdir()
    shutil.copy(MIGRATIONEN / "001_grundschema.sql", ordner)
    conn = verbinde(tmp_path / "test.db")
    try:
        assert migriere(conn, ordner) == 1
        konto = conn.execute(
            "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle) "
            "VALUES ('A', 'a', 'x', 'lehrperson')"
        ).lastrowid
        conn.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('k', 'v')")
        conn.execute("INSERT INTO texte (schluessel, inhalt) VALUES ('t', 'i')")
        conn.execute("INSERT INTO info_abschnitte (titel, inhalt) VALUES ('T', 'I')")
        _, (fid, _) = testdaten.lege_runde_an(conn)
        lid = testdaten.lege_leitfrage_an(conn)
        iid = testdaten.lege_impuls_an(conn)
        aid = conn.execute(
            "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes) "
            "VALUES (?, 'x.webm', 'audio/webm', 4)",
            (konto,),
        ).lastrowid
        testdaten.lege_antwort_an(conn, fid, konto)
        testdaten.lege_eintrag_an(conn, konto, art="impuls", impuls_id=iid, aufnahme_id=aid)
        testdaten.lege_eintrag_an(conn, konto, art="leitfragen", leitfrage_id=lid)
        conn.commit()
        for tabelle, zeilen in testdaten.abzug(conn).items():
            assert zeilen, tabelle
        vorher = testdaten.abzug(conn)

        assert migriere(conn) == 4
        nachher = testdaten.abzug(conn)
        for tabelle in vorher:
            if tabelle != "aufnahmen":
                assert nachher[tabelle] == vorher[tabelle], tabelle
        alt = conn.execute(
            "SELECT id, konto_id, dateiname, mime_typ, groesse_bytes, erstellt FROM aufnahmen"
        ).fetchall()
        assert sorted(tuple(z) for z in alt) == vorher["aufnahmen"]
        assert conn.execute("SELECT dauer_sekunden FROM aufnahmen").fetchone()[0] is None
    finally:
        conn.close()


def _aufnahme(db, konto_id, name):
    return db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes) "
        "VALUES (?, ?, 'audio/webm', 4)",
        (konto_id, name),
    ).lastrowid


def test_aufnahme_nur_einmal(db, lehrperson, einstellungen):
    konto = lehrperson["id"]
    aid = _aufnahme(db, konto, "a.webm")
    testdaten.lege_eintrag_an(db, konto, art="aufnahme", text=None, aufnahme_id=aid)
    with pytest.raises(sqlite3.IntegrityError):
        testdaten.lege_eintrag_an(db, konto, art="aufnahme", text=None, aufnahme_id=aid)
    _, (f1, f2) = testdaten.lege_runde_an(db)
    bid = _aufnahme(db, konto, "b.webm")
    testdaten.lege_antwort_an(db, f1, konto, text=None, aufnahme_id=bid)
    with pytest.raises(sqlite3.IntegrityError):
        testdaten.lege_antwort_an(db, f2, konto, text=None, aufnahme_id=bid)


def test_dauer_nur_ganze_zahl(db, lehrperson, einstellungen):
    aid = _aufnahme(db, lehrperson["id"], "a.webm")
    for wert in ("'x'", "-1"):
        with pytest.raises(sqlite3.IntegrityError):
            db.execute(f"UPDATE aufnahmen SET dauer_sekunden = {wert}")
    db.execute("UPDATE aufnahmen SET dauer_sekunden = 0 WHERE id = ?", (aid,))
