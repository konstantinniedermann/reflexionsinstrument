"""Migration 007: Zusatzinfos werden eigene Bausteine im Ablauf der Runde."""

import shutil

from app.db import MIGRATIONEN, migriere, verbinde
from app.inhalte import ablauf


def _bis_006(tmp_path):
    ordner = tmp_path / "alt"
    ordner.mkdir()
    for datei in MIGRATIONEN.glob("00[1-6]_*.sql"):
        shutil.copy(datei, ordner)
    conn = verbinde(tmp_path / "test.db")
    assert migriere(conn, ordner) == 6
    return conn


def _frage(conn, rid, text, reihenfolge, info=None):
    return conn.execute(
        "INSERT INTO fragen (runde_id, typ, text, reihenfolge, zusatzinfo) "
        "VALUES (?, 'freitext', ?, ?, ?)",
        (rid, text, reihenfolge, info),
    ).lastrowid


def _runde(conn, titel, info=None):
    return conn.execute(
        "INSERT INTO runden (titel, freischaltdatum, zusatzinfo) VALUES (?, '2026-11-23', ?)",
        (titel, info),
    ).lastrowid


def _abfolge(conn, rid):
    return [
        ("F", b["frage"]["text"]) if b["art"] == "frage" else ("I", b["zusatzinfo"]["inhalt"])
        for b in ablauf(conn, rid)
    ]


def _spalten(conn, tabelle):
    return {z["name"] for z in conn.execute(f"PRAGMA table_info({tabelle})")}


def test_zusatzinfos_stehen_an_derselben_stelle(tmp_path):
    conn = _bis_006(tmp_path)
    try:
        a = _runde(conn, "A")
        # Reihenfolge absichtlich mit Lücke und vertauschten Ids
        _frage(conn, a, "F3", 7, "Info nach 3")
        _frage(conn, a, "F1", 1, "Info nach 1")
        _frage(conn, a, "F2", 4)
        b = _runde(conn, "B", "Wartend")
        c = _runde(conn, "C")
        _frage(conn, c, "Ohne", 1, "")
        conn.commit()

        assert migriere(conn) == 7
        assert _abfolge(conn, a) == [
            ("F", "F1"),
            ("I", "Info nach 1"),
            ("F", "F2"),
            ("F", "F3"),
            ("I", "Info nach 3"),
        ]
        assert _abfolge(conn, b) == [("I", "Wartend")]
        assert _abfolge(conn, c) == [("F", "Ohne")]
        assert "zusatzinfo" not in _spalten(conn, "fragen")
        assert "zusatzinfo" not in _spalten(conn, "runden")
    finally:
        conn.close()


def test_antworten_bleiben(tmp_path):
    conn = _bis_006(tmp_path)
    try:
        a = _runde(conn, "A")
        f = _frage(conn, a, "F1", 1, "Info")
        k = conn.execute(
            "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle) "
            "VALUES ('L', 'l', 'x', 'lehrperson')"
        ).lastrowid
        conn.execute(
            "INSERT INTO antworten (frage_id, konto_id, text) VALUES (?, ?, 'Antwort')", (f, k)
        )
        conn.commit()
        migriere(conn)
        assert [tuple(z) for z in conn.execute("SELECT frage_id, text FROM antworten")] == [
            (f, "Antwort")
        ]
    finally:
        conn.close()
