"""Benachrichtigungen auf den Seiten: Ein/Aus nur wo sinnvoll, Hinweistext, Manifest-Links (#37)."""

import pytest
from conftest import als_lehrperson, als_leitung

from app.config import Einstellungen
from app.push import erzeuge_vapid_schluessel
from app.texte import REGISTER

SKRIPT = 'src="/static/js/benachrichtigung.js"'


@pytest.fixture
def einstellungen(tmp_path):
    return Einstellungen(
        daten_verzeichnis=tmp_path / "daten",
        geheimer_schluessel="test-schluessel",
        produktion=False,
        vapid_schluessel=erzeuge_vapid_schluessel(),
    )


@pytest.mark.parametrize("pfad,ort", [("/lehrperson", "start"), ("/lehrperson/info", "info")])
def test_lehrperson_sieht_ein_aus(client, lehrperson, pfad, ort):
    seite = als_lehrperson(client, lehrperson).get(pfad).text
    assert SKRIPT in seite
    assert f'data-ort="{ort}"' in seite
    assert f'data-push-schluessel="{client.app.state.push_schluessel}"' in seite
    assert 'data-aktion="ein"' in seite
    assert 'name="csrf"' in seite


def test_info_zeigt_hinweistext(client, lehrperson):
    seite = als_lehrperson(client, lehrperson).get("/lehrperson/info").text
    assert "Benachrichtigungen sind freiwillig" in seite


def test_andere_seiten_ohne(client, lehrperson):
    seite = als_lehrperson(client, lehrperson).get("/lehrperson/tagebuch/neu").text
    assert SKRIPT not in seite


@pytest.mark.parametrize("pfad", ["/gast", "/gast/info"])
def test_gast_ohne(client, pfad):
    assert SKRIPT not in client.get(pfad).text


def test_vorschau_ohne(client, auftraggeberin):
    leitung = als_leitung(client, auftraggeberin)
    for pfad in ("/verwaltung/vorschau/2026-11-24", "/verwaltung/vorschau/2026-11-24/info"):
        assert SKRIPT not in leitung.get(pfad).text


def test_verwaltung_kann_selbst_einschalten(client, auftraggeberin):
    seite = als_leitung(client, auftraggeberin).get("/verwaltung/benachrichtigung").text
    assert SKRIPT in seite
    assert 'data-ort="verwaltung"' in seite


def test_manifest_und_symbol_verlinkt(client):
    seite = client.get("/").text
    assert '<link rel="manifest" href="/manifest.webmanifest"' in seite
    assert '<link rel="apple-touch-icon" href="/static/bilder/symbol-180.png"' in seite
    assert 'name="apple-mobile-web-app-title"' in seite


def test_hinweistext_im_register():
    vorlage = REGISTER["hinweis_benachrichtigung"]
    assert vorlage.bereich == "hinweise"
    assert "nie Einträge" in vorlage.vorschlag
    assert "Push" not in vorlage.vorschlag


def test_eingabemaske_listet_hinweis(client, auftraggeberin):
    seite = als_leitung(client, auftraggeberin).get("/verwaltung/inhalte").text
    assert "0 von 6 Hinweisen bestätigt" in seite
