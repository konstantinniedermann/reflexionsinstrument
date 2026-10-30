import pytest
import testdaten

from app.db import transaktion
from app.eingaben import InhaltFehler
from app.eintraege import (
    aendere_tagebucheintrag,
    anzahl_tagebucheintraege,
    hole_tagebucheintrag,
    lege_tagebucheintrag_an,
    lies_tagebuchtext,
    loesche_tagebucheintrag,
)

ALT = "2026-01-01T00:00:00Z"
JETZT = "2026-12-01T08:00:00Z"


def _impuls(db, text="Impuls A"):
    return db.execute(
        "SELECT * FROM impulse WHERE id = ?", (testdaten.lege_impuls_an(db, text),)
    ).fetchone()


def _leitfrage(db, text="Leitfrage A"):
    lid = testdaten.lege_leitfrage_an(db, text)
    return db.execute("SELECT * FROM leitfragen WHERE id = ?", (lid,)).fetchone()


def test_lies_tagebuchtext():
    assert lies_tagebuchtext("  a\r\nb ") == "a\nb"
    with pytest.raises(InhaltFehler) as fehler:
        lies_tagebuchtext(" ")
    assert fehler.value.feld == "text"
    assert fehler.value.meldung == "Der Eintrag ist noch leer."
    assert lies_tagebuchtext(" ", pflicht=False) is None
    with pytest.raises(InhaltFehler) as fehler:
        lies_tagebuchtext("x" * 20_001)
    assert "höchstens 20\xa0000 Zeichen" in fehler.value.meldung


def test_frei(db, lehrperson):
    eid = lege_tagebucheintrag_an(db, lehrperson["id"], "frei", "  Ein Tag ", jetzt=JETZT)
    zeile = hole_tagebucheintrag(db, lehrperson["id"], eid)
    assert zeile["art"] == "frei"
    assert zeile["text"] == "Ein Tag"
    assert zeile["erstellt"] == zeile["geaendert"] == JETZT
    assert zeile["impuls_id"] is zeile["leitfrage_id"] is zeile["aufnahme_id"] is None


def test_impuls_kopiert_text(db, lehrperson):
    impuls = _impuls(db)
    eid = lege_tagebucheintrag_an(db, lehrperson["id"], "impuls", "Text", impuls=impuls)
    db.execute("UPDATE impulse SET text = 'Neu'")
    zeile = hole_tagebucheintrag(db, lehrperson["id"], eid)
    assert zeile["impuls_text"] == "Impuls A"
    assert zeile["impuls_id"] == impuls["id"]


def test_leitfrage_kopiert_text(db, lehrperson):
    leitfrage = _leitfrage(db)
    eid = lege_tagebucheintrag_an(db, lehrperson["id"], "leitfragen", "Text", leitfrage=leitfrage)
    db.execute("UPDATE leitfragen SET text = 'Neu'")
    zeile = hole_tagebucheintrag(db, lehrperson["id"], eid)
    assert zeile["leitfrage_text"] == "Leitfrage A"
    assert zeile["leitfrage_id"] == leitfrage["id"]


def test_aufnahme_text_freiwillig(db, lehrperson, einstellungen):
    aid = testdaten.lege_aufnahme_an(
        db, lehrperson["id"], einstellungen.daten_verzeichnis / "aufnahmen"
    )
    eid = lege_tagebucheintrag_an(db, lehrperson["id"], "aufnahme", "", aufnahme_id=aid)
    zeile = hole_tagebucheintrag(db, lehrperson["id"], eid)
    assert zeile["text"] is None
    assert zeile["aufnahme_id"] == aid


@pytest.mark.parametrize("art", ["impuls", "frei", "aufnahme", "x"])
def test_falsche_kombination(db, lehrperson, art):
    leitfrage = _leitfrage(db) if art == "frei" else None
    with pytest.raises(ValueError):
        lege_tagebucheintrag_an(db, lehrperson["id"], art, "Text", leitfrage=leitfrage)
    assert anzahl_tagebucheintraege(db, lehrperson["id"]) == 0


def test_leer_nichts_angelegt(db, lehrperson):
    with pytest.raises(InhaltFehler):
        lege_tagebucheintrag_an(db, lehrperson["id"], "frei", " ")
    assert anzahl_tagebucheintraege(db, lehrperson["id"]) == 0


def test_doppelt_abgesendet_legt_einmal_an(db, lehrperson):
    k = lehrperson["id"]
    eid = lege_tagebucheintrag_an(db, k, "frei", "Ein Tag", jetzt="2026-12-01T08:00:00Z")
    # Zweites Absenden desselben Formulars innert 10 Sekunden, Text gleich nach Normalisierung.
    nochmal = lege_tagebucheintrag_an(db, k, "frei", " Ein Tag\r\n", jetzt="2026-12-01T08:00:10Z")
    assert nochmal == eid
    assert anzahl_tagebucheintraege(db, k) == 1


def test_gleicher_text_spaeter_neu(db, lehrperson):
    k = lehrperson["id"]
    eid = lege_tagebucheintrag_an(db, k, "frei", "Ein Tag", jetzt="2026-12-01T08:00:00Z")
    assert lege_tagebucheintrag_an(db, k, "frei", "Ein Tag", jetzt="2026-12-01T08:00:11Z") != eid
    assert anzahl_tagebucheintraege(db, k) == 2


def test_doppelt_nur_bei_gleichem_text_bezug_und_konto(db, lehrperson, zweite_lehrperson):
    k = lehrperson["id"]
    eins, zwei = _leitfrage(db, "Eins"), _leitfrage(db, "Zwei")
    ids = {
        lege_tagebucheintrag_an(db, k, "leitfragen", "Text", leitfrage=eins, jetzt=JETZT),
        lege_tagebucheintrag_an(db, k, "leitfragen", "Text", leitfrage=zwei, jetzt=JETZT),
        lege_tagebucheintrag_an(db, k, "leitfragen", "Anders", leitfrage=eins, jetzt=JETZT),
        lege_tagebucheintrag_an(db, k, "frei", "Text", jetzt=JETZT),
        lege_tagebucheintrag_an(db, k, "impuls", "Text", impuls=_impuls(db), jetzt=JETZT),
        lege_tagebucheintrag_an(db, zweite_lehrperson["id"], "frei", "Text", jetzt=JETZT),
    }
    assert len(ids) == 6


def test_transaktion_des_aufrufers(db, lehrperson):
    with pytest.raises(RuntimeError), transaktion(db):
        lege_tagebucheintrag_an(db, lehrperson["id"], "frei", "Text")
        raise RuntimeError("zurueck")
    assert anzahl_tagebucheintraege(db, lehrperson["id"]) == 0


def test_fremder_eintrag(db, lehrperson, zweite_lehrperson, einstellungen):
    eid = lege_tagebucheintrag_an(db, lehrperson["id"], "frei", "Text", jetzt=JETZT)
    fremd = zweite_lehrperson["id"]
    vorher = testdaten.abzug(db)
    assert hole_tagebucheintrag(db, fremd, eid) is None
    assert aendere_tagebucheintrag(db, fremd, eid, "Neu") is False
    assert loesche_tagebucheintrag(db, fremd, eid, einstellungen.daten_verzeichnis) is False
    assert loesche_tagebucheintrag(db, fremd, 9999, einstellungen.daten_verzeichnis) is False
    assert testdaten.abzug(db) == vorher


def test_aendern(db, lehrperson, einstellungen):
    konto = lehrperson["id"]
    eid = lege_tagebucheintrag_an(db, konto, "frei", "Text")
    db.execute("UPDATE tagebucheintraege SET erstellt = ?, geaendert = ?", (ALT,) * 2)
    assert aendere_tagebucheintrag(db, konto, eid, " Text ") is True
    assert hole_tagebucheintrag(db, konto, eid)["geaendert"] == ALT
    assert aendere_tagebucheintrag(db, konto, eid, "Neu") is True
    zeile = hole_tagebucheintrag(db, konto, eid)
    assert zeile["text"] == "Neu"
    assert zeile["geaendert"] > ALT
    assert zeile["erstellt"] == ALT
    with pytest.raises(InhaltFehler):
        aendere_tagebucheintrag(db, konto, eid, "")
    assert hole_tagebucheintrag(db, konto, eid)["text"] == "Neu"

    aid = testdaten.lege_aufnahme_an(db, konto, einstellungen.daten_verzeichnis / "aufnahmen")
    aufn = lege_tagebucheintrag_an(db, konto, "aufnahme", "Notiz", aufnahme_id=aid)
    assert aendere_tagebucheintrag(db, konto, aufn, "") is True
    assert hole_tagebucheintrag(db, konto, aufn)["text"] is None


def test_loeschen_mit_aufnahme(db, lehrperson, einstellungen):
    konto = lehrperson["id"]
    verzeichnis = einstellungen.daten_verzeichnis / "aufnahmen"
    aid = testdaten.lege_aufnahme_an(db, konto, verzeichnis)
    name = db.execute("SELECT dateiname FROM aufnahmen WHERE id = ?", (aid,)).fetchone()[0]
    eid = lege_tagebucheintrag_an(db, konto, "aufnahme", None, aufnahme_id=aid)

    with transaktion(db), pytest.raises(RuntimeError):
        loesche_tagebucheintrag(db, konto, eid, verzeichnis)
    assert (verzeichnis / name).exists()

    assert loesche_tagebucheintrag(db, konto, eid, verzeichnis) is True
    assert not (verzeichnis / name).exists()
    assert hole_tagebucheintrag(db, konto, eid) is None
    assert db.execute("SELECT COUNT(*) FROM aufnahmen").fetchone()[0] == 0


def test_anzahl(db, lehrperson, zweite_lehrperson, einstellungen):
    konto = lehrperson["id"]
    aid = testdaten.lege_aufnahme_an(db, konto, einstellungen.daten_verzeichnis / "aufnahmen")
    lege_tagebucheintrag_an(db, konto, "frei", "a")
    lege_tagebucheintrag_an(db, konto, "leitfragen", "b", leitfrage=_leitfrage(db))
    lege_tagebucheintrag_an(db, konto, "impuls", "c", impuls=_impuls(db))
    lege_tagebucheintrag_an(db, konto, "aufnahme", None, aufnahme_id=aid)
    lege_tagebucheintrag_an(db, zweite_lehrperson["id"], "frei", "x")
    assert anzahl_tagebucheintraege(db, konto) == 4
    assert anzahl_tagebucheintraege(db, zweite_lehrperson["id"]) == 1
