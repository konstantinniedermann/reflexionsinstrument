"""Aufnahmen abspielen: Lehrperson (nur eigene) und Auftraggeberin (alle)."""

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung

INHALT = testdaten.WEBM_ANFANG + bytes(60)


def _pfad(db, einstellungen, aid):
    name = db.execute("SELECT dateiname FROM aufnahmen WHERE id = ?", (aid,)).fetchone()[0]
    return einstellungen.aufnahmen_verzeichnis / name


@pytest.fixture
def aufnahme_der_ersten(db, lehrperson, einstellungen):
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    return aid, _pfad(db, einstellungen, aid)


def test_eigene_aufnahme_abspielen(client, lehrperson, aufnahme_der_ersten):
    aid, pfad = aufnahme_der_ersten
    als_lehrperson(client, lehrperson)
    r = client.get(f"/lehrperson/aufnahmen/{aid}")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/webm"
    assert r.headers["content-disposition"] == f'inline; filename="aufnahme-{aid}.webm"'
    assert r.headers["accept-ranges"] == "bytes"
    assert r.headers["cache-control"] == "no-store"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["cross-origin-resource-policy"] == "same-origin"
    assert r.content == pfad.read_bytes()


def test_range(client, lehrperson, aufnahme_der_ersten):
    aid, _ = aufnahme_der_ersten
    als_lehrperson(client, lehrperson)
    r = client.get(f"/lehrperson/aufnahmen/{aid}", headers={"Range": "bytes=0-3"})
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 0-3/64"
    assert r.content == testdaten.WEBM_ANFANG
    r = client.get(f"/lehrperson/aufnahmen/{aid}", headers={"Range": "bytes=64-"})
    assert r.status_code == 416


@pytest.mark.parametrize("kopf", [{}, {"Range": "bytes=0-3"}])
def test_fremde_aufnahme_404(client, zweite_lehrperson, aufnahme_der_ersten, kopf):
    aid, _ = aufnahme_der_ersten
    als_lehrperson(client, zweite_lehrperson)
    r = client.get(f"/lehrperson/aufnahmen/{aid}", headers=kopf)
    assert r.status_code == 404
    assert testdaten.WEBM_ANFANG not in r.content
    assert "Nicht gefunden" in r.text


@pytest.mark.parametrize("wert", ["999", "abc", "0", "-1", "99999999999999999999"])
def test_ungueltige_ids(client, lehrperson, auftraggeberin, wert):
    als_lehrperson(client, lehrperson)
    assert client.get(f"/lehrperson/aufnahmen/{wert}").status_code == 404
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    assert client.get(f"/verwaltung/aufnahmen/{wert}").status_code == 404


def test_datei_fehlt_404(client, db, einstellungen, lehrperson, aufnahme_der_ersten):
    aid, pfad = aufnahme_der_ersten
    pfad.unlink()
    als_lehrperson(client, lehrperson)
    assert client.get(f"/lehrperson/aufnahmen/{aid}").status_code == 404


def test_dateiname_manipuliert_404(client, db, lehrperson, auftraggeberin, aufnahme_der_ersten):
    aid, _ = aufnahme_der_ersten
    db.execute("UPDATE aufnahmen SET dateiname = '../reflexion.db' WHERE id = ?", (aid,))
    als_lehrperson(client, lehrperson)
    assert client.get(f"/lehrperson/aufnahmen/{aid}").status_code == 404
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    assert client.get(f"/verwaltung/aufnahmen/{aid}").status_code == 404


def test_auftraggeberin_hoert_alle(
    client, db, einstellungen, lehrperson, zweite_lehrperson, auftraggeberin
):
    ids = [
        testdaten.lege_aufnahme_an(db, k["id"], einstellungen.aufnahmen_verzeichnis)
        for k in (lehrperson, zweite_lehrperson)
    ]
    als_leitung(client, auftraggeberin)
    for aid in ids:
        r = client.get(f"/verwaltung/aufnahmen/{aid}")
        assert r.status_code == 200
        assert r.content == INHALT
        assert r.headers["content-type"] == "audio/webm"


def test_rollen_getrennt(client, lehrperson, auftraggeberin, aufnahme_der_ersten):
    aid, _ = aufnahme_der_ersten
    als_lehrperson(client, lehrperson)
    assert client.get(f"/verwaltung/aufnahmen/{aid}").status_code == 403
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    assert client.get(f"/lehrperson/aufnahmen/{aid}").status_code == 403
    client.cookies.clear()
    for pfad in (f"/lehrperson/aufnahmen/{aid}", f"/verwaltung/aufnahmen/{aid}"):
        r = client.get(pfad)
        assert r.status_code == 303
        assert r.headers["location"] == "/"
