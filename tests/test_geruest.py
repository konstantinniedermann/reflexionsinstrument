from pathlib import Path

import pytest
from conftest import als_leitung
from fastapi import APIRouter
from fastapi.testclient import TestClient

from app.main import erstelle_app
from app.routen import aufnahmen, gast, verwaltung_eintraege, verwaltung_vorschau

MODULE = {
    "aufnahmen": aufnahmen,
    "verwaltung_eintraege": verwaltung_eintraege,
    "gast": gast,
    "verwaltung_vorschau": verwaltung_vorschau,
}
APP = Path(__file__).parent.parent / "app"


def test_router_eingebunden_ohne_praefix(einstellungen, monkeypatch):
    for name, modul in MODULE.items():
        r = APIRouter()
        r.get(f"/geruest-{name}")(lambda: "ok")
        monkeypatch.setattr(modul, "router", r)
    with TestClient(erstelle_app(einstellungen)) as c:
        for name in MODULE:
            assert c.get(f"/geruest-{name}").status_code == 200, name


@pytest.mark.parametrize("datei", ["start.html", "rahmen.html"])
def test_verwaltung_vorbereitete_plaetze(datei):
    text = (APP / "templates" / "verwaltung" / datei).read_text(encoding="utf-8")
    trenn = "{# Trennzeile zwischen #18 und #19, nicht ändern #}"
    assert text.index("{# #18:") < text.index(trenn) < text.index("{# #19:")
    assert "{% for name in" not in text


def test_verwaltung_unveraendert(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    seite = client.get("/verwaltung").text
    assert "Einträge" in seite and "Vorschau" in seite


def test_css_abschnitte():
    css = (APP / "static" / "css" / "style.css").read_text(encoding="utf-8")
    marken = [
        "/* Pilot: Lehrpersonen-Ansicht */",
        "/* Pilot: Aufnahmen (#17) */",
        "/* Ende #17 */",
        "/* Pilot: Einträge und Export (#18) */",
        "/* Ende #18 */",
        "/* Pilot: Gast und Vorschau (#19) */",
        "/* Ende #19 */",
    ]
    stellen = [css.index(m) for m in marken]
    assert stellen == sorted(stellen)


def test_e2e_geruest():
    e2e = (Path(__file__).parent / "e2e-pilot.mjs").read_text(encoding="utf-8")
    for teil in (
        "--use-fake-ui-for-media-stream",
        "--use-fake-device-for-media-stream",
        "async function ablaufLehrperson",
        "async function ablaufAufnahmen",
        "async function ablaufEintraege",
        "async function ablaufGast",
        "await ablaufGast();",
    ):
        assert teil in e2e
