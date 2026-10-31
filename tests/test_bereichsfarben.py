"""Bereichsfarben als Navigationshilfe, siehe docs/superpowers/specs/2026-10-31-bereichsfarben-design.md."""

import re
from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung


def _flaeche(text: str, bereich: str) -> list[str]:
    """Öffnende Tags, die vollflächig in der Farbe des Bereichs stehen."""
    return [
        t
        for t in re.findall(r"<(?:a|section|article|div)\b[^>]*>", text)
        if re.search(r'class="[^"]*\bflaeche\b', t) and f"bereich--{bereich}" in t
    ]


def _etikett(text: str) -> list[str]:
    return re.findall(r'class="seitenetikett"[^>]*>([^<]*)<', text)


@pytest.fixture
def inhalte(db, heute_ist):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    runde_id, frage_ids = testdaten.lege_runde_an(
        db, "Runde Eins", "2026-11-23", fallbeispiel="Ein Fall."
    )
    impuls_id = testdaten.lege_impuls_an(db, "Impuls Eins", "2026-11-23")
    testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    db.commit()
    heute_ist(date(2026, 11, 24))
    return {"runde": runde_id, "fragen": frage_ids, "impuls": impuls_id}


def test_start_karten_vollflaechig(client, lehrperson, inhalte):
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson").text
    for bereich in ("runden", "tagebuch", "impuls", "info"):
        assert _flaeche(text, bereich), bereich
    assert _etikett(text) == []


@pytest.mark.parametrize(
    "pfad,name",
    [
        ("/lehrperson/info", "Info"),
        ("/lehrperson/tagebuch/neu/frei", "Tagebuch"),
    ],
)
def test_seitenetikett_ueber_dem_inhalt(client, lehrperson, inhalte, pfad, name):
    als_lehrperson(client, lehrperson)
    assert _etikett(client.get(pfad).text) == [name]


def test_seitenetikett_runde(client, lehrperson, inhalte):
    als_lehrperson(client, lehrperson)
    text = client.get(f"/lehrperson/runden/{inhalte['runde']}").text
    assert _etikett(text) == ["Runden"]
    assert _flaeche(text, "runden")


@pytest.mark.parametrize(
    "pfad,name",
    [("/lehrperson/tagebuch/neu", "Tagebuch"), ("/lehrperson/eintraege", "Meine Einträge")],
)
def test_ueberschrift_wird_zum_etikett(client, lehrperson, inhalte, pfad, name):
    """Lautet die Überschrift wie der Bereich, steht der Name nicht doppelt da."""
    als_lehrperson(client, lehrperson)
    text = client.get(pfad).text
    assert re.search(rf'<h1 class="seitenetikett"[^>]*>{name}</h1>', text)
    assert _etikett(text) == [name]


def test_tagebuch_wahl_farbig(client, lehrperson, inhalte):
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson/tagebuch/neu").text
    assert len(_flaeche(text, "tagebuch")) >= 3  # frei schreiben, frei sprechen, Leitfrage
    assert len(_flaeche(text, "impuls")) == 1


def test_meine_eintraege_in_der_farbe_der_art(client, db, lehrperson, inhalte):
    testdaten.lege_antwort_an(db, inhalte["fragen"][0], lehrperson["id"], "Antwort")
    testdaten.lege_eintrag_an(db, lehrperson["id"], "frei", "Frei")
    testdaten.lege_eintrag_an(
        db, lehrperson["id"], "impuls", "Zum Impuls", impuls_id=inhalte["impuls"]
    )
    db.commit()
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson/eintraege").text
    for bereich in ("runden", "tagebuch", "impuls"):
        assert len([t for t in _flaeche(text, bereich) if "karte--eintrag" in t]) == 1, bereich


def _aktiv(text: str) -> list[str]:
    nav = re.search(r'<nav class="verwaltungsnavigation".*?</nav>', text, re.DOTALL).group(0)
    return re.findall(r'<a [^>]*aria-current="page"[^>]*>([^<]*)</a>', nav)


@pytest.mark.parametrize(
    "pfad,aktiv",
    [
        ("/verwaltung", "Übersicht"),
        ("/verwaltung/inhalte", "Inhalte"),
        ("/verwaltung/inhalte/runden", "Inhalte"),
        ("/verwaltung/eintraege", "Einträge"),
        ("/verwaltung/vorschau", "Vorschau"),
        ("/verwaltung/zugaenge", "Zugänge"),
        ("/verwaltung/benachrichtigung", "Benachrichtigung"),
    ],
)
def test_verwaltungsnavigation_zeigt_ort(client, auftraggeberin, pfad, aktiv):
    als_leitung(client, auftraggeberin)
    assert _aktiv(client.get(pfad).text) == [aktiv]


def test_verwaltungsnavigation_farbig(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung").text
    nav = re.search(r'<nav class="verwaltungsnavigation".*?</nav>', text, re.DOTALL).group(0)
    links = re.findall(r"<a [^>]*>", nav)
    assert len(links) == 6
    assert all(re.search(r'class="bereich--[a-z]+"', a) for a in links)


def test_inhalte_uebersicht_in_den_farben_der_lehrpersonen(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung/inhalte").text
    for bereich, anker in (
        ("info", "bereich-info"),
        ("runden", "bereich-runden"),
        ("tagebuch", "bereich-leitfragen"),
        ("impuls", "bereich-impulse"),
    ):
        assert [t for t in _flaeche(text, bereich) if anker in t], bereich
