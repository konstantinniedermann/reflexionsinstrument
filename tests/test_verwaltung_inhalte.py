import html
import re
from pathlib import Path

import pytest
from conftest import als_leitung, csrf_von, lege_antwort_an, lege_eintrag_an
from fastapi.testclient import TestClient

from app import inhalte
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


# ---------- Runden und Fragen ----------

RUNDEN = "/verwaltung/inhalte/runden"


def melde_an(client, auftraggeberin):
    return als_leitung(client, auftraggeberin)


def erster_tag(db, datum="2026-11-23"):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', ?)", (datum,))


def neue_runde(db, datum="2026-11-23", titel="Runde", fallbeispiel=None):
    return db.execute(
        "INSERT INTO runden (titel, fallbeispiel, freischaltdatum) VALUES (?, ?, ?)",
        (titel, fallbeispiel, datum),
    ).lastrowid


def neue_frage(db, runde_id, text="Frage", typ="freitext", nummer=1):
    skala = ("klein", "gross") if typ == "skala" else (None, None)
    return db.execute(
        "INSERT INTO fragen (runde_id, typ, text, skala_min_text, skala_max_text, reihenfolge) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (runde_id, typ, text, *skala, nummer),
    ).lastrowid


def neues_konto(db, name):
    return db.execute(
        "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle) "
        "VALUES (?, ?, 'x', 'lehrperson')",
        (name, name),
    ).lastrowid


def sende(client, pfad, formular="/verwaltung/inhalte/runden", **felder):
    """POST mit CSRF-Token, das von der Seite `formular` gelesen wird."""
    return client.post(pfad, data={"csrf": csrf_von(client, formular), **felder})


def runde_felder(**felder):
    return {"titel": "Neue Runde", "freischaltdatum": "2026-11-23", "fallbeispiel": "", **felder}


def frage_felder(**felder):
    return {
        "typ": "freitext",
        "text": "Was ist gelungen?",
        "skala_min_text": "",
        "skala_max_text": "",
        **felder,
    }


def anzahl(db, tabelle):
    return db.execute(f"SELECT COUNT(*) FROM {tabelle}").fetchone()[0]


def test_runde_anlegen_leitet_auf_runde(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, RUNDEN, **runde_felder())
    assert antwort.status_code == 303
    rid = db.execute("SELECT id FROM runden").fetchone()[0]
    assert antwort.headers["location"] == f"{RUNDEN}/{rid}?erledigt=angelegt"
    seite = client.get(antwort.headers["location"])
    assert seite.status_code == 200
    assert "Angelegt." in seite.text
    assert "Neue Runde" in seite.text


def test_neu_laden_legt_nicht_doppelt_an(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, RUNDEN, **runde_felder())
    assert antwort.status_code == 303
    for _ in range(2):
        assert client.get(antwort.headers["location"]).status_code == 200
    assert anzahl(db, "runden") == 1


def test_runde_anlegen_fehler(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(
        client, RUNDEN, **runde_felder(titel="", freischaltdatum="", fallbeispiel="Fall")
    )
    assert antwort.status_code == 400
    assert "Bitte prüfe die markierten Felder." in antwort.text
    assert "Bitte einen Titel eingeben." in antwort.text
    assert 'aria-describedby="fehler-titel"' in antwort.text
    assert "Fall</textarea>" in antwort.text
    datum = sende(client, RUNDEN, **runde_felder(freischaltdatum=""))
    assert datum.status_code == 400
    assert "Bitte ein Datum wählen." in datum.text
    assert 'aria-describedby="fehler-freischaltdatum"' in datum.text
    assert anzahl(db, "runden") == 0


def test_neue_runde_datum_vorgeschlagen(client, auftraggeberin, db):
    erster_tag(db)
    neue_runde(db, "2026-11-23")
    antwort = melde_an(client, auftraggeberin).get(f"{RUNDEN}/neu")
    assert antwort.status_code == 200
    assert 'value="2026-11-30"' in antwort.text


def test_runden_ohne_ersten_tag(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    formular = client.get(f"{RUNDEN}/neu")
    assert formular.status_code == 200
    assert 'name="freischaltdatum"' in formular.text
    assert 'value="20' not in formular.text
    neue_runde(db, "2026-11-23")
    liste = client.get(RUNDEN)
    assert liste.status_code == 200
    assert "Woche" not in liste.text
    assert "Mo 23.11.2026" in liste.text
    seite = client.get(f"{RUNDEN}/{db.execute('SELECT id FROM runden').fetchone()[0]}")
    assert seite.status_code == 200
    assert "Woche" not in seite.text


def test_runden_liste_zeigt_woche_und_marke(client, auftraggeberin, db, festes_heute):
    erster_tag(db)
    neue_runde(db, "2026-11-23", "Erste")
    neue_runde(db, "2026-12-07", "Dritte")
    liste = melde_an(client, auftraggeberin).get(RUNDEN)
    assert liste.status_code == 200
    assert "Woche 1" in liste.text and "Woche 3" in liste.text
    assert "Sichtbar" in liste.text
    assert "Ab Mo 07.12." in liste.text
    assert "Nach oben" not in liste.text and "Nach unten" not in liste.text


def test_runde_vor_dem_start(client, auftraggeberin, db):
    erster_tag(db)
    rid = neue_runde(db, "2026-11-20")
    melde_an(client, auftraggeberin)
    for pfad in (RUNDEN, f"{RUNDEN}/{rid}"):
        antwort = client.get(pfad)
        assert antwort.status_code == 200
        assert "vor dem Start" in antwort.text, pfad
        assert "Woche 0" not in antwort.text and "Woche -" not in antwort.text


def test_hinweis_bei_sichtbarer_runde(client, auftraggeberin, db, festes_heute):
    sichtbar = neue_runde(db, "2026-11-30")
    spaeter = neue_runde(db, "2026-12-07")
    melde_an(client, auftraggeberin)
    a = client.get(f"{RUNDEN}/{sichtbar}/bearbeiten")
    b = client.get(f"{RUNDEN}/{spaeter}/bearbeiten")
    assert a.status_code == 200 and b.status_code == 200
    assert "Diese Runde ist schon sichtbar." in a.text
    assert "Diese Runde ist schon sichtbar." not in b.text


def test_runde_bearbeiten(client, auftraggeberin, db):
    rid = neue_runde(db, "2026-11-23", "Alt")
    melde_an(client, auftraggeberin)
    pfad = f"{RUNDEN}/{rid}/bearbeiten"
    formular = client.get(pfad)
    assert 'value="Alt"' in formular.text
    antwort = sende(client, pfad, pfad, **runde_felder(titel="Neu", freischaltdatum="2026-12-01"))
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{RUNDEN}/{rid}?erledigt=gespeichert"
    zeile = db.execute("SELECT titel, freischaltdatum FROM runden").fetchone()
    assert tuple(zeile) == ("Neu", "2026-12-01")
    fehler = sende(client, pfad, pfad, **runde_felder(titel=""))
    assert fehler.status_code == 400
    assert db.execute("SELECT titel FROM runden").fetchone()[0] == "Neu"


def test_fallbeispiel_formatiert(client, auftraggeberin, db):
    rid = neue_runde(db, fallbeispiel="- a\n- b")
    seite = melde_an(client, auftraggeberin).get(f"{RUNDEN}/{rid}")
    assert seite.status_code == 200
    assert "<ul><li>a</li><li>b</li></ul>" in seite.text


def test_fallbeispiel_escapt(client, auftraggeberin, db):
    rid = neue_runde(db, fallbeispiel="<script>alert(1)</script>")
    seite = melde_an(client, auftraggeberin).get(f"{RUNDEN}/{rid}")
    assert "<script>alert" not in seite.text
    assert "&lt;script&gt;" in seite.text


def test_frage_anlegen_und_umsortieren(client, auftraggeberin, db):
    rid = neue_runde(db)
    melde_an(client, auftraggeberin)
    seite = f"{RUNDEN}/{rid}"
    ids = []
    for text in ("Erste", "Zweite"):
        antwort = sende(client, f"{seite}/fragen", seite, **frage_felder(text=text))
        assert antwort.status_code == 303
        fid = db.execute("SELECT id FROM fragen WHERE text = ?", (text,)).fetchone()[0]
        ids.append(fid)
        assert antwort.headers["location"] == f"{seite}?erledigt=angelegt#frage-{fid}"
    assert client.get(seite).text.index("Erste") < client.get(seite).text.index("Zweite")
    antwort = sende(
        client, f"/verwaltung/inhalte/fragen/{ids[1]}/verschieben", seite, richtung="hoch"
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{seite}#frage-{ids[1]}"
    text = client.get(seite).text
    assert text.index("Zweite") < text.index("Erste")


def test_verschieben_knoepfe(client, auftraggeberin, db):
    rid = neue_runde(db)
    neue_frage(db, rid, "Oben", nummer=1)
    neue_frage(db, rid, "Mitte", nummer=2)
    neue_frage(db, rid, "Unten", nummer=3)
    text = melde_an(client, auftraggeberin).get(f"{RUNDEN}/{rid}").text
    assert "‹Oben› nach oben" not in text and "‹Oben› nach unten" in text
    assert 'aria-label="‹Mitte› nach oben"' in text and 'aria-label="‹Mitte› nach unten"' in text
    assert "‹Unten› nach unten" not in text and "‹Unten› nach oben" in text


def test_frage_skala_ohne_beschriftung_400(client, auftraggeberin, db):
    rid = neue_runde(db)
    melde_an(client, auftraggeberin)
    seite = f"{RUNDEN}/{rid}"
    antwort = sende(
        client,
        f"{seite}/fragen",
        seite,
        **frage_felder(typ="skala", text="Wie war es?", skala_min_text="wenig"),
    )
    assert antwort.status_code == 400
    assert "Für die Skala braucht es beide Beschriftungen." in antwort.text
    assert 'aria-describedby="fehler-skala_max_text"' in antwort.text
    assert "Wie war es?</textarea>" in antwort.text
    assert 'value="wenig"' in antwort.text
    assert anzahl(db, "fragen") == 0


def test_frage_formular_neu(client, auftraggeberin, db):
    rid = neue_runde(db)
    text = melde_an(client, auftraggeberin).get(f"{RUNDEN}/{rid}/fragen/neu").text
    assert "Antwort als Text" in text
    assert "Antwort auf einer Skala von 1 bis 5" in text
    assert "disabled" not in text
    assert "beantwortet" not in text


def test_frage_mit_antworten_formular_speichern(client, auftraggeberin, db):
    rid = neue_runde(db)
    fid = neue_frage(db, rid, "Alt")
    lege_antwort_an(db, fid, neues_konto(db, "a"))
    lege_antwort_an(db, fid, neues_konto(db, "b"))
    melde_an(client, auftraggeberin)
    pfad = f"/verwaltung/inhalte/fragen/{fid}"
    formular = client.get(pfad)
    assert formular.status_code == 200
    assert "disabled" in formular.text
    assert 'type="hidden" name="typ" value="freitext"' in formular.text
    assert "schon 2-mal beantwortet" in formular.text
    assert "Die Art lässt sich nicht mehr ändern" in formular.text
    vorher = [tuple(z) for z in db.execute("SELECT * FROM antworten ORDER BY id")]

    # So, wie der Browser das angezeigte Formular schickt: gesperrte Radios fehlen, das
    # versteckte Feld bringt die bisherige Art mit.
    antwort = sende(client, pfad, pfad, typ="freitext", text="Neuer Text")
    assert antwort.status_code == 303
    assert db.execute("SELECT text FROM fragen").fetchone()[0] == "Neuer Text"

    abweichend = sende(
        client, pfad, pfad, typ="skala", text="Skala?", skala_min_text="a", skala_max_text="b"
    )
    assert abweichend.status_code == 400
    assert "Die Art lässt sich nicht mehr ändern, weil die Frage schon beantwortet wurde." in (
        abweichend.text
    )
    zeile = db.execute("SELECT typ, text FROM fragen").fetchone()
    assert tuple(zeile) == ("freitext", "Neuer Text")
    assert [tuple(z) for z in db.execute("SELECT * FROM antworten ORDER BY id")] == vorher


def test_frage_ohne_antworten_art_waehlbar(client, auftraggeberin, db):
    rid = neue_runde(db)
    fid = neue_frage(db, rid)
    melde_an(client, auftraggeberin)
    pfad = f"/verwaltung/inhalte/fragen/{fid}"
    text = client.get(pfad).text
    assert "disabled" not in text and 'type="hidden" name="typ"' not in text
    antwort = sende(
        client, pfad, pfad, typ="skala", text="Neu", skala_min_text="a", skala_max_text="b"
    )
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{RUNDEN}/{rid}?erledigt=gespeichert#frage-{fid}"
    assert db.execute("SELECT typ FROM fragen").fetchone()[0] == "skala"


def test_frage_loeschen(client, auftraggeberin, db):
    rid = neue_runde(db)
    a = neue_frage(db, rid, "A", nummer=1)
    neue_frage(db, rid, "B", nummer=2)
    melde_an(client, auftraggeberin)
    pfad = f"/verwaltung/inhalte/fragen/{a}/loeschen"
    bestaetigung = client.get(pfad)
    assert bestaetigung.status_code == 200
    assert "Endgültig löschen" in bestaetigung.text
    antwort = sende(client, pfad, pfad)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{RUNDEN}/{rid}?erledigt=geloescht"
    assert [tuple(z) for z in db.execute("SELECT text, reihenfolge FROM fragen")] == [("B", 1)]


def test_frage_loeschen_gesperrt_409(client, auftraggeberin, db):
    rid = neue_runde(db)
    fid = neue_frage(db, rid)
    lege_antwort_an(db, fid, neues_konto(db, "a"))
    lege_antwort_an(db, fid, neues_konto(db, "b"))
    melde_an(client, auftraggeberin)
    pfad = f"/verwaltung/inhalte/fragen/{fid}/loeschen"
    bestaetigung = client.get(pfad)
    assert bestaetigung.status_code == 200
    assert "Diese Frage wurde schon 2-mal beantwortet." in bestaetigung.text
    assert "Endgültig löschen" not in bestaetigung.text
    antwort = sende(client, pfad, pfad)
    assert antwort.status_code == 409
    assert "Diese Frage wurde schon 2-mal beantwortet." in antwort.text
    assert "Endgültig löschen" not in antwort.text
    assert anzahl(db, "fragen") == 1 and anzahl(db, "antworten") == 2


def test_sicherheitsnetz_route(client, auftraggeberin, db, monkeypatch):
    rid = neue_runde(db)
    fid = neue_frage(db, rid)
    lege_antwort_an(db, fid, neues_konto(db, "a"))
    pfad = f"/verwaltung/inhalte/fragen/{fid}/loeschen"
    melde_an(client, auftraggeberin)
    token = csrf_von(client, pfad)
    monkeypatch.setattr(inhalte, "zaehle_antworten_frage", lambda db, frage_id: 0)
    antwort = client.post(pfad, data={"csrf": token})
    assert antwort.status_code == 409
    assert "schon 1-mal beantwortet" in antwort.text
    assert anzahl(db, "fragen") == 1 and anzahl(db, "antworten") == 1


def test_runde_loeschen(client, auftraggeberin, db):
    rid = neue_runde(db)
    neue_frage(db, rid, nummer=1)
    neue_frage(db, rid, nummer=2)
    melde_an(client, auftraggeberin)
    pfad = f"{RUNDEN}/{rid}/loeschen"
    bestaetigung = client.get(pfad)
    assert bestaetigung.status_code == 200
    assert "Die Runde und ihre 2 Fragen werden gelöscht." in bestaetigung.text
    antwort = sende(client, pfad, pfad)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{RUNDEN}?erledigt=geloescht"
    assert anzahl(db, "runden") == 0 and anzahl(db, "fragen") == 0


def test_runde_loeschen_gesperrt_409(client, auftraggeberin, db):
    rid = neue_runde(db)
    neue_frage(db, rid, nummer=1)
    fid = neue_frage(db, rid, nummer=2)
    lege_antwort_an(db, fid, neues_konto(db, "a"))
    melde_an(client, auftraggeberin)
    pfad = f"{RUNDEN}/{rid}/loeschen"
    bestaetigung = client.get(pfad)
    assert bestaetigung.status_code == 200
    assert "schon 1-mal beantwortet" in bestaetigung.text
    assert "Endgültig löschen" not in bestaetigung.text
    antwort = sende(client, pfad, pfad)
    assert antwort.status_code == 409
    assert anzahl(db, "runden") == 1 and anzahl(db, "fragen") == 2 and anzahl(db, "antworten") == 1


def test_unbekannte_ids_404(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    token = csrf_von(client, RUNDEN)
    basis = "/verwaltung/inhalte"
    pfade = [
        "runden/999",
        "runden/999/bearbeiten",
        "runden/999/loeschen",
        "runden/999/fragen/neu",
        "fragen/999",
        "fragen/999/loeschen",
    ]
    for pfad in pfade:
        assert client.get(f"{basis}/{pfad}").status_code == 404, pfad
    posts = pfade[1:3] + ["runden/999/fragen", "fragen/999", "fragen/999/loeschen"]
    for pfad in posts:
        daten = {"csrf": token, **runde_felder(), **frage_felder()}
        assert client.post(f"{basis}/{pfad}", data=daten).status_code == 404, pfad
    verschieben = client.post(
        f"{basis}/fragen/999/verschieben", data={"csrf": token, "richtung": "hoch"}
    )
    assert verschieben.status_code == 404
    for kaputt in ("runden/0", "runden/abc", "runden/99999999999999999999"):
        assert client.get(f"{basis}/{kaputt}").status_code == 404, kaputt
    assert client.get(f"{basis}/fragen/99999999999999999999").status_code == 404


def test_doppelt_loeschen_404(client, auftraggeberin, db):
    rid = neue_runde(db)
    fid = neue_frage(db, rid)
    melde_an(client, auftraggeberin)
    pfad = f"/verwaltung/inhalte/fragen/{fid}/loeschen"
    token = csrf_von(client, pfad)
    assert client.post(pfad, data={"csrf": token}).status_code == 303
    zweites = client.post(pfad, data={"csrf": token})
    assert zweites.status_code == 404
    assert client.get(pfad).status_code == 404
    verschieben = client.post(
        f"/verwaltung/inhalte/fragen/{fid}/verschieben", data={"csrf": token, "richtung": "hoch"}
    )
    assert verschieben.status_code == 404


def test_doppelt_loeschen_runde_404(client, auftraggeberin, db):
    rid = neue_runde(db)
    melde_an(client, auftraggeberin)
    pfad = f"{RUNDEN}/{rid}/loeschen"
    token = csrf_von(client, pfad)
    assert client.post(pfad, data={"csrf": token}).status_code == 303
    assert client.post(pfad, data={"csrf": token}).status_code == 404


def test_richtung_ungueltig_400(client, auftraggeberin, db):
    rid = neue_runde(db)
    a = neue_frage(db, rid, "A", nummer=1)
    neue_frage(db, rid, "B", nummer=2)
    melde_an(client, auftraggeberin)
    antwort = sende(
        client, f"/verwaltung/inhalte/fragen/{a}/verschieben", RUNDEN, richtung="seitwaerts"
    )
    assert antwort.status_code == 400
    antwort = sende(client, f"/verwaltung/inhalte/fragen/{a}/verschieben", RUNDEN)
    assert antwort.status_code == 400
    assert [z[0] for z in db.execute("SELECT reihenfolge FROM fragen ORDER BY id")] == [1, 2]


def test_neue_frage_in_unbekannte_runde_nicht_angelegt(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, f"{RUNDEN}/999/fragen", **frage_felder())
    assert antwort.status_code == 404
    assert anzahl(db, "fragen") == 0


def test_programmierfehler_ist_kein_404(client, auftraggeberin, db, monkeypatch):
    rid = neue_runde(db)
    melde_an(client, auftraggeberin)
    pfad = f"{RUNDEN}/{rid}/bearbeiten"
    token = csrf_von(client, pfad)

    def kaputt(*args):
        raise KeyError("Programmierfehler")

    monkeypatch.setattr("app.routen.verwaltung_inhalte.aendere_runde", kaputt)
    with pytest.raises(KeyError):
        client.post(pfad, data={"csrf": token, **runde_felder()})


def test_runde_ohne_fragen_loeschen_text(client, auftraggeberin, db):
    rid = neue_runde(db)
    melde_an(client, auftraggeberin)
    seite = client.get(f"{RUNDEN}/{rid}/loeschen")
    assert "Die Runde wird gelöscht." in seite.text
    assert "0 Fragen" not in seite.text


# ---------- Infoblock und Leitfragen ----------

INFO = "/verwaltung/inhalte/info"
LEITFRAGEN = "/verwaltung/inhalte/leitfragen"


def neuer_abschnitt(db, titel="Abschnitt", inhalt="Text", nummer=1):
    return db.execute(
        "INSERT INTO info_abschnitte (titel, inhalt, reihenfolge) VALUES (?, ?, ?)",
        (titel, inhalt, nummer),
    ).lastrowid


def neue_leitfrage(db, text="Leitfrage", nummer=1):
    return db.execute(
        "INSERT INTO leitfragen (text, reihenfolge) VALUES (?, ?)", (text, nummer)
    ).lastrowid


def test_info_anlegen_mit_anker(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, INFO, INFO, titel="Worum es geht", inhalt="Text")
    assert antwort.status_code == 303
    aid = db.execute("SELECT id FROM info_abschnitte").fetchone()[0]
    assert antwort.headers["location"] == f"{INFO}?erledigt=angelegt#abschnitt-{aid}"
    seite = client.get(f"{INFO}?erledigt=angelegt")
    assert "Angelegt." in seite.text and f'id="abschnitt-{aid}"' in seite.text


def test_info_bearbeiten(client, auftraggeberin, db):
    aid = neuer_abschnitt(db, "Alt", "Alter Text")
    melde_an(client, auftraggeberin)
    formular = client.get(f"{INFO}/{aid}")
    assert "Alter Text" in formular.text
    antwort = sende(client, f"{INFO}/{aid}", f"{INFO}/{aid}", titel="Neu", inhalt="Neuer Text")
    assert antwort.headers["location"] == f"{INFO}?erledigt=gespeichert#abschnitt-{aid}"
    assert db.execute("SELECT titel, inhalt FROM info_abschnitte").fetchone()[:] == (
        "Neu",
        "Neuer Text",
    )


def test_info_liste_formatiert_und_escapt(client, auftraggeberin, db):
    neuer_abschnitt(db, "Liste", "- a\n- **b**", 1)
    neuer_abschnitt(db, "Gefahr", "<script>alert(1)</script>", 2)
    melde_an(client, auftraggeberin)
    text = client.get(INFO).text
    assert "<ul><li>a</li><li><strong>b</strong></li></ul>" in text
    assert "&lt;script&gt;" in text
    assert "<script>alert(1)" not in text


def test_info_datenschutz_karte_am_schluss(client, auftraggeberin, db):
    neuer_abschnitt(db, "Erster", "Text", 1)
    letzter = neuer_abschnitt(db, "Letzter", "Text", 2)
    melde_an(client, auftraggeberin)
    text = client.get(INFO).text
    karte = text[text.index("Datenschutz (immer am Schluss)") :]
    assert text.index(f'id="abschnitt-{letzter}"') < text.index("Datenschutz (immer am Schluss)")
    assert "/verwaltung/inhalte/hinweise/hinweis_datenspeicherung" in karte
    assert "Frankfurt" in karte
    assert "Nach oben" not in karte and "/loeschen" not in karte
    assert "verschieben" not in karte


def test_info_leer_zeigt_nur_datenschutz(client, auftraggeberin):
    melde_an(client, auftraggeberin)
    text = client.get(INFO).text
    assert "Noch kein eigener Abschnitt" in text
    assert "Datenschutz (immer am Schluss)" in text


def test_info_verschieben(client, auftraggeberin, db):
    a = neuer_abschnitt(db, "AAA", "a", 1)
    neuer_abschnitt(db, "BBB", "b", 2)
    melde_an(client, auftraggeberin)
    antwort = sende(client, f"{INFO}/{a}/verschieben", INFO, richtung="runter")
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{INFO}#abschnitt-{a}"
    assert "erledigt" not in antwort.headers["location"]
    text = client.get(INFO).text
    assert text.index("BBB") < text.index("AAA")


def test_info_loeschen(client, auftraggeberin, db):
    aid = neuer_abschnitt(db)
    melde_an(client, auftraggeberin)
    pfad = f"{INFO}/{aid}/loeschen"
    assert "Endgültig löschen" in client.get(pfad).text
    antwort = sende(client, pfad, pfad)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{INFO}?erledigt=geloescht"
    assert anzahl(db, "info_abschnitte") == 0


def test_info_fehler_400(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, INFO, INFO, titel="", inhalt="Mein Text")
    assert antwort.status_code == 400
    assert "Bitte einen Titel eingeben." in antwort.text
    assert "Mein Text" in antwort.text
    assert anzahl(db, "info_abschnitte") == 0
    aid = neuer_abschnitt(db)
    antwort = sende(client, f"{INFO}/{aid}", f"{INFO}/{aid}", titel="T", inhalt="")
    assert antwort.status_code == 400
    assert "Bitte einen Text eingeben." in antwort.text


def test_leitfragen_anlegen_bearbeiten(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    antwort = sende(client, LEITFRAGEN, LEITFRAGEN, text="Was war heute?")
    lid = db.execute("SELECT id FROM leitfragen").fetchone()[0]
    assert antwort.headers["location"] == f"{LEITFRAGEN}?erledigt=angelegt#leitfrage-{lid}"
    antwort = sende(client, f"{LEITFRAGEN}/{lid}", f"{LEITFRAGEN}/{lid}", text="Neu")
    assert antwort.headers["location"] == f"{LEITFRAGEN}?erledigt=gespeichert#leitfrage-{lid}"
    assert "Neu" in client.get(LEITFRAGEN).text
    fehler = sende(client, LEITFRAGEN, LEITFRAGEN, text=" ")
    assert fehler.status_code == 400
    assert "Bitte eine Leitfrage eingeben." in fehler.text


def test_leitfrage_mit_eintrag_hinweise(client, auftraggeberin, db):
    lid = neue_leitfrage(db)
    lege_eintrag_an(db, neues_konto(db, "a"), art="leitfragen", leitfrage_id=lid)
    melde_an(client, auftraggeberin)
    assert "1 Tagebucheintrag bezieht sich darauf" in client.get(f"{LEITFRAGEN}/{lid}").text
    lege_eintrag_an(db, neues_konto(db, "b"), art="leitfragen", leitfrage_id=lid)
    assert "2 Tagebucheinträge beziehen sich darauf" in client.get(f"{LEITFRAGEN}/{lid}").text
    bestaetigung = client.get(f"{LEITFRAGEN}/{lid}/loeschen")
    assert "Einträge, die sich darauf beziehen, bleiben erhalten." in bestaetigung.text
    assert "Endgültig löschen" in bestaetigung.text


def test_leitfragen_verschieben_und_loeschen(client, auftraggeberin, db):
    a = neue_leitfrage(db, "AAA", 1)
    b = neue_leitfrage(db, "BBB", 2)
    lege_eintrag_an(db, neues_konto(db, "a"), art="leitfragen", leitfrage_id=a)
    melde_an(client, auftraggeberin)
    antwort = sende(client, f"{LEITFRAGEN}/{a}/verschieben", LEITFRAGEN, richtung="runter")
    assert antwort.headers["location"] == f"{LEITFRAGEN}#leitfrage-{a}"
    text = client.get(LEITFRAGEN).text
    assert text.index("BBB") < text.index("AAA")
    pfad = f"{LEITFRAGEN}/{a}/loeschen"
    antwort = sende(client, pfad, pfad)
    assert antwort.headers["location"] == f"{LEITFRAGEN}?erledigt=geloescht"
    assert [z[0] for z in db.execute("SELECT id FROM leitfragen")] == [b]
    assert db.execute("SELECT reihenfolge FROM leitfragen").fetchone()[0] == 1
    eintrag = db.execute("SELECT leitfrage_id, leitfrage_text FROM tagebucheintraege").fetchone()
    assert eintrag[:] == (None, "AAA")


def test_unbekannte_ids_404_info_leitfragen(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    token = csrf_von(client, INFO)
    daten = {"csrf": token, "titel": "T", "inhalt": "I", "text": "X", "richtung": "hoch"}
    for basis in (INFO, LEITFRAGEN):
        for pfad in ("999", "999/loeschen"):
            assert client.get(f"{basis}/{pfad}").status_code == 404, pfad
        for pfad in ("999", "999/loeschen", "999/verschieben"):
            assert client.post(f"{basis}/{pfad}", data=daten).status_code == 404, pfad
        assert client.get(f"{basis}/99999999999999999999").status_code == 404


def test_richtung_ungueltig_400_info_leitfragen(client, auftraggeberin, db):
    a = neuer_abschnitt(db)
    lid = neue_leitfrage(db)
    melde_an(client, auftraggeberin)
    assert sende(client, f"{INFO}/{a}/verschieben", INFO, richtung="x").status_code == 400
    assert sende(client, f"{LEITFRAGEN}/{lid}/verschieben", INFO).status_code == 400


# ---------- Impulse ----------

IMPULSE = "/verwaltung/inhalte/impulse"
HINWEISE = "/verwaltung/inhalte/hinweise"


def neuer_impuls(db, text="Impuls", datum="2026-11-23"):
    return db.execute(
        "INSERT INTO impulse (text, sichtbar_ab) VALUES (?, ?)", (text, datum)
    ).lastrowid


def test_impuls_anlegen_mit_vorschlag(client, auftraggeberin, db):
    erster_tag(db)
    melde_an(client, auftraggeberin)
    assert 'value="2026-11-23"' in client.get(f"{IMPULSE}/neu").text
    antwort = sende(
        client, IMPULSE, IMPULSE, text="Was fiel dir heute auf?", sichtbar_ab="2026-11-23"
    )
    assert antwort.status_code == 303
    iid = db.execute("SELECT id FROM impulse").fetchone()[0]
    assert antwort.headers["location"] == f"{IMPULSE}?erledigt=angelegt#impuls-{iid}"
    seite = client.get(f"{IMPULSE}?erledigt=angelegt").text
    assert f'id="impuls-{iid}"' in seite and "Angelegt." in seite
    assert 'value="2026-11-30"' in client.get(f"{IMPULSE}/neu").text
    antwort = sende(client, f"{IMPULSE}/{iid}", IMPULSE, text="Neu", sichtbar_ab="2026-12-01")
    assert antwort.headers["location"] == f"{IMPULSE}?erledigt=gespeichert#impuls-{iid}"
    assert "Neu" in client.get(IMPULSE).text
    fehler = sende(client, IMPULSE, IMPULSE, text=" ", sichtbar_ab="2026-11-23")
    assert fehler.status_code == 400 and "Bitte einen Impuls eingeben." in fehler.text
    fehler = sende(client, IMPULSE, IMPULSE, text="x", sichtbar_ab="")
    assert fehler.status_code == 400 and "Bitte ein Datum wählen." in fehler.text


def test_impulse_gleicher_tag_hinweis(client, auftraggeberin, db):
    neuer_impuls(db, "Eins", "2026-11-23")
    melde_an(client, auftraggeberin)
    assert "Am selben Tag gibt es noch einen Impuls." not in client.get(IMPULSE).text
    neuer_impuls(db, "Zwei", "2026-11-23")
    neuer_impuls(db, "Drei", "2026-11-30")
    text = client.get(IMPULSE).text
    assert text.count("Am selben Tag gibt es noch einen Impuls.") == 2
    assert "Auf der Startseite erscheint der zuletzt erfasste." in text


def test_impuls_mit_eintrag_hinweise_und_loeschen_ueber_bestaetigung(client, auftraggeberin, db):
    iid = neuer_impuls(db, "Impulstext")
    lege_eintrag_an(db, neues_konto(db, "a"), art="impuls", impuls_id=iid)
    melde_an(client, auftraggeberin)
    assert "1 Tagebucheintrag bezieht sich darauf" in client.get(f"{IMPULSE}/{iid}").text
    bestaetigung = client.get(f"{IMPULSE}/{iid}/loeschen")
    assert "Einträge, die sich darauf beziehen, bleiben erhalten." in bestaetigung.text
    assert "Endgültig löschen" in bestaetigung.text
    assert db.execute("SELECT COUNT(*) FROM impulse").fetchone()[0] == 1
    antwort = sende(client, f"{IMPULSE}/{iid}/loeschen", f"{IMPULSE}/{iid}/loeschen")
    assert antwort.headers["location"] == f"{IMPULSE}?erledigt=geloescht"
    assert db.execute("SELECT COUNT(*) FROM impulse").fetchone()[0] == 0
    eintrag = db.execute("SELECT impuls_id, impuls_text FROM tagebucheintraege").fetchone()
    assert eintrag[:] == (None, "Impulstext")


def test_unbekannte_ids_404_impulse(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    token = csrf_von(client, IMPULSE)
    daten = {"csrf": token, "text": "X", "sichtbar_ab": "2026-11-23"}
    for pfad in ("999", "999/loeschen"):
        assert client.get(f"{IMPULSE}/{pfad}").status_code == 404, pfad
        assert client.post(f"{IMPULSE}/{pfad}", data=daten).status_code == 404, pfad
    assert client.get(f"{IMPULSE}/99999999999999999999").status_code == 404


# ---------- Hinweise ----------


def test_hinweise_liste(client, auftraggeberin):
    text = als_leitung(client, auftraggeberin).get(HINWEISE).text
    for schluessel, vorlage in REGISTER.items():
        if vorlage.bereich == "hinweise":
            assert f'id="hinweis-{schluessel}"' in text
            assert f"{HINWEISE}/{schluessel}" in text
        else:
            assert f'id="hinweis-{schluessel}"' not in text
    assert text.count("Erscheint:") == 5
    assert text.count("Vorschlag, noch nicht von dir bestätigt") == 5


def test_hinweis_unveraendert_bestaetigen(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    schluessel = "hinweis_aufnahme"
    pfad = f"{HINWEISE}/{schluessel}"
    seite = client.get(pfad).text
    assert "Bestätigen heisst speichern, auch unverändert." in seite
    feld = re.search(r'<textarea[^>]*name="inhalt"[^>]*>(.*?)</textarea>', seite, re.DOTALL)
    vorschlag = html.unescape(feld.group(1)).strip()
    assert vorschlag == REGISTER[schluessel].vorschlag
    antwort = sende(client, pfad, pfad, inhalt=vorschlag)
    assert antwort.status_code == 303
    assert antwort.headers["location"] == f"{HINWEISE}?erledigt=gespeichert#hinweis-{schluessel}"
    liste = client.get(HINWEISE).text
    karte = re.search(rf'id="hinweis-{schluessel}".*?</article>', liste, re.DOTALL).group(0)
    assert "Bestätigt" in karte and "noch nicht von dir bestätigt" not in karte
    assert liste.count("Vorschlag, noch nicht von dir bestätigt") == 4
    assert "1 von 5 Hinweisen bestätigt" in client.get("/verwaltung/inhalte").text
    assert "Bestätigen heisst speichern" not in client.get(pfad).text


def test_hinweis_leer_400(client, auftraggeberin, db):
    melde_an(client, auftraggeberin)
    pfad = f"{HINWEISE}/hinweis_gast"
    antwort = sende(client, pfad, pfad, inhalt="  \n ")
    assert antwort.status_code == 400
    assert "Bitte einen Text eingeben." in antwort.text
    assert db.execute("SELECT COUNT(*) FROM texte").fetchone()[0] == 0


def test_hinweis_unbekannt_404(client, auftraggeberin):
    melde_an(client, auftraggeberin)
    token = csrf_von(client, HINWEISE)
    for schluessel in ("begruessung", "gibts_nicht"):
        pfad = f"{HINWEISE}/{schluessel}"
        assert client.get(pfad).status_code == 404, schluessel
        assert client.post(pfad, data={"csrf": token, "inhalt": "X"}).status_code == 404, schluessel


def test_datenschutz_link_im_infoblock_fuehrt_zum_hinweis(client, auftraggeberin):
    melde_an(client, auftraggeberin)
    assert f"{HINWEISE}/hinweis_datenspeicherung" in client.get("/verwaltung/inhalte/info").text
    assert client.get(f"{HINWEISE}/hinweis_datenspeicherung").status_code == 200
