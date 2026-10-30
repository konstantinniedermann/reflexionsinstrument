import re
from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung

from app.routen.verwaltung_vorschau import band_vorschau
from app.texte import REGISTER, speichere_text

V = "/verwaltung/vorschau"


def _erster_tag(db, tag="2026-11-23"):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', ?)", (tag,))
    db.commit()


@pytest.fixture
def leitung(client, auftraggeberin, heute_ist):
    heute_ist(date(2026, 11, 16))
    return als_leitung(client, auftraggeberin)


def test_band_vorschau():
    assert band_vorschau(date(2026, 11, 30), date(2026, 11, 23), []) == (
        "Vorschau: So sieht es eine Lehrperson am Mo 30.11.2026 (Woche 2). "
        "Es wird nichts gespeichert."
    )
    assert "(Woche" not in band_vorschau(date(2026, 11, 30), None, [])
    assert "(Woche" not in band_vorschau(date(2026, 11, 30), date(2026, 12, 1), [])
    assert band_vorschau(date(2026, 11, 30), None, ["Begrüssung", "Hinweis im Tagebuch"]).endswith(
        "\nNoch Vorschläge statt deiner Texte: Begrüssung, Hinweis im Tagebuch."
    )


def test_vorschau_start_am_tag(leitung, db):
    _erster_tag(db)
    testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_runde_an(db, "Runde Zwei", "2026-12-07")
    db.commit()
    text = leitung.get(f"{V}/2026-11-30").text
    assert leitung.get(f"{V}/2026-11-30").status_code == 200
    assert "Woche 2" in text
    assert "Runde Eins" in text
    assert "Nächste Runde ab Mo 07.12." in text
    assert "Runde Zwei" not in text
    assert "Willkommen" in text
    text = leitung.get(f"{V}/2026-12-07").text
    assert "Runde Eins" in text and "Runde Zwei" in text
    assert "Woche 3" in text


def test_vorschau_aktueller_impuls(leitung, db):
    _erster_tag(db)
    testdaten.lege_impuls_an(db, "Impuls A", "2026-11-23")
    testdaten.lege_impuls_an(db, "Impuls B", "2026-12-07")
    db.commit()
    text = leitung.get(f"{V}/2026-11-30").text
    assert "Impuls A" in text and "Impuls B" not in text
    assert "Impuls B" in leitung.get(f"{V}/2026-12-07").text


def test_vorschau_kuenftige_runde(leitung, db):
    _erster_tag(db)
    rid, _ = testdaten.lege_runde_an(
        db, "Runde Zwei", "2026-12-07", fallbeispiel="Fall Zwei", fragen=(("freitext", "Frage A"),)
    )
    db.commit()
    antwort = leitung.get(f"{V}/2026-12-07/runden/{rid}")
    assert antwort.status_code == 200
    assert "Fall Zwei" in antwort.text and "Frage A" in antwort.text
    assert leitung.get(f"{V}/2026-12-06/runden/{rid}").status_code == 404


def test_vorschau_seiten(leitung, db):
    _erster_tag(db)
    iid = testdaten.lege_impuls_an(db, "Impuls A", "2026-12-07")
    spaet = testdaten.lege_impuls_an(db, "Impuls C", "2026-12-14")
    lid = testdaten.lege_leitfrage_an(db, "Leitfrage A")
    db.commit()
    for pfad in (
        "/info",
        "/tagebuch/neu",
        "/tagebuch/neu/frei",
        f"/tagebuch/neu/impuls/{iid}",
        f"/tagebuch/neu/leitfrage/{lid}",
    ):
        assert leitung.get(f"{V}/2026-12-07{pfad}").status_code == 200, pfad
    assert leitung.get(f"{V}/2026-12-07/tagebuch/neu/impuls/{spaet}").status_code == 404
    assert leitung.get(f"{V}/2026-12-07/tagebuch/neu/leitfrage/999").status_code == 404


@pytest.mark.parametrize(
    "x",
    ["2026-13-01", "2026-02-30", "abc", "20261130", "2026-11-30%0A", "1" * 50, "2019-12-31"]
    + ["2100-01-01"],
)
def test_vorschau_ungueltiges_datum(leitung, x):
    assert leitung.get(f"{V}/{x}").status_code == 404
    assert leitung.get(f"{V}/{x}/info").status_code == 404


def test_vorschau_links_tragen_tag(leitung, db):
    _erster_tag(db)
    rid, _ = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    db.commit()
    tag = f"{V}/2026-11-30"
    for seite in (tag, f"{tag}/runden/{rid}"):
        text = leitung.get(seite).text
        ziele = re.findall(r'(?:href|action)="([^"]*)"', text)
        assert ziele
        for z in ziele:
            assert z in (V, "/abmelden") or z.startswith(("/static/", tag)), (seite, z)
            assert not z.startswith(("/lehrperson", "/gast")), (seite, z)
    assert f'action="{tag}/runden/{rid}"' in leitung.get(f"{tag}/runden/{rid}").text


def test_vorschau_band_und_ausgang(leitung, db):
    _erster_tag(db)
    text = leitung.get(f"{V}/2026-11-30").text
    assert "Vorschau: So sieht es eine Lehrperson am Mo 30.11.2026 (Woche 2)." in text
    assert (
        "Noch Vorschläge statt deiner Texte: Begrüssung, Hinweis im Tagebuch, Wer sieht was" in text
    )
    assert f'href="{V}"' in text and "Vorschau beenden" in text
    for k in REGISTER:
        speichere_text(db, k, "Text")
    db.commit()
    assert "Noch Vorschläge" not in leitung.get(f"{V}/2026-11-30").text


def test_vorschau_nur_auftraggeberin(client, lehrperson, heute_ist):
    heute_ist(date(2026, 11, 16))
    antwort = client.get(f"{V}/2026-11-30")
    assert antwort.status_code == 303 and antwort.headers["location"] == "/"
    als_lehrperson(client, lehrperson)
    assert client.get(f"{V}/2026-11-30").status_code == 403
