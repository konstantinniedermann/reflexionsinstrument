"""Migration 006: die Zusatzinfo einer Runde wandert zu ihrer ersten Frage."""

import shutil

from app.db import MIGRATIONEN, migriere, verbinde


def _ordner(tmp_path, name, muster):
    ordner = tmp_path / name
    ordner.mkdir()
    for datei in MIGRATIONEN.glob(muster):
        shutil.copy(datei, ordner)
    return ordner


def _bis_005(tmp_path):
    conn = verbinde(tmp_path / "test.db")
    assert migriere(conn, _ordner(tmp_path, "alt", "00[1-5]_*.sql")) == 5
    return conn


def _bis_006(conn, tmp_path):
    """Nur bis 006: Migration 007 macht aus den Zusatzinfos eigene Bausteine."""
    return migriere(conn, _ordner(tmp_path, "bis6", "00[1-6]_*.sql"))


def _frage(conn, rid, text, reihenfolge):
    return conn.execute(
        "INSERT INTO fragen (runde_id, typ, text, reihenfolge) VALUES (?, 'freitext', ?, ?)",
        (rid, text, reihenfolge),
    ).lastrowid


def test_zusatzinfo_wandert_zur_ersten_frage(tmp_path):
    conn = _bis_005(tmp_path)
    try:
        a = conn.execute(
            "INSERT INTO runden (titel, freischaltdatum, zusatzinfo) "
            "VALUES ('A', '2026-11-23', 'Info A')"
        ).lastrowid
        zweite = _frage(conn, a, "Zweite", 2)
        erste = _frage(conn, a, "Erste", 1)
        b = conn.execute(
            "INSERT INTO runden (titel, freischaltdatum, zusatzinfo) "
            "VALUES ('B', '2026-11-30', 'Info B')"
        ).lastrowid
        c = conn.execute(
            "INSERT INTO runden (titel, freischaltdatum) VALUES ('C', '2026-12-07')"
        ).lastrowid
        ohne = _frage(conn, c, "Ohne", 1)
        conn.commit()

        assert _bis_006(conn, tmp_path) == 6
        info = dict(conn.execute("SELECT id, zusatzinfo FROM fragen").fetchall())
        assert info == {erste: "Info A", zweite: None, ohne: None}
        bei_runde = dict(conn.execute("SELECT id, zusatzinfo FROM runden").fetchall())
        assert bei_runde[a] is None
        assert bei_runde[b] == "Info B"

    finally:
        conn.close()
