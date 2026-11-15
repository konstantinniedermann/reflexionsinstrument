"""Zusatzinfo einer Runde: steht nach Frage 1 und erscheint erst, wenn Frage 1 beantwortet ist."""

from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, csrf_von

ZUSATZ = "Neue **Wendung** im Fall"
SATZ = "Sobald du deine Antwort gespeichert hast, folgt eine Zusatzinformation"


@pytest.fixture
def runde(db, client, lehrperson, heute_ist):
    """Runde mit Freitext f1, Freitext f2 und Skala f3 sowie Zusatzinfo; Lehrperson angemeldet."""
    rid, ids = testdaten.lege_runde_an(
        db,
        "Runde Eins",
        "2026-11-23",
        (("freitext", "Erste Frage"), ("freitext", "Zweite Frage"), ("skala", "Dritte Frage")),
        fallbeispiel="Fall",
        zusatzinfo=ZUSATZ,
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    return rid, ids


def _seite(client, rid, basis="/lehrperson"):
    return client.get(f"{basis}/runden/{rid}").text


def _post(client, rid, daten, basis="/lehrperson", follow=False):
    seite = f"{basis}/runden/{rid}"
    return client.post(
        seite, data={"csrf": csrf_von(client, seite), **daten}, follow_redirects=follow
    )


def _zu(text):
    return SATZ in text and "Wendung" not in text and "Zweite Frage" not in text


def _offen(text):
    return SATZ not in text and "<strong>Wendung</strong>" in text and "Zweite Frage" in text


def test_ohne_antwort_nur_erste_frage(runde, client):
    rid, (_, f2, f3) = runde
    text = _seite(client, rid)
    assert "Erste Frage" in text
    assert _zu(text)
    assert "Zusatzinformation mit weiteren Fragen." in text
    assert f'name="antwort_{f2}"' not in text
    assert f'name="antwort_{f3}"' not in text


def test_nach_speichern_offen_und_sprung(runde, client):
    rid, (f1, _, _) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "Mein Gedanke", "anker": f"frage-{f1}"})
    assert antwort.status_code == 303
    assert antwort.headers["location"].endswith("#zusatzinfo")
    text = _seite(client, rid)
    assert _offen(text)
    assert 'id="zusatzinfo"' in text
    assert text.index("Erste Frage") < text.index("Wendung") < text.index("Zweite Frage")


def test_spaeteres_speichern_springt_wie_bisher(runde, client):
    rid, (f1, f2, _) = runde
    _post(client, rid, {f"antwort_{f1}": "Mein Gedanke"})
    antwort = _post(client, rid, {f"antwort_{f2}": "Weiter", "anker": f"frage-{f2}"})
    assert antwort.headers["location"].endswith(f"#frage-{f2}")


def test_leere_erste_frage_bleibt_zu(runde, client):
    rid, (f1, _, _) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "   "})
    assert "#zusatzinfo" not in antwort.headers["location"]
    assert _zu(_seite(client, rid))


def test_skala_keine_angabe_gilt_nicht(db, client, lehrperson, heute_ist):
    rid, (f1, _) = testdaten.lege_runde_an(
        db,
        "Skala zuerst",
        "2026-11-23",
        (("skala", "Skala"), ("freitext", "Zweite Frage")),
        zusatzinfo=ZUSATZ,
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    _post(client, rid, {f"antwort_{f1}": ""})
    assert _zu(_seite(client, rid))
    _post(client, rid, {f"antwort_{f1}": "3"})
    assert _offen(_seite(client, rid))


def test_antwort_nur_als_aufnahme(runde, client, db, lehrperson, einstellungen):
    rid, (f1, _, _) = runde
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], None, aufnahme_id=aid)
    db.commit()
    assert _offen(_seite(client, rid))


def test_erste_geloescht_spaetere_beantwortet_bleibt_offen(runde, client):
    rid, (f1, f2, f3) = runde
    _post(client, rid, {f"antwort_{f1}": "Mein Gedanke"})
    _post(client, rid, {f"antwort_{f2}": "Weiter"})
    _post(client, rid, {f"antwort_{f1}": "", f"antwort_{f2}": "Weiter", f"antwort_{f3}": ""})
    text = _seite(client, rid)
    assert _offen(text)
    assert "Weiter" in text


def test_speichern_bei_verdeckten_fragen_loescht_nichts(runde, client, db, lehrperson):
    """Fehlende Felder bleiben unveraendert, auch wenn die Fragen verdeckt sind."""
    rid, (f1, f2, _) = runde
    testdaten.lege_antwort_an(db, f2, lehrperson["id"], "Alt")
    db.commit()
    _post(client, rid, {f"antwort_{f1}": ""})
    assert db.execute("SELECT text FROM antworten WHERE frage_id = ?", (f2,)).fetchone()[0] == "Alt"


def test_runde_ohne_zusatzinfo_zeigt_alles(db, client, lehrperson, heute_ist):
    rid, _ = testdaten.lege_runde_an(
        db, "Ohne", "2026-11-23", (("freitext", "Erste Frage"), ("freitext", "Zweite Frage"))
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = _seite(client, rid)
    assert "Zweite Frage" in text
    assert SATZ not in text
    assert 'id="zusatzinfo"' not in text


def test_zusatzinfo_mit_nur_einer_frage(db, client, lehrperson, heute_ist):
    rid, (f1,) = testdaten.lege_runde_an(
        db, "Eine", "2026-11-23", (("freitext", "Erste Frage"),), zusatzinfo=ZUSATZ
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = _seite(client, rid)
    assert SATZ in text
    assert "mit weiteren Fragen" not in text
    _post(client, rid, {f"antwort_{f1}": "Ja"})
    text = _seite(client, rid)
    assert "<strong>Wendung</strong>" in text
    assert SATZ not in text


def test_gast_sieht_zusatzinfo_nach_abschicken(runde, client):
    rid, (f1, _, _) = runde
    client.cookies.clear()
    assert _zu(_seite(client, rid, "/gast"))
    antwort = _post(client, rid, {f"antwort_{f1}": "Probe"}, basis="/gast")
    assert antwort.status_code == 200
    assert _offen(antwort.text)
    assert _zu(_seite(client, rid, "/gast"))
