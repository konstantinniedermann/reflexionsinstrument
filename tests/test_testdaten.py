import re
from datetime import date

import testdaten


def test_lege_runde_an(db):
    rid, (f1, f2) = testdaten.lege_runde_an(db)
    zeilen = db.execute(
        "SELECT id, typ, skala_min_text, skala_max_text, reihenfolge FROM fragen "
        "WHERE runde_id = ? ORDER BY reihenfolge",
        (rid,),
    ).fetchall()
    assert [z[0] for z in zeilen] == [f1, f2]
    assert (zeilen[0][1], zeilen[0][4]) == ("freitext", 1)
    assert tuple(zeilen[1][1:]) == ("skala", "wenig", "viel", 2)
    assert (
        db.execute("SELECT freischaltdatum FROM runden WHERE id = ?", (rid,)).fetchone()[0]
        == "2026-11-23"
    )


def test_lege_eintrag_kopiert_bezug(db, lehrperson):
    iid = testdaten.lege_impuls_an(db, text="Ein Impuls")
    lid = testdaten.lege_leitfrage_an(db, text="Eine Leitfrage")
    e1 = testdaten.lege_eintrag_an(db, lehrperson["id"], art="impuls", impuls_id=iid)
    e2 = testdaten.lege_eintrag_an(db, lehrperson["id"], art="leitfragen", leitfrage_id=lid)
    assert db.execute("SELECT impuls_text FROM tagebucheintraege WHERE id = ?", (e1,)).fetchone()[
        0
    ] == ("Ein Impuls")
    assert db.execute(
        "SELECT leitfrage_text FROM tagebucheintraege WHERE id = ?", (e2,)
    ).fetchone()[0] == ("Eine Leitfrage")


def test_lege_aufnahme_an(db, lehrperson, einstellungen):
    verzeichnis = einstellungen.aufnahmen_verzeichnis
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], verzeichnis)
    name, mime, groesse, dauer = db.execute(
        "SELECT dateiname, mime_typ, groesse_bytes, dauer_sekunden FROM aufnahmen WHERE id = ?",
        (aid,),
    ).fetchone()
    assert re.fullmatch(r"[0-9a-f]{32}\.webm", name)
    inhalt = (verzeichnis / name).read_bytes()
    assert inhalt.startswith(b"\x1aE\xdf\xa3")
    assert (mime, groesse, dauer) == ("audio/webm", len(inhalt), 5)


def test_abzug_alle_tabellen(db):
    namen = {
        z[0]
        for z in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        )
    }
    assert len(namen) == 11
    assert set(testdaten.abzug(db)) == namen


def test_heute_ist(client, heute_ist):
    assert heute_ist(date(2026, 11, 22)) == date(2026, 11, 22)
    assert client.app.state.heute() == date(2026, 11, 22)
