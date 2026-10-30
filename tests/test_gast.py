"""Gast-Ansicht (#19): ohne Anmeldung, nur freigeschaltete Inhalte, speichert nichts."""

import re
from collections import deque
from datetime import date
from pathlib import Path

import pytest
import testdaten
from conftest import anmelden, csrf_von

from app.routen.ohne_speichern import MELDUNG_GAST

ZIEL = re.compile(r'(?:href|action)="([^"]*)"')
VERBOTEN = ("/lehrperson", "/verwaltung", "/eintraege", "/aufnahmen")
# Die Startseite hat ohne Sitzung kein Formular; das csrf-Feld kommt von einer Formularseite.
FORMULAR = "/gast/tagebuch/neu/frei"


@pytest.fixture
def inhalte(db, einstellungen, lehrperson, heute_ist):
    heute_ist(date(2026, 11, 24))
    offen, (f1, f2) = testdaten.lege_runde_an(
        db,
        "Runde Offen",
        "2026-11-23",
        fragen=(("freitext", "Frage Text"), ("skala", "Frage Skala")),
        fallbeispiel="Fall Offen",
    )
    geheim, _ = testdaten.lege_runde_an(db, "Runde Geheim", "2026-11-30")
    impuls = testdaten.lege_impuls_an(db, "Impuls Offen", "2026-11-23")
    impuls_geheim = testdaten.lege_impuls_an(db, "Impuls Geheim", "2026-11-30")
    leitfrage = testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    db.execute(
        "INSERT INTO info_abschnitte (titel, inhalt, reihenfolge) "
        "VALUES ('Abschnitt Eins', 'Text Eins', 1)"
    )
    konto = lehrperson["id"]
    testdaten.lege_antwort_an(db, f1, konto, "Antwort Geheim")
    testdaten.lege_eintrag_an(db, konto, "frei", "Eintrag Geheim")
    testdaten.lege_eintrag_an(db, konto, "impuls", "Eintrag Geheim Impuls", impuls_id=impuls)
    testdaten.lege_eintrag_an(
        db, konto, "leitfragen", "Eintrag Geheim Leitfrage", leitfrage_id=leitfrage
    )
    aufnahme = testdaten.lege_aufnahme_an(db, konto, einstellungen.aufnahmen_verzeichnis)
    testdaten.lege_eintrag_an(db, konto, "aufnahme", None, aufnahme_id=aufnahme)
    db.commit()
    return {
        "offen": offen,
        "geheim": geheim,
        "f1": f1,
        "f2": f2,
        "impuls": impuls,
        "impuls_geheim": impuls_geheim,
        "leitfrage": leitfrage,
    }


@pytest.fixture
def gast_seiten(inhalte):
    """Alle sieben GET-Seiten der Gast-Ansicht, mit den IDs aus `inhalte`."""
    i = inhalte
    return [
        "/gast",
        "/gast/info",
        f"/gast/runden/{i['offen']}",
        "/gast/tagebuch/neu",
        "/gast/tagebuch/neu/frei",
        f"/gast/tagebuch/neu/impuls/{i['impuls']}",
        f"/gast/tagebuch/neu/leitfrage/{i['leitfrage']}",
    ]


def test_gast_seiten_ohne_anmeldung(client, gast_seiten):
    for pfad in gast_seiten:
        antwort = client.get(pfad)
        assert antwort.status_code == 200, pfad
        assert "Ansicht ohne Speichern." in antwort.text, pfad
        assert re.search(r'href="/"[^>]*>\s*Anmelden', antwort.text), pfad
    text = client.get("/gast").text
    assert "Willkommen" in text
    assert "Runde Offen" in text
    assert "Impuls Offen" in text


def test_gast_nicht_freigeschaltet(client, inhalte, gast_seiten, heute_ist):
    for pfad in gast_seiten:
        assert "Runde Geheim" not in client.get(pfad).text, pfad
    assert "Nächste Runde ab Mo 30.11." in client.get("/gast").text
    geheim = f"/gast/runden/{inhalte['geheim']}"
    assert client.get(geheim).status_code == 404
    csrf = csrf_von(client, FORMULAR)
    antwort = client.post(geheim, data={"csrf": csrf, f"antwort_{inhalte['f1']}": "x"})
    assert antwort.status_code == 404
    assert "Impuls Geheim" not in client.get("/gast").text
    assert "Impuls Geheim" not in client.get("/gast/tagebuch/neu").text
    impuls = f"/gast/tagebuch/neu/impuls/{inhalte['impuls_geheim']}"
    assert client.get(impuls).status_code == 404
    assert client.post(impuls, data={"csrf": csrf, "text": "x"}).status_code == 404
    heute_ist(date(2026, 11, 30))
    assert client.get(geheim).status_code == 200


def test_gast_zeigt_keine_eintraege(client, inhalte, gast_seiten):
    for pfad in gast_seiten:
        text = client.get(pfad).text
        for verboten in (
            "Antwort Geheim",
            "Eintrag Geheim",
            "Anna Beispiel",
            "/aufnahmen/",
            "Abmelden",
            "data-entwurf",
        ):
            assert verboten not in text, (pfad, verboten)
    text = client.get(f"/gast/runden/{inhalte['offen']}").text
    assert re.search(rf'<textarea name="antwort_{inhalte["f1"]}"[^>]*>\s*</textarea>', text)


def test_gast_kein_weg_zu_eintraegen(client, inhalte):
    besucht, offen = set(), deque(["/gast"])
    while offen:
        pfad = offen.popleft()
        if pfad in besucht:
            continue
        besucht.add(pfad)
        antwort = client.get(pfad)
        assert antwort.status_code == 200, pfad
        for z in ZIEL.findall(antwort.text):
            assert z == "/" or z.startswith(("/gast", "/static/")), (pfad, z)
            assert not any(v in z for v in VERBOTEN), (pfad, z)
            if z.startswith("/gast") and z not in besucht:
                offen.append(z)
    assert {
        "/gast",
        "/gast/info",
        f"/gast/runden/{inhalte['offen']}",
        "/gast/tagebuch/neu",
        "/gast/tagebuch/neu/frei",
    } <= besucht
    for pfad in ("/gast/eintraege", "/gast/tagebuch/1", "/gast/tagebuch/1/loeschen"):
        assert client.get(pfad).status_code == 404, pfad
    assert client.get("/gast/aufnahmen/1").status_code == 404


def test_gast_speichern_verworfen(client, inhalte):
    f1, f2 = inhalte["f1"], inhalte["f2"]
    url = f"/gast/runden/{inhalte['offen']}"
    csrf = csrf_von(client, FORMULAR)
    antwort = client.post(
        url, data={"csrf": csrf, f"antwort_{f1}": "Mein Text", f"antwort_{f2}": "3"}
    )
    assert antwort.status_code == 200
    assert re.search(r'role="status"[^>]*>[^<]*' + re.escape(MELDUNG_GAST), antwort.text)
    assert re.search(r"<textarea[^>]*>\s*Mein Text", antwort.text)
    assert re.search(
        r'<input[^>]*value="3"[^>]*checked|<input[^>]*checked[^>]*value="3"', antwort.text
    )
    antwort = client.post(url, data={"csrf": csrf, f"antwort_{f2}": "7"})
    assert antwort.status_code == 400
    assert MELDUNG_GAST not in antwort.text
    antwort = client.post(url, data={"csrf": csrf, f"antwort_{f1}": "<script>x</script>"})
    assert antwort.status_code == 200
    assert "&lt;script&gt;x&lt;/script&gt;" in antwort.text
    assert "<script>x" not in antwort.text
    antwort = client.post(
        f"/gast/tagebuch/neu/leitfrage/{inhalte['leitfrage']}",
        data={"csrf": csrf, "text": "Notiz"},
    )
    assert antwort.status_code == 200
    assert MELDUNG_GAST in antwort.text
    assert re.search(r"<textarea[^>]*>\s*Notiz", antwort.text)


def test_gast_langer_text_bleibt_stehen(client, inhalte, db):
    vorher = testdaten.abzug(db)
    antwort = client.post(
        "/gast/tagebuch/neu/frei",
        data={"csrf": csrf_von(client, FORMULAR), "text": "Schöne Grüsse, äöü. " * 1000},
    )
    assert antwort.status_code == 200
    assert MELDUNG_GAST in antwort.text
    assert re.search(r"<textarea[^>]*>\s*Schöne Grüsse", antwort.text)
    assert testdaten.abzug(db) == vorher


def _durchgang(client, i, seiten):
    for pfad in seiten:
        assert client.get(pfad).status_code == 200, pfad
    csrf = csrf_von(client, FORMULAR)
    runde = f"/gast/runden/{i['offen']}"
    tagebuch = [
        "/gast/tagebuch/neu/frei",
        f"/gast/tagebuch/neu/impuls/{i['impuls']}",
        f"/gast/tagebuch/neu/leitfrage/{i['leitfrage']}",
    ]
    gueltig = {f"antwort_{i['f1']}": "Mein Text", f"antwort_{i['f2']}": "3"}
    assert client.post(runde, data={"csrf": csrf, **gueltig}).status_code == 200
    assert client.post(runde, data={"csrf": csrf, f"antwort_{i['f2']}": "7"}).status_code == 400
    lang = {"csrf": csrf, f"antwort_{i['f1']}": "x" * 20_001}
    assert client.post(runde, data=lang).status_code == 400
    assert client.post(runde, data=gueltig).status_code == 403
    for pfad in tagebuch:
        assert client.post(pfad, data={"csrf": csrf, "text": "Notiz"}).status_code == 200, pfad
        lang = {"csrf": csrf, "text": "x" * 20_001}
        assert client.post(pfad, data=lang).status_code == 400, pfad
        assert client.post(pfad, data={"text": "Notiz"}).status_code == 403, pfad
    geheim = f"/gast/runden/{i['geheim']}"
    assert client.post(geheim, data={"csrf": csrf, **gueltig}).status_code == 404
    impuls = f"/gast/tagebuch/neu/impuls/{i['impuls_geheim']}"
    assert client.post(impuls, data={"csrf": csrf, "text": "Notiz"}).status_code == 404


def test_gast_datenbank_unveraendert(client, inhalte, gast_seiten, db, einstellungen, lehrperson):
    def ordner():
        return sorted(p.name for p in einstellungen.aufnahmen_verzeichnis.iterdir())

    vorher, dateien = testdaten.abzug(db), ordner()
    _durchgang(client, inhalte, gast_seiten)
    assert testdaten.abzug(db) == vorher
    assert ordner() == dateien

    assert anmelden(client, lehrperson["benutzername"], lehrperson["passwort"]).status_code == 303
    vorher = testdaten.abzug(db)
    _durchgang(client, inhalte, gast_seiten)
    assert testdaten.abzug(db) == vorher
    assert ordner() == dateien


def test_gast_sitzung_unberuehrt(client, inhalte, lehrperson):
    assert anmelden(client, lehrperson["benutzername"], lehrperson["passwort"]).status_code == 303
    antwort = client.get("/gast")
    assert antwort.status_code == 200
    assert not [c for c in antwort.headers.get_list("set-cookie") if c.startswith("sitzung=")]
    assert "Anna Beispiel" not in antwort.text
    assert client.get("/lehrperson").status_code == 200


def test_login_zeigt_gast_knopf(client):
    html = client.get("/").text
    assert 'href="/gast"' in html
    assert "Ansehen ohne Konto" in html
    assert "Ohne Anmeldung. Es wird nichts gespeichert." in html


def test_datenschutz_nennt_gast_ansicht():
    text = (Path(__file__).parent.parent / "docs" / "datenschutz.md").read_text(encoding="utf-8")
    assert "Gast-Ansicht speichert nichts" in text
    assert "test_gast_datenbank_unveraendert" in text
    zeile = next(z for z in text.splitlines() if "`hinweis_gast`" in z)
    assert "als Meldung statt einer Bestätigung" not in zeile
