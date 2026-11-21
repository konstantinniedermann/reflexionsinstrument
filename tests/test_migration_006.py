"""Migration 006: die Zusatzinfo einer Runde wandert zu ihrer ersten Frage."""

import shutil

from app.db import MIGRATIONEN, migriere, verbinde
from app.inhalte import lege_frage_an, runde


def _bis_005(tmp_path):
    ordner = tmp_path / "alt"
    ordner.mkdir()
    for datei in MIGRATIONEN.glob("00[1-5]_*.sql"):
        shutil.copy(datei, ordner)
    conn = verbinde(tmp_path / "test.db")
    assert migriere(conn, ordner) == 5
    return conn


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

        assert migriere(conn) == 6
        info = dict(conn.execute("SELECT id, zusatzinfo FROM fragen").fetchall())
        assert info == {erste: "Info A", zweite: None, ohne: None}
        assert runde(conn, a)["zusatzinfo"] is None
        assert runde(conn, b)["zusatzinfo"] == "Info B"

        # Das Formular der ersten Frage schickt die vorbelegte Info mit.
        neu = lege_frage_an(conn, b, "freitext", "Neu", "", "", zusatzinfo="Info B")
        assert conn.execute("SELECT zusatzinfo FROM fragen WHERE id = ?", (neu,)).fetchone()[0] == (
            "Info B"
        )
        assert runde(conn, b)["zusatzinfo"] is None
    finally:
        conn.close()


def test_eigene_info_ersetzt_wartende(tmp_path):
    conn = _bis_005(tmp_path)
    try:
        b = conn.execute(
            "INSERT INTO runden (titel, freischaltdatum, zusatzinfo) "
            "VALUES ('B', '2026-11-30', 'Alt')"
        ).lastrowid
        conn.commit()
        migriere(conn)
        neu = lege_frage_an(conn, b, "freitext", "Neu", "", "", zusatzinfo="Eigene")
        zeile = conn.execute("SELECT zusatzinfo FROM fragen WHERE id = ?", (neu,)).fetchone()
        # Das Formular zeigt die wartende Info vorbelegt; wer sie ersetzt, tut das bewusst.
        assert zeile[0] == "Eigene"
        assert runde(conn, b)["zusatzinfo"] is None
    finally:
        conn.close()


def test_geleerte_wartende_info_ist_weg(tmp_path):
    conn = _bis_005(tmp_path)
    try:
        b = conn.execute(
            "INSERT INTO runden (titel, freischaltdatum, zusatzinfo) "
            "VALUES ('B', '2026-11-30', 'Alt')"
        ).lastrowid
        conn.commit()
        migriere(conn)
        neu = lege_frage_an(conn, b, "freitext", "Neu", "", "", zusatzinfo="   ")
        zeile = conn.execute("SELECT zusatzinfo FROM fragen WHERE id = ?", (neu,)).fetchone()
        assert zeile[0] is None
        assert runde(conn, b)["zusatzinfo"] is None
    finally:
        conn.close()
