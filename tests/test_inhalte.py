from datetime import date

import pytest

from app.db import transaktion
from app.eingaben import InhaltFehler, kurzer_text
from app.inhalte import (
    lies_projektstart,
    lies_titel,
    speichere_allgemein,
    zaehle_inhalte,
)
from app.texte import lies_text


def test_kurzer_text_wird_eine_zeile():
    assert kurzer_text("a\r\nb\nc ", "f", 500, "m") == "a b c"
    assert kurzer_text("", "f", 60, None) is None


def test_titel_standard(db):
    assert lies_titel(db) == "Reflexionsinstrument"
    assert lies_projektstart(db) is None


def test_speichere_allgemein(db):
    speichere_allgemein(db, "Lernheft", "Hallo **alle**", "2026-11-23")
    assert lies_titel(db) == "Lernheft"
    assert lies_text(db, "begruessung") == "Hallo **alle**"
    assert lies_projektstart(db) == date(2026, 11, 23)


def test_allgemein_ohne_ersten_tag(db):
    speichere_allgemein(db, "Lernheft", "Hallo", "2026-11-23")
    speichere_allgemein(db, "Lernheft", "Hallo", "")
    assert lies_projektstart(db) is None


def test_allgemein_fehler_schreibt_nichts(db):
    speichere_allgemein(db, "Alt", "Alter Text", "2026-11-23")
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "Neu", "Neuer Text", "23.11.2026")
    assert e.value.feld == "projektstart"
    assert lies_titel(db) == "Alt"
    assert lies_text(db, "begruessung") == "Alter Text"
    assert lies_projektstart(db) == date(2026, 11, 23)


def test_titel_zu_lang(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "x" * 61, "Hallo", "")
    assert e.value.feld == "titel"


def test_titel_leer(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, " ", "Hallo", "")
    assert e.value.feld == "titel"


def test_begruessung_leer(db):
    with pytest.raises(InhaltFehler) as e:
        speichere_allgemein(db, "Titel", " ", "")
    assert e.value.feld == "begruessung"


def test_transaktion_verschachtelt(db):
    with pytest.raises(RuntimeError), transaktion(db):
        speichere_allgemein(db, "Neu", "Neuer Text", "2026-11-23")
        raise RuntimeError("abbruch")
    assert lies_titel(db) == "Reflexionsinstrument"
    assert lies_projektstart(db) is None
    assert not db.in_transaction


def test_zaehle_inhalte(db):
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('A', '2026-11-23')")
    db.execute("INSERT INTO runden (titel, freischaltdatum) VALUES ('B', '2026-11-30')")
    for i in range(3):
        db.execute(f"INSERT INTO fragen (runde_id, typ, text) VALUES (1, 'freitext', 'F{i}')")
    db.execute("INSERT INTO info_abschnitte (titel, inhalt) VALUES ('T', 'I')")
    assert zaehle_inhalte(db) == {
        "runden": 2,
        "fragen": 3,
        "runden_ohne_fragen": 1,
        "info_abschnitte": 1,
        "leitfragen": 0,
        "impulse": 0,
    }
