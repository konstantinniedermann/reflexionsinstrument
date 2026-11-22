"""Ablauf einer Runde: Fragen und Zusatzinfos in gemeinsamer Reihenfolge."""

import pytest

from app.eingaben import InhaltFehler
from app.inhalte import (
    NichtGefunden,
    ablauf,
    aendere_zusatzinfo,
    lege_frage_an,
    lege_runde_an,
    lege_zusatzinfo_an,
    loesche_frage,
    loesche_runde,
    loesche_zusatzinfo,
    verschiebe_im_ablauf,
    zusatzinfo,
)


def _runde(db, datum="2026-11-23"):
    return lege_runde_an(db, "Runde", "", datum)


def _frage(db, rid, text):
    return lege_frage_an(db, rid, "freitext", text, "", "")


def _folge(db, rid):
    return [
        b["frage"]["text"] if b["art"] == "frage" else "I:" + b["zusatzinfo"]["inhalt"]
        for b in ablauf(db, rid)
    ]


def _nummern(db, rid):
    return [b[b["art"]]["reihenfolge"] for b in ablauf(db, rid)]


def test_neue_bausteine_kommen_ans_ende(db):
    rid = _runde(db)
    _frage(db, rid, "a")
    lege_zusatzinfo_an(db, rid, "x")
    _frage(db, rid, "b")
    lege_zusatzinfo_an(db, rid, "y")
    assert _folge(db, rid) == ["a", "I:x", "b", "I:y"]
    assert _nummern(db, rid) == [1, 2, 3, 4]


def test_zusatzinfo_vor_erster_frage(db):
    rid = _runde(db)
    lege_zusatzinfo_an(db, rid, "x")
    _frage(db, rid, "a")
    assert _folge(db, rid) == ["I:x", "a"]


def test_verschieben_ueber_die_art_hinweg(db):
    rid = _runde(db)
    a = _frage(db, rid, "a")
    _frage(db, rid, "b")
    info = lege_zusatzinfo_an(db, rid, "x")
    verschiebe_im_ablauf(db, "zusatzinfo", info, "hoch")
    assert _folge(db, rid) == ["a", "I:x", "b"]
    verschiebe_im_ablauf(db, "frage", a, "runter")
    assert _folge(db, rid) == ["I:x", "a", "b"]
    verschiebe_im_ablauf(db, "zusatzinfo", info, "hoch")
    assert _folge(db, rid) == ["I:x", "a", "b"]
    assert _nummern(db, rid) == [1, 2, 3]
    with pytest.raises(ValueError):
        verschiebe_im_ablauf(db, "info", info, "hoch")


def test_verschieben_bleibt_in_der_runde(db):
    r1, r2 = _runde(db), _runde(db, "2026-11-30")
    _frage(db, r1, "a")
    info = lege_zusatzinfo_an(db, r2, "x")
    _frage(db, r2, "b")
    verschiebe_im_ablauf(db, "zusatzinfo", info, "runter")
    assert _folge(db, r1) == ["a"]
    assert _folge(db, r2) == ["b", "I:x"]


def test_loeschen_nummeriert_den_ablauf_neu(db):
    rid = _runde(db)
    _frage(db, rid, "a")
    info = lege_zusatzinfo_an(db, rid, "x")
    b = _frage(db, rid, "b")
    lege_zusatzinfo_an(db, rid, "y")
    loesche_frage(db, b)
    assert _folge(db, rid) == ["a", "I:x", "I:y"]
    assert _nummern(db, rid) == [1, 2, 3]
    loesche_zusatzinfo(db, info)
    assert _folge(db, rid) == ["a", "I:y"]
    assert _nummern(db, rid) == [1, 2]


def test_zusatzinfo_pruefen_und_aendern(db):
    rid = _runde(db)
    with pytest.raises(InhaltFehler) as fehler:
        lege_zusatzinfo_an(db, rid, "   ")
    assert (fehler.value.feld, fehler.value.meldung) == ("inhalt", "Bitte einen Text eingeben.")
    info = lege_zusatzinfo_an(db, rid, "  alt  ")
    aendere_zusatzinfo(db, info, "neu")
    assert zusatzinfo(db, info)["inhalt"] == "neu"
    with pytest.raises(NichtGefunden):
        aendere_zusatzinfo(db, 999, "neu")
    with pytest.raises(NichtGefunden):
        loesche_zusatzinfo(db, 999)
    with pytest.raises(NichtGefunden):
        lege_zusatzinfo_an(db, 999, "x")


def test_runde_loeschen_nimmt_zusatzinfos_mit(db):
    rid = _runde(db)
    info = lege_zusatzinfo_an(db, rid, "x")
    loesche_runde(db, rid)
    assert zusatzinfo(db, info) is None
