"""Benachrichtigungen ohne VAPID-Schlüssel: Funktion aus, App läuft (#37)."""

import pytest
from conftest import als_lehrperson, als_leitung, csrf_von
from test_push_abos import AUTH, P256DH


@pytest.fixture
def lp(client, lehrperson):
    return als_lehrperson(client, lehrperson)


@pytest.fixture
def leitung(client, auftraggeberin):
    return als_leitung(client, auftraggeberin)


def test_abo_nicht_moeglich(lp):
    daten = {
        "csrf": csrf_von(lp, "/lehrperson/info"),
        "endpunkt": "https://fcm.googleapis.com/fcm/send/abc",
        "p256dh": P256DH,
        "auth": AUTH,
    }
    assert lp.post("/benachrichtigung/abo", data=daten).status_code == 404


def test_verwaltung_erklaert(leitung):
    seite = leitung.get("/verwaltung/benachrichtigung").text
    assert "Benachrichtigungen sind nicht eingerichtet." in seite
    assert "<textarea" not in seite


def test_verwaltung_senden_nicht_moeglich(leitung):
    daten = {"csrf": csrf_von(leitung, "/verwaltung/benachrichtigung"), "text": "Hallo"}
    assert leitung.post("/verwaltung/benachrichtigung", data=daten).status_code == 404


def test_manifest_und_service_worker_trotzdem(client):
    assert client.get("/manifest.webmanifest").status_code == 200
    assert client.get("/sw.js").status_code == 200


def test_lehrperson_ohne_schluessel_ohne_skript(lp):
    for pfad in ("/lehrperson", "/lehrperson/info"):
        assert "benachrichtigung.js" not in lp.get(pfad).text
