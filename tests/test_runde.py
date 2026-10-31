import re
from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, anmelden, csrf_von

from app.texte import REGISTER


@pytest.fixture
def runde(db, client, lehrperson, heute_ist):
    """Runde am 23.11. mit Freitext f1 und Skala f2; Lehrperson angemeldet."""
    rid, (f1, f2) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    return rid, f1, f2


def _post(client, rid, daten, pfad=""):
    seite = f"/lehrperson/runden/{rid}"
    return client.post(
        seite + pfad, data={"csrf": csrf_von(client, seite), **daten}, follow_redirects=False
    )


def _antworten(db, konto_id):
    return [
        tuple(z)
        for z in db.execute(
            "SELECT frage_id, text, skalawert FROM antworten WHERE konto_id = ? ORDER BY frage_id",
            (konto_id,),
        )
    ]


def _feld(text, name):
    treffer = re.search(rf'<textarea[^>]*name="{name}"[^>]*>\s*(.*?)</textarea>', text, re.DOTALL)
    assert treffer, name
    return treffer.group(1)


def _feld_tag(text, name):
    treffer = re.search(rf'<textarea[^>]*name="{name}"[^>]*>', text)
    assert treffer, name
    return treffer.group(0)


def _gewaehlt(text, name):
    treffer = re.findall(rf'<input type="radio" name="{name}" value="([^"]*)" checked>', text)
    assert len(treffer) == 1, treffer
    return treffer[0]


def test_nicht_freigeschaltet_404(client, lehrperson, db, heute_ist):
    rid, (f1, _) = testdaten.lege_runde_an(db, "Spaet", "2026-11-30")
    db.commit()
    heute_ist(date(2026, 11, 29))
    als_lehrperson(client, lehrperson)
    vorher = testdaten.abzug(db)
    csrf = csrf_von(client, "/lehrperson/info")
    seite = f"/lehrperson/runden/{rid}"
    antworten = [
        client.get(seite),
        client.post(seite, data={"csrf": csrf, f"antwort_{f1}": "x"}),
        client.get(seite + "/loeschen"),
        client.post(seite + "/loeschen", data={"csrf": csrf}),
    ]
    for antwort in antworten:
        assert antwort.status_code == 404
        assert "Nicht gefunden" in antwort.text
    assert testdaten.abzug(db) == vorher
    heute_ist(date(2026, 11, 30))
    assert client.get(seite).status_code == 200


@pytest.mark.parametrize("wert", ["999", "abc", "0", "-1", "99999999999999999999"])
def test_ungueltige_ids(client, lehrperson, wert):
    als_lehrperson(client, lehrperson)
    assert client.get(f"/lehrperson/runden/{wert}").status_code == 404
    assert client.get(f"/lehrperson/runden/{wert}/loeschen").status_code == 404


def test_post_unbekannte_runde(client, lehrperson):
    als_lehrperson(client, lehrperson)
    csrf = csrf_von(client, "/lehrperson/info")
    assert client.post("/lehrperson/runden/999", data={"csrf": csrf}).status_code == 404


def test_anzeige(db, client, lehrperson, heute_ist):
    rid, (f1, _, f3) = testdaten.lege_runde_an(
        db,
        "Runde Eins",
        "2026-11-23",
        (("freitext", "Frage **y**"), ("freitext", "Zweite"), ("skala", "Skala")),
        fallbeispiel="Ein **x** Fall",
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = client.get(f"/lehrperson/runden/{rid}").text
    assert "<strong>x</strong>" in text
    assert "Frage **y**" in text and "<strong>y</strong>" not in text
    assert re.search(rf'<textarea[^>]*name="antwort_{f1}"[^>]*id="frage-{f1}"', text)
    assert 'maxlength="20000"' in text
    assert len(re.findall(rf'name="antwort_{f3}" value="[1-5]"', text)) == 5
    assert "Keine Angabe" in text
    assert _gewaehlt(text, f"antwort_{f3}") == ""
    assert REGISTER["hinweis_tagebuch"].vorschlag[:40] in text
    assert text.count('name="anker" value="frage-') == 2
    assert text.count('name="anker" value="aufnahme-') == 2  # #17: Antwort einsprechen
    assert f'name="anker" value="frage-{f1}"' in text
    assert len(re.findall(r'class="knopf"[^>]*>Speichern<', text)) == 1
    assert "Mo 23.11." in text
    assert "Zuletzt gespeichert" not in text
    assert "löschen" not in text


def test_speichern_und_anzeigen(runde, client, db, lehrperson):
    rid, f1, f2 = runde
    antwort = _post(client, rid, {f"antwort_{f1}": "Text A", f"antwort_{f2}": "4"})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"/lehrperson/runden/{rid}?erledigt=gespeichert"
    text = client.get(antwort.headers["location"]).text
    assert "Gespeichert." in text
    assert 'role="status"' in text
    assert _feld(text, f"antwort_{f1}") == "Text A"
    assert _gewaehlt(text, f"antwort_{f2}") == "4"
    assert "Zuletzt gespeichert:" in text
    assert "Meine Antworten zu dieser Runde löschen" in text


def test_unterbrochene_eingabe(runde, client, lehrperson):
    rid, f1, _ = runde
    assert _post(client, rid, {f"antwort_{f1}": "Text A"}).status_code == 303
    client.cookies.clear()
    assert anmelden(client, lehrperson["benutzername"], lehrperson["passwort"]).status_code == 303
    assert _feld(client.get(f"/lehrperson/runden/{rid}").text, f"antwort_{f1}") == "Text A"


def test_leeren_loescht_antwort(runde, client, db, lehrperson):
    rid, f1, f2 = runde
    _post(client, rid, {f"antwort_{f1}": "Text A", f"antwort_{f2}": "4"})
    _post(client, rid, {f"antwort_{f1}": "  ", f"antwort_{f2}": ""})
    assert _antworten(db, lehrperson["id"]) == []


def test_veraltetes_formular_laesst_fehlendes_unberuehrt(runde, client, db, lehrperson):
    rid, f1, f2 = runde
    _post(client, rid, {f"antwort_{f1}": "Text A", f"antwort_{f2}": "4"})
    _post(client, rid, {f"antwort_{f1}": "Text B"})
    assert _antworten(db, lehrperson["id"]) == [(f1, "Text B", None), (f2, None, 4)]


def test_anker(runde, client):
    rid, f1, _ = runde
    ziel = f"/lehrperson/runden/{rid}?erledigt=gespeichert"
    antwort = _post(client, rid, {f"antwort_{f1}": "x", "anker": f"frage-{f1}"})
    assert antwort.headers["location"] == f"{ziel}#frage-{f1}"
    for anker in ["frage-1x", "javascript:x", "frage-" + "1" * 11, "frage-", "x"]:
        antwort = _post(client, rid, {"anker": anker})
        assert antwort.headers["location"] == ziel, anker


def test_anker_aufnahme(runde, client, db, lehrperson):
    rid, f1, f2 = runde
    _, (fremd, _) = testdaten.lege_runde_an(db, "Andere", "2026-11-23")
    db.commit()
    antwort = _post(client, rid, {f"antwort_{f1}": "Text A", "anker": f"aufnahme-{f1}"})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"/lehrperson/runden/{rid}/fragen/{f1}/aufnahme"
    assert _antworten(db, lehrperson["id"]) == [(f1, "Text A", None)]
    ziel = f"/lehrperson/runden/{rid}?erledigt=gespeichert"
    for nummer in (f2, fremd):
        assert _post(client, rid, {"anker": f"aufnahme-{nummer}"}).headers["location"] == ziel


def test_meldungen(runde, client):
    rid, _, _ = runde
    seite = f"/lehrperson/runden/{rid}"
    assert "Die Aufnahme wurde gelöscht." in client.get(seite + "?erledigt=aufnahme_geloescht").text
    text = client.get(seite + "?erledigt=<script>").text
    assert "<script>" not in text and "&lt;script" not in text


def test_fehler_400_behaelt_eingaben(db, client, lehrperson, heute_ist):
    rid, (f1, f2, f3) = testdaten.lege_runde_an(
        db,
        "Runde Eins",
        "2026-11-23",
        (("freitext", "A"), ("skala", "B"), ("freitext", "C")),
    )
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    vorher = testdaten.abzug(db)
    antwort = _post(
        client, rid, {f"antwort_{f1}": "Neu", f"antwort_{f2}": "7", f"antwort_{f3}": "Dritte"}
    )
    assert antwort.status_code == 400
    text = antwort.text
    assert "Bitte prüfe die markierten Felder." in text
    assert "Bitte einen Wert von 1 bis 5 wählen." in text
    assert f'aria-describedby="fehler-antwort_{f2}"' in text
    assert f'id="fehler-antwort_{f2}"' in text
    # Alle sechs Knoepfe der Skala (1 bis 5 und «Keine Angabe») sind markiert.
    assert text.count(f'name="antwort_{f2}" aria-invalid="true"') == 6
    assert "aria-invalid" not in _feld_tag(text, f"antwort_{f1}")
    assert _feld(text, f"antwort_{f1}") == "Neu"
    assert _feld(text, f"antwort_{f3}") == "Dritte"
    assert testdaten.abzug(db) == vorher

    antwort = _post(
        client, rid, {f"antwort_{f1}": "x" * 20_001, f"antwort_{f2}": "3", f"antwort_{f3}": "Z"}
    )
    assert antwort.status_code == 400
    assert _gewaehlt(antwort.text, f"antwort_{f2}") == "3"
    assert _feld(antwort.text, f"antwort_{f3}") == "Z"
    assert "Der Text ist zu lang" in antwort.text
    assert f'aria-invalid="true" aria-describedby="fehler-antwort_{f1}"' in _feld_tag(
        antwort.text, f"antwort_{f1}"
    )
    assert testdaten.abzug(db) == vorher


def test_post_nach_datumsaenderung_404(runde, client, db, lehrperson):
    rid, f1, _ = runde
    seite = f"/lehrperson/runden/{rid}"
    assert client.get(seite).status_code == 200
    csrf = csrf_von(client, seite)
    db.execute("UPDATE runden SET freischaltdatum = '2026-12-31'")
    db.commit()
    antwort = client.post(seite, data={"csrf": csrf, f"antwort_{f1}": "x"})
    assert antwort.status_code == 404
    assert _antworten(db, lehrperson["id"]) == []


def test_veraltetes_formular_nach_typwechsel(runde, client, db, lehrperson):
    rid, f1, f2 = runde
    seite = f"/lehrperson/runden/{rid}"
    assert client.get(seite).status_code == 200
    db.execute("UPDATE fragen SET typ = 'skala' WHERE id = ?", (f1,))
    db.execute("UPDATE fragen SET typ = 'freitext' WHERE id = ?", (f2,))
    db.commit()
    antwort = _post(client, rid, {f"antwort_{f1}": "Text A", f"antwort_{f2}": "4"})
    assert antwort.status_code == 400
    assert "Bitte einen Wert von 1 bis 5 wählen." in antwort.text
    assert f'id="fehler-antwort_{f1}"' in antwort.text
    assert _antworten(db, lehrperson["id"]) == []
    # Umgekehrt: «4» zur Frage, die jetzt Freitext ist, wird sichtbar als Text gespeichert.
    assert _post(client, rid, {f"antwort_{f2}": "4"}).status_code == 303
    assert _antworten(db, lehrperson["id"]) == [(f2, "4", None)]


def test_feld_anderer_runde_ignoriert(runde, client, db, lehrperson):
    rid, f1, _ = runde
    _, (fremd, _) = testdaten.lege_runde_an(db, "Andere", "2026-11-23")
    db.commit()
    _post(client, rid, {f"antwort_{f1}": "A", f"antwort_{fremd}": "Fremd", "antwort_x": "y"})
    assert _antworten(db, lehrperson["id"]) == [(f1, "A", None)]


def test_runde_ohne_fragen(db, client, lehrperson, heute_ist):
    rid, _ = testdaten.lege_runde_an(db, "Leer", "2026-11-23", fragen=())
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = client.get(f"/lehrperson/runden/{rid}").text
    assert "Zu dieser Runde gibt es noch keine Fragen." in text
    assert 'name="anker"' not in text and '<form class="formular"' not in text


def test_runde_loeschen(runde, client, db, lehrperson, zweite_lehrperson):
    rid, f1, f2 = runde
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"], "Bens Antwort")
    db.commit()
    _post(client, rid, {f"antwort_{f1}": "A", f"antwort_{f2}": "2"})
    seite = f"/lehrperson/runden/{rid}/loeschen"
    text = client.get(seite).text
    assert "Alle deine Antworten zu" in text and "Runde Eins" in text
    assert "Endgültig löschen" in text and "Abbrechen" in text
    antwort = client.post(seite, data={"csrf": csrf_von(client, seite)})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/lehrperson/eintraege?erledigt=geloescht"
    assert _antworten(db, lehrperson["id"]) == []
    assert _antworten(db, zweite_lehrperson["id"]) == [(f1, "Bens Antwort", None)]


def test_fremde_antworten_unsichtbar(runde, client, db, zweite_lehrperson):
    rid, f1, f2 = runde
    testdaten.lege_antwort_an(db, f1, zweite_lehrperson["id"], "Geheimantwort", None)
    testdaten.lege_antwort_an(db, f2, zweite_lehrperson["id"], None, 5)
    db.commit()
    text = client.get(f"/lehrperson/runden/{rid}").text
    assert "Geheimantwort" not in text
    assert _gewaehlt(text, f"antwort_{f2}") == ""
    assert "Zuletzt gespeichert" not in text


def test_ausgabe_escapt(runde, client, db, lehrperson):
    rid, f1, _ = runde
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], "</textarea><script>x</script> **f**")
    db.commit()
    text = client.get(f"/lehrperson/runden/{rid}").text
    assert "&lt;script&gt;" in text and "**f**" in text
    assert "<script>" not in text and "<strong>f" not in text
