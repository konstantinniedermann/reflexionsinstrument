import re
from pathlib import Path

from conftest import als_leitung, csrf_von
from fastapi.testclient import TestClient

from app.texte import REGISTER

BEREICHE = ("allgemein", "info", "runden", "leitfragen", "impulse", "hinweise")
PFAD = "/verwaltung/inhalte/allgemein"


def bereich(text, name):
    treffer = re.search(rf'id="bereich-{name}".*?</a>', text, re.DOTALL)
    assert treffer, name
    return treffer.group(0)


def speichern(client, **felder):
    daten = {
        "csrf": csrf_von(client, PFAD),
        "titel": "Lernheft",
        "begruessung": "Hallo",
        "projektstart": "2026-11-23",
    }
    daten.update(felder)
    return client.post(PFAD, data=daten)


def test_uebersicht_zeigt_bereiche(client, auftraggeberin):
    antwort = als_leitung(client, auftraggeberin).get("/verwaltung/inhalte")
    assert antwort.status_code == 200
    for name in BEREICHE:
        assert f'href="/verwaltung/inhalte/{name}"' in antwort.text
    assert "0 von 5 Hinweisen bestätigt" in antwort.text
    assert "Erster Tag noch nicht festgelegt" in antwort.text
    for name in ("allgemein", "runden", "hinweise"):
        assert "Noch offen" in bereich(antwort.text, name), name


def test_uebersicht_stand(client, auftraggeberin, db):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    db.execute("INSERT INTO runden (id, titel, freischaltdatum) VALUES (1, 'A', '2026-11-23')")
    db.execute("INSERT INTO runden (id, titel, freischaltdatum) VALUES (2, 'B', '2026-11-30')")
    for i in range(3):
        db.execute(
            "INSERT INTO fragen (runde_id, text, typ, reihenfolge) VALUES (1, 'F', 'freitext', ?)",
            (i,),
        )
    text = als_leitung(client, auftraggeberin).get("/verwaltung/inhalte").text
    assert "Erster Tag: Mo 23.11.2026" in text
    assert "2 Runden, 3 Fragen" in text
    assert "Noch offen" in bereich(text, "runden")


def test_allgemein_zeigt_vorschlag_markiert(client, auftraggeberin):
    text = als_leitung(client, auftraggeberin).get(PFAD).text
    feld = re.search(r'<textarea[^>]*name="begruessung"[^>]*>(.*?)</textarea>', text, re.DOTALL)
    assert feld and REGISTER["begruessung"].vorschlag in feld.group(1)
    assert "Vorschlag, noch nicht von dir bestätigt" in text


def test_allgemein_speichern(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    antwort = speichern(client, begruessung="Hallo\n\n- a\n- **b**")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/verwaltung/inhalte/allgemein?erledigt=gespeichert"
    text = client.get(antwort.headers["location"]).text
    assert "Gespeichert." in text
    assert "noch nicht von dir bestätigt" not in text
    anzeige = re.search(r'id="begruessung-anzeige".*?</section>', text, re.DOTALL).group(0)
    assert "<p>Hallo</p><ul><li>a</li><li><strong>b</strong></li></ul>" in anzeige
    assert re.search(r"<title>[^<]*Lernheft", text)
    assert re.search(r'seitenkopf__titel">[^<]*Lernheft', text)
    frisch = TestClient(client.app, follow_redirects=False)
    assert "Lernheft" in frisch.get("/").text


def test_allgemein_fehler(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    antwort = speichern(client, titel="Mein Titel", projektstart="23.11.2026")
    assert antwort.status_code == 400
    assert "Bitte prüfe die markierten Felder." in antwort.text
    assert "Bitte ein Datum wählen." in antwort.text
    assert 'aria-describedby="fehler-projektstart"' in antwort.text
    assert 'id="fehler-projektstart"' in antwort.text
    assert 'value="Mein Titel"' in antwort.text


def test_titel_escapt(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    assert speichern(client, titel="<b>x</b>").status_code == 303
    text = client.get(PFAD).text
    assert "&lt;b&gt;x&lt;/b&gt;" in text
    assert "<b>x</b>" not in text


def test_fehlerseite_zeigt_titel(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    speichern(client)
    antwort = client.get("/gibts-nicht")
    assert antwort.status_code == 404
    assert re.search(r'seitenkopf__titel">[^<]*Lernheft', antwort.text)


def test_kein_fester_titel_in_templates():
    wurzel = Path(__file__).parent.parent / "app" / "templates"
    for datei in wurzel.rglob("*"):
        if datei.is_file():
            assert "Reflexionsinstrument" not in datei.read_text(encoding="utf-8"), datei


def test_bestaetigung_nur_aus_fester_liste(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    text = client.get(PFAD + "?erledigt=<script>").text
    assert "<script>" not in text and "&lt;script" not in text


def test_verwaltung_verlinkt_inhalte(client, auftraggeberin):
    text = als_leitung(client, auftraggeberin).get("/verwaltung").text
    assert 'href="/verwaltung/inhalte"' in text
    nav = re.search(r"<nav.*?</nav>", text, re.DOTALL).group(0)
    assert "Inhalte" in nav
