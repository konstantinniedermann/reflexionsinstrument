import re

import pytest
from conftest import anmelden, csrf_von
from fastapi.testclient import TestClient

from app.db import verbinde

MUSTER_VORSCHLAG = re.compile(r"[a-z]{4}-[a-z]{4}-[a-z]{4}-\d{2}")


def als_leitung(client, auftraggeberin):
    assert (
        anmelden(client, auftraggeberin["benutzername"], auftraggeberin["passwort"]).status_code
        == 303
    )
    return client


def neues_fenster(client):
    return TestClient(client.app, follow_redirects=False)


def anlegen(client, pfad="/verwaltung/zugaenge", **felder):
    daten = {
        "csrf": csrf_von(client, "/verwaltung/zugaenge"),
        "anzeigename": "Clara Muster",
        "benutzername": "lp.clara",
        "passwort": "clara-pass-1",
    }
    daten.update(felder)
    return client.post(pfad, data=daten)


def test_uebersicht(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    antwort = client.get("/verwaltung")
    assert antwort.status_code == 200
    assert 'href="/verwaltung/zugaenge"' in antwort.text
    for name in ("Inhalte", "Einträge", "Vorschau"):
        assert name in antwort.text
    assert "folgt" in antwort.text


def test_liste_zeigt_nur_lehrpersonen(client, auftraggeberin, lehrperson, zweite_lehrperson):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung/zugaenge").text
    assert "Anna Beispiel" in text and "lp.anna" in text
    assert "Ben Beispiel" in text
    assert "projektleitung" not in text
    assert f"/verwaltung/zugaenge/{lehrperson['id']}/passwort" in text
    assert f"/verwaltung/zugaenge/{lehrperson['id']}/loeschen" in text


def test_formular_hat_passwort_vorschlag(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung/zugaenge").text
    treffer = re.search(r'name="passwort"[^>]*value="([^"]*)"', text)
    assert treffer and MUSTER_VORSCHLAG.fullmatch(treffer.group(1))
    assert 'type="text"' in text


def test_zugang_anlegen(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    antwort = anlegen(client)
    assert antwort.status_code == 200
    assert "lp.clara" in antwort.text and "clara-pass-1" in antwort.text
    assert "Bitte notieren, es wird danach nicht mehr angezeigt." in antwort.text
    assert antwort.headers["cache-control"] == "no-store"
    lehrer = neues_fenster(client)
    assert anmelden(lehrer, "lp.clara", "clara-pass-1").status_code == 303


def test_zugang_anlegen_fehler(client, auftraggeberin, lehrperson):
    als_leitung(client, auftraggeberin)
    faelle = [
        ({"benutzername": "lp.anna"}, "Diesen Benutzernamen gibt es schon."),
        ({"passwort": "kurz"}, "mindestens 8 Zeichen"),
        ({"anzeigename": "  "}, "Bitte einen Namen eingeben."),
    ]
    for aenderung, meldung in faelle:
        antwort = anlegen(client, **aenderung)
        assert antwort.status_code == 400
        assert meldung in antwort.text
        erwartet = {"anzeigename": "Clara Muster", "benutzername": "lp.clara"} | aenderung
        for feld in ("anzeigename", "benutzername"):
            if erwartet[feld].strip():
                assert f'value="{erwartet[feld]}"' in antwort.text


def test_passwort_setzen_beendet_sitzungen(client, auftraggeberin, lehrperson):
    lehrer = neues_fenster(client)
    anmelden(lehrer, lehrperson["benutzername"], lehrperson["passwort"])
    assert lehrer.get("/lehrperson").status_code == 200
    als_leitung(client, auftraggeberin)
    pfad = f"/verwaltung/zugaenge/{lehrperson['id']}/passwort"
    assert MUSTER_VORSCHLAG.search(client.get(pfad).text)
    antwort = client.post(pfad, data={"csrf": csrf_von(client, pfad), "passwort": "neues-pass-9"})
    assert antwort.status_code == 200
    assert "neues-pass-9" in antwort.text
    assert "Bitte notieren, es wird danach nicht mehr angezeigt." in antwort.text
    assert lehrer.get("/lehrperson").status_code == 303
    assert anmelden(neues_fenster(client), "lp.anna", lehrperson["passwort"]).status_code == 400
    assert anmelden(neues_fenster(client), "lp.anna", "neues-pass-9").status_code == 303


def test_passwort_setzen_fehler(client, auftraggeberin, lehrperson):
    als_leitung(client, auftraggeberin)
    pfad = f"/verwaltung/zugaenge/{lehrperson['id']}/passwort"
    antwort = client.post(pfad, data={"csrf": csrf_von(client, pfad), "passwort": "kurz"})
    assert antwort.status_code == 400
    assert "mindestens 8 Zeichen" in antwort.text
    assert 'value="kurz"' in antwort.text


def _daten_anlegen(einstellungen, konto_id, aufnahmen=0):
    conn = verbinde(einstellungen.db_pfad)
    try:
        conn.execute(
            "INSERT INTO tagebucheintraege (konto_id, art, text) VALUES (?, 'frei', 'x')",
            (konto_id,),
        )
        dateien = []
        for i in range(aufnahmen):
            name = f"auf-{konto_id}-{i}.webm"
            datei = einstellungen.aufnahmen_verzeichnis / name
            datei.write_bytes(b"x")
            dateien.append(datei)
            conn.execute(
                "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes)"
                " VALUES (?, ?, 'audio/webm', 1)",
                (konto_id, name),
            )
        return dateien
    finally:
        conn.close()


def test_loeschen_bestaetigung_zeigt_zahlen(client, einstellungen, auftraggeberin, lehrperson):
    _daten_anlegen(einstellungen, lehrperson["id"], aufnahmen=3)
    als_leitung(client, auftraggeberin)
    text = client.get(f"/verwaltung/zugaenge/{lehrperson['id']}/loeschen").text
    assert "1 Tagebucheintrag " in text or "1 Tagebucheintrag<" in text
    assert "0 Antworten" in text
    assert "3 Aufnahmen" in text
    assert "Anna Beispiel" in text
    assert "Das lässt sich nicht rückgängig machen." in text
    assert "Endgültig löschen" in text and "Abbrechen" in text


def test_loeschen_bestaetigung_einzahl(client, einstellungen, auftraggeberin, lehrperson):
    _daten_anlegen(einstellungen, lehrperson["id"], aufnahmen=1)
    als_leitung(client, auftraggeberin)
    text = client.get(f"/verwaltung/zugaenge/{lehrperson['id']}/loeschen").text
    assert "1 Aufnahme " in text or "1 Aufnahme." in text
    assert "1 Aufnahmen" not in text


def test_loeschen(client, einstellungen, auftraggeberin, lehrperson, zweite_lehrperson):
    dateien = _daten_anlegen(einstellungen, lehrperson["id"], aufnahmen=1)
    fremde = _daten_anlegen(einstellungen, zweite_lehrperson["id"], aufnahmen=1)
    lehrer = neues_fenster(client)
    anmelden(lehrer, lehrperson["benutzername"], lehrperson["passwort"])
    als_leitung(client, auftraggeberin)
    pfad = f"/verwaltung/zugaenge/{lehrperson['id']}/loeschen"
    antwort = client.post(pfad, data={"csrf": csrf_von(client, pfad)})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/verwaltung/zugaenge?erledigt=geloescht"
    assert not dateien[0].exists() and fremde[0].exists()
    liste = client.get(antwort.headers["location"]).text
    assert "Der Zugang wurde gelöscht." in liste
    assert "lp.anna" not in liste and "lp.ben" in liste
    assert lehrer.get("/lehrperson").status_code == 303


def test_fremde_ids_404(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    token = csrf_von(client, "/verwaltung")
    for konto_id in (auftraggeberin["id"], 999):
        for aktion in ("passwort", "loeschen"):
            pfad = f"/verwaltung/zugaenge/{konto_id}/{aktion}"
            assert client.get(pfad).status_code == 404, pfad
            antwort = client.post(pfad, data={"csrf": token, "passwort": "irgendwas-12"})
            assert antwort.status_code == 404, pfad


def test_bestaetigung_nur_aus_fester_liste(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung/zugaenge?erledigt=<script>").text
    assert "<script>" not in text and "script" not in text.lower()


@pytest.mark.parametrize(
    "pfad",
    [
        "/verwaltung/zugaenge/abc/passwort",
        "/verwaltung/zugaenge/99999999999999999999999/passwort",
        "/verwaltung/zugaenge/0/loeschen",
    ],
)
def test_ungueltige_id_ist_404_als_seite(client, auftraggeberin, pfad):
    antwort = als_leitung(client, auftraggeberin).get(pfad)
    assert antwort.status_code == 404
    assert antwort.headers["content-type"].startswith("text/html")
    assert "Diese Seite gibt es nicht." in antwort.text
