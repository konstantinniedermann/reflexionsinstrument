"""Blocksatz mit Silbentrennung für Fliesstexte der Lehrpersonen-Ansicht (Rückmeldung 15.11.)."""

import re
from datetime import date
from pathlib import Path

from conftest import als_lehrperson, als_leitung

CSS = (Path(__file__).parent.parent / "app" / "static" / "css" / "style.css").read_text(
    encoding="utf-8"
)


def _regel(selektor: str) -> str:
    treffer = re.search(rf"{re.escape(selektor)}\s*\{{([^}}]*)\}}", CSS)
    assert treffer, selektor
    return treffer.group(1)


def test_fliesstext_im_blocksatz_mit_silbentrennung():
    regel = _regel(".seite .formatiert p,\n.seite .formatiert li")
    assert "text-align: justify" in regel
    assert "hyphens: auto" in regel


def test_lehrperson_seiten_tragen_die_klasse(client, lehrperson, heute_ist):
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson").text
    assert '<body class="seite ' in text
    assert '<html lang="de">' in text


def test_verwaltung_ohne_blocksatz(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    assert '<body class="seite' not in client.get("/verwaltung/inhalte").text
