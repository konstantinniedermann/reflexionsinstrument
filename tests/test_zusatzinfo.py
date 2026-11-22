"""Zusatzinfos einer Runde: jede steht nach ihrer Frage und erscheint Abschnitt für Abschnitt.

Ein Abschnitt geht auf, wenn alle Fragen des vorherigen beantwortet sind (Text, Skalawert oder
Aufnahme; «Keine Angabe» zählt nicht) oder eine Frage ab ihm schon eine Antwort hat.
"""

from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von

from app.routen.ohne_speichern import MELDUNG_GAST, MELDUNG_VORSCHAU

INFO_A = "Erste **Wendung** im Fall"
INFO_B = "Zweite **Lage** im Fall"
SATZ = "folgt eine Zusatzinformation"
EINE = "Sobald du die Frage oben beantwortet und gespeichert hast, folgt eine Zusatzinformation"
ALLE = "Sobald du alle Fragen oben beantwortet und gespeichert hast, folgt eine Zusatzinformation"


@pytest.fixture
def runde(db, client, lehrperson, heute_ist):
    """f1 Freitext · Info A · f2 Freitext · f3 Skala · Info B · f4 Freitext; Lehrperson angemeldet."""
    rid, ids = testdaten.lege_runde_an(
        db,
        "Runde Eins",
        "2026-11-23",
        (
            ("freitext", "Erste Frage"),
            ("freitext", "Zweite Frage"),
            ("skala", "Dritte Frage"),
            ("freitext", "Vierte Frage"),
        ),
        fallbeispiel="Fall",
        zusatzinfos={0: INFO_A, 2: INFO_B},
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


def _stufe(text):
    """1: nur Frage 1; 2: bis Frage 3 mit Info A; 3: alles mit Info B."""
    a = "<strong>Wendung</strong>" in text
    b = "<strong>Lage</strong>" in text
    if not a:
        assert "Zweite Frage" not in text and not b and "Vierte Frage" not in text
        return 1
    if not b:
        assert "Dritte Frage" in text and "Vierte Frage" not in text
        return 2
    assert "Vierte Frage" in text and SATZ not in text
    return 3


def test_ohne_antwort_nur_erste_frage(runde, client):
    rid, (_, f2, f3, f4) = runde
    text = _seite(client, rid)
    assert _stufe(text) == 1
    assert 'name="offen"' not in text  # Lehrperson: nur Gespeichertes zählt
    assert f"{EINE} mit weiteren Fragen." in text
    for f in (f2, f3, f4):
        assert f'name="antwort_{f}"' not in text


def test_abschnitt_fuer_abschnitt_mit_sprung(runde, client):
    rid, (f1, f2, f3, f4) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "Mein Gedanke", "anker": f"frage-{f1}"})
    assert antwort.headers["location"].endswith(f"#zusatzinfo-{f1}")
    text = _seite(client, rid)
    assert _stufe(text) == 2
    assert f'id="zusatzinfo-{f1}"' in text
    assert f"{ALLE} mit weiteren Fragen." in text
    assert text.index("Erste Frage") < text.index("Wendung") < text.index("Zweite Frage")

    # Nur ein Teil des Abschnitts: Info B bleibt zu, Sprung wie bisher zur Frage
    antwort = _post(client, rid, {f"antwort_{f2}": "Weiter", "anker": f"frage-{f2}"})
    assert antwort.headers["location"].endswith(f"#frage-{f2}")
    assert _stufe(_seite(client, rid)) == 2

    antwort = _post(client, rid, {f"antwort_{f2}": "Weiter", f"antwort_{f3}": "4"})
    assert antwort.headers["location"].endswith(f"#zusatzinfo-{f3}")
    text = _seite(client, rid)
    assert _stufe(text) == 3
    assert text.index("Dritte Frage") < text.index("Lage") < text.index("Vierte Frage")
    assert f'name="antwort_{f4}"' in text

    # Alles offen: der Knopf unten führt zur Startseite
    antwort = _post(client, rid, {f"antwort_{f4}": "Schluss"})
    assert antwort.headers["location"] == "/lehrperson?erledigt=runde_gespeichert"


def test_knopf_unten_ohne_neue_zusatzinfo_zur_startseite(runde, client):
    """Bleibt der nächste Abschnitt zu, ist nichts Neues zu sehen: zurück zur Startseite."""
    rid, (f1, f2, _, _) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "   "})
    assert antwort.headers["location"] == "/lehrperson?erledigt=runde_gespeichert"
    _post(client, rid, {f"antwort_{f1}": "Gedanke"})
    antwort = _post(client, rid, {f"antwort_{f2}": "Nur die zweite"})
    assert antwort.headers["location"] == "/lehrperson?erledigt=runde_gespeichert"
    assert _stufe(_seite(client, rid)) == 2


def test_skala_keine_angabe_gilt_nicht(runde, client):
    rid, (f1, f2, f3, _) = runde
    _post(client, rid, {f"antwort_{f1}": "Gedanke"})
    _post(client, rid, {f"antwort_{f2}": "Weiter", f"antwort_{f3}": ""})
    assert _stufe(_seite(client, rid)) == 2


def test_skala_als_erste_frage(db, client, lehrperson, heute_ist):
    rid, (f1, _) = testdaten.lege_runde_an(
        db,
        "Skala zuerst",
        "2026-11-23",
        (("skala", "Skala"), ("freitext", "Zweite Frage")),
        zusatzinfos={0: INFO_A},
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    _post(client, rid, {f"antwort_{f1}": ""})
    assert "<strong>Wendung</strong>" not in _seite(client, rid)
    _post(client, rid, {f"antwort_{f1}": "3"})
    assert "<strong>Wendung</strong>" in _seite(client, rid)


def test_leere_erste_frage_bleibt_zu(runde, client):
    rid, (f1, _, _, _) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "   "})
    assert "#zusatzinfo" not in antwort.headers["location"]
    assert _stufe(_seite(client, rid)) == 1


def test_antwort_nur_als_aufnahme(runde, client, db, lehrperson, einstellungen):
    rid, (f1, _, _, _) = runde
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], None, aufnahme_id=aid)
    db.commit()
    assert _stufe(_seite(client, rid)) == 2


def test_fruehere_geloescht_spaetere_beantwortet_bleibt_offen(runde, client, db, lehrperson):
    rid, (f1, f2, f3, f4) = runde
    testdaten.lege_antwort_an(db, f4, lehrperson["id"], "Schluss")
    db.commit()
    text = _seite(client, rid)
    assert _stufe(text) == 3
    assert "Schluss" in text
    _post(client, rid, {f"antwort_{f1}": "", f"antwort_{f2}": "", f"antwort_{f3}": ""})
    assert _stufe(_seite(client, rid)) == 3


def test_antwort_im_zweiten_abschnitt_haelt_ihn_offen(runde, client, db, lehrperson):
    rid, (_, f2, _, _) = runde
    testdaten.lege_antwort_an(db, f2, lehrperson["id"], "Alt")
    db.commit()
    assert _stufe(_seite(client, rid)) == 2


def test_speichern_bei_verdeckten_fragen_loescht_nichts(runde, client, db, lehrperson):
    """Fehlende Felder bleiben unveraendert, auch wenn die Fragen verdeckt sind."""
    rid, (f1, _, _, f4) = runde
    testdaten.lege_antwort_an(db, f4, lehrperson["id"], "Alt")
    db.commit()
    _post(client, rid, {f"antwort_{f1}": ""})
    assert db.execute("SELECT text FROM antworten WHERE frage_id = ?", (f4,)).fetchone()[0] == "Alt"


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
    assert 'id="zusatzinfo' not in text


def test_zusatzinfo_nach_der_letzten_frage(db, client, lehrperson, heute_ist):
    rid, (f1,) = testdaten.lege_runde_an(
        db, "Eine", "2026-11-23", (("freitext", "Erste Frage"),), zusatzinfos={0: INFO_A}
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = _seite(client, rid)
    assert f"{EINE}." in text
    antwort = _post(client, rid, {f"antwort_{f1}": "Ja"})
    assert antwort.headers["location"].endswith(f"#zusatzinfo-{f1}")
    text = _seite(client, rid)
    assert "<strong>Wendung</strong>" in text
    assert SATZ not in text


def test_gast_zusatzinfo_nach_der_letzten_frage(db, client, heute_ist):
    """Der leere Schlussabschnitt hat kein Feld: das Formular meldet, was schon offen war."""
    rid, (f1,) = testdaten.lege_runde_an(
        db, "Eine", "2026-11-23", (("freitext", "Erste Frage"),), zusatzinfos={0: INFO_A}
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    assert 'name="offen" value="1"' in _seite(client, rid, "/gast")
    antwort = _post(client, rid, {f"antwort_{f1}": "Ja", "offen": "1"}, basis="/gast")
    assert antwort.status_code == 200
    assert "<strong>Wendung</strong>" in antwort.text
    assert 'name="offen" value="2"' in antwort.text
    antwort = _post(client, rid, {f"antwort_{f1}": "Ja", "offen": "2"}, basis="/gast")
    assert antwort.headers["location"] == "/gast?erledigt=nicht_gespeichert"
    # Unsinnige Werte zählen nicht
    for offen in ("x", "-1", "9" * 30):
        antwort = _post(client, rid, {f"antwort_{f1}": "Ja", "offen": offen}, basis="/gast")
        assert antwort.status_code == 200, offen


def test_gast_spielt_abschnitte_durch(runde, client):
    rid, (f1, f2, f3, f4) = runde
    client.cookies.clear()
    assert _stufe(_seite(client, rid, "/gast")) == 1
    antwort = _post(client, rid, {f"antwort_{f1}": "Probe"}, basis="/gast")
    assert antwort.status_code == 200
    assert _stufe(antwort.text) == 2
    daten = {f"antwort_{f1}": "Probe", f"antwort_{f2}": "Mehr", f"antwort_{f3}": "2"}
    assert _stufe(_post(client, rid, daten, basis="/gast").text) == 3
    assert _stufe(_seite(client, rid, "/gast")) == 1
    # Alles offen: der Knopf unten führt wie bei der Lehrperson zur Startseite
    antwort = _post(client, rid, daten | {f"antwort_{f4}": "Ende"}, basis="/gast")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/gast?erledigt=nicht_gespeichert"
    start = client.get(antwort.headers["location"]).text
    assert f'role="status">{MELDUNG_GAST}<' in start
    # Ohne neuen Abschnitt (Frage 1 leer) ebenso; ein kleiner Knopf bleibt auf der Seite
    antwort = _post(client, rid, {f"antwort_{f1}": ""}, basis="/gast")
    assert antwort.headers["location"] == "/gast?erledigt=nicht_gespeichert"
    antwort = _post(client, rid, {f"antwort_{f1}": "", "anker": f"frage-{f1}"}, basis="/gast")
    assert antwort.status_code == 200
    assert MELDUNG_GAST in antwort.text


def test_aufnahme_auf_erste_frage_springt_zur_zusatzinfo(runde, client):
    rid, (f1, _, _, _) = runde
    seite = f"/lehrperson/runden/{rid}/fragen/{f1}/aufnahme"
    datei = {"aufnahme": ("aufnahme.webm", testdaten.WEBM_ANFANG + bytes(60), "audio/webm")}
    antwort = client.post(
        seite, files=datei, data={"csrf": csrf_von(client, seite)}, follow_redirects=False
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"].endswith(f"#zusatzinfo-{f1}")
    assert _stufe(_seite(client, rid)) == 2
    # zweite Aufnahme (ersetzen): Zusatzinfo war schon offen, Sprung wie bisher zur Frage
    antwort = client.post(
        seite, files=datei, data={"csrf": csrf_von(client, seite)}, follow_redirects=False
    )
    assert antwort.headers["location"].endswith(f"#frage-{f1}")


def test_fehlerseite_der_lehrperson_zeigt_nur_gespeichertes(runde, client):
    rid, (f1, _, _, _) = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "x" * 20_001})
    assert antwort.status_code == 400
    assert _stufe(antwort.text) == 1


def test_vorschau_zeigt_zusatzinfo_nach_abschicken(runde, client, auftraggeberin):
    rid, (f1, f2, _, _) = runde
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    basis = "/verwaltung/vorschau/2026-11-23"
    assert _stufe(_seite(client, rid, basis)) == 1
    antwort = _post(client, rid, {f"antwort_{f1}": "Probe"}, basis=basis)
    assert antwort.status_code == 200
    assert _stufe(antwort.text) == 2
    antwort = _post(client, rid, {f"antwort_{f1}": "Probe", f"antwort_{f2}": "x"}, basis=basis)
    assert antwort.headers["location"] == f"{basis}?erledigt=nicht_gespeichert"
    start = client.get(antwort.headers["location"]).text
    assert f'role="status">{MELDUNG_VORSCHAU}<' in start
    # Andere Werte von «erledigt» zeigen nichts
    assert 'role="status"' not in client.get(f"{basis}?erledigt=gespeichert").text
