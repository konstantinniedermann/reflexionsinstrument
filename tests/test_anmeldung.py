import re
from dataclasses import replace

import pytest
from conftest import anmelden, csrf_von
from fastapi.testclient import TestClient

from app.main import erstelle_app

FALSCH = "Benutzername oder Passwort stimmt nicht."


def test_login_seite(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    text = antwort.text
    assert "Anmelden" in text
    assert 'name="benutzername"' in text
    assert 'name="passwort"' in text
    assert re.search(r'<input[^>]*name="dauerhaft"[^>]*checked', text)
    assert "Den Zugang erhältst du von der Projektleitung." in text


def test_anmelden_lehrperson(client, lehrperson):
    antwort = anmelden(client, "lp.anna", "anna-pass-1")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/lehrperson"
    assert "Anna Beispiel" in client.get("/lehrperson").text
    antwort = client.get("/")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/lehrperson"


def test_anmelden_auftraggeberin(client, auftraggeberin):
    antwort = anmelden(client, "projektleitung", "leitung-pass-1")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/verwaltung"


@pytest.mark.parametrize(
    ("name", "passwort"), [("lp.anna", "falsch-falsch"), ("lp.unbekannt", "irgendwas-1")]
)
def test_anmelden_falsch(client, lehrperson, name, passwort):
    antwort = anmelden(client, name, passwort)
    assert antwort.status_code == 400
    assert FALSCH in antwort.text
    assert "sitzung" not in client.cookies
    assert f'value="{name}"' in antwort.text
    assert passwort not in antwort.text


def test_anmelden_mit_ueberlangem_passwort(client, lehrperson):
    antwort = anmelden(client, "lp.anna", "ä" * 50)
    assert antwort.status_code == 400
    assert FALSCH in antwort.text


def test_anmelden_schreibweise_egal(client, lehrperson):
    antwort = anmelden(client, " LP.Anna ", "anna-pass-1")
    assert antwort.status_code == 303


def test_sperre_nach_fuenf_fehlversuchen(client, lehrperson):
    for _ in range(5):
        assert anmelden(client, "lp.anna", "falsch-falsch").status_code == 400
    antwort = anmelden(client, "lp.anna", "anna-pass-1")
    assert antwort.status_code == 429
    assert "Zu viele Fehlversuche. Bitte in 15 Minuten nochmals versuchen." in antwort.text
    assert "sitzung" not in client.cookies


def test_fehlversuche_verraten_keine_namen_im_log(client, lehrperson, caplog):
    anmelden(client, "lp.anna", "falsch-falsch")
    assert "lp.anna" not in caplog.text
    assert "falsch-falsch" not in caplog.text


def test_fly_client_ip_nur_in_produktion(einstellungen):
    produktion = replace(einstellungen, produktion=True, geheimer_schluessel="x" * 40)
    with TestClient(
        erstelle_app(produktion), base_url="https://testserver", follow_redirects=False
    ) as c:
        eins = {"Fly-Client-IP": "1.2.3.4"}
        for i in range(20):
            anmelden(c, f"name{i}", "falsch-falsch", headers=eins)
        assert anmelden(c, "name99", "falsch-falsch", headers=eins).status_code == 429
        zwei = {"Fly-Client-IP": "5.6.7.8"}
        assert anmelden(c, "name99", "falsch-falsch", headers=zwei).status_code == 400


def test_fly_client_ip_in_entwicklung_ignoriert(client):
    for i in range(20):
        anmelden(client, f"name{i}", "falsch-falsch", headers={"Fly-Client-IP": f"1.1.1.{i}"})
    antwort = anmelden(client, "name99", "falsch-falsch", headers={"Fly-Client-IP": "9.9.9.9"})
    assert antwort.status_code == 429


def test_abmelden(client, lehrperson):
    anmelden(client, "lp.anna", "anna-pass-1")
    vorher = client.cookies["csrf"]
    antwort = client.post("/abmelden", data={"csrf": csrf_von(client, "/lehrperson")})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/"
    assert client.get("/lehrperson").headers["location"] == "/"
    assert client.cookies["csrf"] != vorher


def test_anmelden_erneuert_csrf(client, lehrperson):
    client.get("/")
    vorher = client.cookies["csrf"]
    anmelden(client, "lp.anna", "anna-pass-1")
    assert client.cookies["csrf"] != vorher


def test_abgelaufenes_formular_beim_anmelden(client, lehrperson):
    antwort = client.post("/anmelden", data={"benutzername": "lp.anna", "passwort": "anna-pass-1"})
    assert antwort.status_code == 403
    assert "Formular abgelaufen" in antwort.text
