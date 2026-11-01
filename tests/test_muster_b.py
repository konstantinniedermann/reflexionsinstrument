"""Muster B in der Pilot-Version, siehe docs/superpowers/specs/2026-11-01-muster-b-uebernahme-design.md."""

import re
from datetime import date
from pathlib import Path

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung

CSS = (Path(__file__).parent.parent / "app" / "static" / "css" / "style.css").read_text(
    encoding="utf-8"
)


def _farbe(name: str) -> str:
    return re.search(rf"--farbe-{name}:\s*(#[0-9a-f]{{6}});", CSS).group(1)


def test_impuls_und_tagebuch_verschiedene_farben():
    farben = [_farbe(n) for n in ("start", "runden", "tagebuch", "impuls", "eintraege", "info")]
    assert len(set(farben)) == len(farben)


@pytest.fixture
def inhalte(db, heute_ist):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    runde_id, _ = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23", fallbeispiel="Fall.")
    testdaten.lege_impuls_an(db, "Impuls Eins", "2026-11-23")
    db.commit()
    heute_ist(date(2026, 11, 24))
    return {"runde": runde_id}


@pytest.mark.parametrize(
    "pfad,bereich",
    [
        ("/lehrperson", "start"),
        ("/lehrperson/tagebuch/neu", "tagebuch"),
        ("/lehrperson/eintraege", "eintraege"),
        ("/lehrperson/info", "info"),
    ],
)
def test_seite_traegt_registerfarbe(client, lehrperson, inhalte, pfad, bereich):
    als_lehrperson(client, lehrperson)
    assert f'<body class="seite bereich--{bereich}">' in client.get(pfad).text


def test_runde_traegt_runden_ton(client, lehrperson, inhalte):
    als_lehrperson(client, lehrperson)
    text = client.get(f"/lehrperson/runden/{inhalte['runde']}").text
    assert '<body class="seite bereich--runden">' in text
    nav = re.search(r'<nav class="tabs".*?</nav>', text, re.DOTALL).group(0)
    assert re.search(r'<a class="bereich--runden" [^>]*aria-current="page"', nav)


def test_verwaltung_ohne_registerton(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    assert "<body>" in client.get("/verwaltung/inhalte").text
