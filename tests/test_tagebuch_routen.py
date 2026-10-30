import re
from datetime import date

import pytest
import testdaten
from conftest import als_lehrperson, csrf_von

from app.texte import REGISTER

NEU = "/lehrperson/tagebuch/neu"


@pytest.fixture
def welt(db, client, lehrperson, heute_ist):
    """Ein aktueller Impuls, ein spaeterer, zwei Leitfragen; Lehrperson angemeldet."""
    aktuell = testdaten.lege_impuls_an(db, "Impuls Jetzt", "2026-11-23")
    alt = testdaten.lege_impuls_an(db, "Impuls Alt", "2026-11-16")
    spaet = testdaten.lege_impuls_an(db, "Impuls Spaet", "2026-12-07")
    l1 = testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    l2 = testdaten.lege_leitfrage_an(db, "Leitfrage Zwei")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    return {"aktuell": aktuell, "alt": alt, "spaet": spaet, "l1": l1, "l2": l2}


def _anlegen(client, pfad, text, **mehr):
    return client.post(pfad, data={"csrf": csrf_von(client, pfad), "text": text, **mehr})


def _eintraege(db):
    return db.execute("SELECT * FROM tagebucheintraege ORDER BY id").fetchall()


def _feld(text, name="text"):
    treffer = re.search(rf'<textarea[^>]*name="{name}"[^>]*>\s*(.*?)</textarea>', text, re.DOTALL)
    assert treffer, name
    return treffer.group(1)


def test_wahl(client, welt):
    text = client.get(NEU).text
    assert 'class="inhalt bereich--tagebuch"' in text
    assert f'href="{NEU}/frei"' in text
    assert f'href="{NEU}/impuls/{welt["aktuell"]}"' in text
    assert "Impuls Jetzt" in text
    assert "Impuls Spaet" not in text and "Impuls Alt" not in text
    assert "Zu einer Leitfrage schreiben" in text
    for lid in (welt["l1"], welt["l2"]):
        assert f'href="{NEU}/leitfrage/{lid}"' in text


def test_wahl_ohne_impuls_und_leitfragen(client, db, lehrperson, heute_ist):
    testdaten.lege_impuls_an(db, "Kommt noch", "2026-12-07")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = client.get(NEU).text
    assert f'href="{NEU}/frei"' in text
    assert "/neu/impuls/" not in text
    assert "Zu einer Leitfrage schreiben" not in text


def test_neu_frei(client, db, lehrperson, welt):
    seite = client.get(f"{NEU}/frei").text
    assert re.search(r'<textarea[^>]*name="text"', seite)
    assert 'maxlength="20000"' in seite
    assert REGISTER["hinweis_tagebuch"].vorschlag[:40] in seite
    antwort = _anlegen(client, f"{NEU}/frei", "Mein Gedanke")
    assert antwort.status_code == 303
    eintrag = _eintraege(db)[0]
    assert eintrag["art"] == "frei" and eintrag["konto_id"] == lehrperson["id"]
    assert antwort.headers["location"] == (
        f"/lehrperson/tagebuch/{eintrag['id']}?erledigt=gespeichert"
    )
    text = client.get(antwort.headers["location"]).text
    assert "Gespeichert." in text
    assert "Freier Eintrag" in text
    assert "Mein Gedanke" in text
    assert "Erstellt" in text
    assert "geändert" not in text
    assert "Zur Startseite" in text
    assert "Zu einer weiteren Leitfrage" not in text


def test_neu_zum_impuls(client, db, welt):
    seite = client.get(f"{NEU}/impuls/{welt['aktuell']}").text
    assert seite.index("Impuls Jetzt") < seite.index("<textarea")
    antwort = _anlegen(client, f"{NEU}/impuls/{welt['aktuell']}", "Dazu")
    assert antwort.status_code == 303
    db.execute("UPDATE impulse SET text = 'Neu' WHERE id = ?", (welt["aktuell"],))
    db.commit()
    text = client.get(antwort.headers["location"]).text
    assert "Zum Impuls" in text
    assert "Impuls Jetzt" in text
    assert ">Neu<" not in text
    assert _anlegen(client, f"{NEU}/impuls/{welt['alt']}", "Alt").status_code == 303
    assert [e["impuls_text"] for e in _eintraege(db)] == ["Impuls Jetzt", "Impuls Alt"]


def test_neu_zur_leitfrage(client, db, welt):
    antwort = _anlegen(client, f"{NEU}/leitfrage/{welt['l1']}", "Gedanke")
    assert antwort.status_code == 303
    eintrag = _eintraege(db)[0]
    assert eintrag["art"] == "leitfragen" and eintrag["leitfrage_text"] == "Leitfrage Eins"
    text = client.get(antwort.headers["location"]).text
    assert "Zur Leitfrage" in text and "Leitfrage Eins" in text
    assert "Zu einer weiteren Leitfrage schreiben" in text


def test_neu_bezug_404(client, db, welt):
    vorher = testdaten.abzug(db)
    csrf = csrf_von(client, NEU)
    for pfad in (f"{NEU}/impuls/{welt['spaet']}", f"{NEU}/leitfrage/9999", f"{NEU}/impuls/abc"):
        assert client.get(pfad).status_code == 404, pfad
        assert client.post(pfad, data={"csrf": csrf, "text": "x"}).status_code == 404, pfad
    assert testdaten.abzug(db) == vorher


def test_neu_leer_400(client, db, welt):
    antwort = _anlegen(client, f"{NEU}/frei", "   ")
    assert antwort.status_code == 400
    assert "Der Eintrag ist noch leer." in antwort.text
    assert _eintraege(db) == []


def test_neu_400_behaelt_text(client, db, welt):
    antwort = _anlegen(client, f"{NEU}/frei", "x" * 20001)
    assert antwort.status_code == 400
    assert _eintraege(db) == []


def test_neu_laden_legt_nicht_doppelt_an(client, db, welt):
    antwort = _anlegen(client, f"{NEU}/frei", "Einmal")
    assert antwort.status_code == 303
    for _ in range(2):
        assert client.get(antwort.headers["location"]).status_code == 200
    assert len(_eintraege(db)) == 1


def test_doppelt_abgesendet_legt_einmal_an(client, db, welt):
    pfad = f"{NEU}/leitfrage/{welt['l1']}"
    csrf = csrf_von(client, pfad)
    antworten = [client.post(pfad, data={"csrf": csrf, "text": "Gleich"}) for _ in range(2)]
    (eintrag,) = _eintraege(db)
    for antwort in antworten:
        assert antwort.status_code == 303
        assert antwort.headers["location"] == (
            f"/lehrperson/tagebuch/{eintrag['id']}?erledigt=gespeichert"
        )


def test_anderer_text_legt_zwei_an(client, db, welt):
    assert _anlegen(client, f"{NEU}/frei", "Erster").status_code == 303
    assert _anlegen(client, f"{NEU}/frei", "Zweiter").status_code == 303
    assert [e["text"] for e in _eintraege(db)] == ["Erster", "Zweiter"]


def test_langer_text_mit_umlauten_passt(client, db, welt):
    text = "Schöne Grüsse, äöü. " * 1000
    assert _anlegen(client, f"{NEU}/frei", text).status_code == 303
    assert _eintraege(db)[0]["text"] == text.rstrip()


def _eintrag(client, db, text="Erster Text"):
    antwort = _anlegen(client, f"{NEU}/frei", text)
    assert antwort.status_code == 303
    return _eintraege(db)[-1]["id"]


def test_aendern(client, db, welt):
    eid = _eintrag(client, db)
    seite = f"/lehrperson/tagebuch/{eid}"
    assert _feld(client.get(seite).text) == "Erster Text"
    gleich = _anlegen(client, seite, "Erster Text")
    assert gleich.status_code == 303
    assert gleich.headers["location"] == f"{seite}?erledigt=gespeichert"
    assert "geändert" not in client.get(gleich.headers["location"]).text
    db.execute("UPDATE tagebucheintraege SET erstellt = '2026-11-23T17:40:00Z'")
    db.commit()
    assert _anlegen(client, seite, "Zweiter Text").status_code == 303
    text = client.get(seite).text
    assert "geändert" in text
    assert _feld(text) == "Zweiter Text"
    leer = _anlegen(client, seite, "")
    assert leer.status_code == 400
    assert "Zum Löschen bitte ‹Eintrag löschen› wählen." in leer.text
    assert _eintraege(db)[0]["text"] == "Zweiter Text"


def test_eintrag_mit_aufnahme(client, db, lehrperson, einstellungen, welt):
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis, 5)
    eid = testdaten.lege_eintrag_an(db, lehrperson["id"], "aufnahme", "Notiz", aufnahme_id=aid)
    db.commit()
    seite = f"/lehrperson/tagebuch/{eid}"
    text = client.get(seite).text
    assert "Gesprochener Eintrag" in text
    assert "Notiz zur Aufnahme (freiwillig)" in text
    assert "<audio" in text and f'src="/lehrperson/aufnahmen/{aid}"' in text
    assert 'preload="none"' in text
    assert "5 Sek." in text
    assert _anlegen(client, seite, "").status_code == 303
    assert (
        db.execute("SELECT text FROM tagebucheintraege WHERE id = ?", (eid,)).fetchone()[0] is None
    )


def test_loeschen_doppelt_404(client, db, lehrperson, einstellungen, welt):
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    eid = testdaten.lege_eintrag_an(db, lehrperson["id"], "aufnahme", None, aufnahme_id=aid)
    db.commit()
    assert len(list(einstellungen.aufnahmen_verzeichnis.iterdir())) == 1
    pfad = f"/lehrperson/tagebuch/{eid}/loeschen"
    seite = client.get(pfad)
    assert "Diesen Eintrag löschen? Das lässt sich nicht rückgängig machen." in seite.text
    csrf = csrf_von(client, pfad)
    antwort = client.post(pfad, data={"csrf": csrf})
    assert antwort.status_code == 303
    assert antwort.headers["location"] == "/lehrperson/eintraege?erledigt=geloescht"
    assert client.post(pfad, data={"csrf": csrf}).status_code == 404
    assert client.get(pfad).status_code == 404
    assert list(einstellungen.aufnahmen_verzeichnis.iterdir()) == []
    assert "Gelöscht." in client.get(antwort.headers["location"]).text


def test_eintrag_escapt_unformatiert(client, db, welt):
    roh = "<b>x</b> **f**\r\nZeile"
    antwort = _anlegen(client, f"{NEU}/frei", roh)
    assert antwort.status_code == 303
    assert _eintraege(db)[0]["text"] == "<b>x</b> **f**\nZeile"
    for adresse in (antwort.headers["location"], "/lehrperson/eintraege"):
        text = client.get(adresse).text
        assert "&lt;b&gt;" in text and "**f**" in text
        assert "<b>x" not in text and "<strong>" not in text


def test_meine_eintraege(client, db, lehrperson, einstellungen, heute_ist):
    rid, (f1, _) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    imp = testdaten.lege_impuls_an(db, "Impuls Jetzt", "2026-11-23")
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], "Antwort A")
    e_frei = testdaten.lege_eintrag_an(db, lehrperson["id"], "frei", "Frei Text")
    e_imp = testdaten.lege_eintrag_an(db, lehrperson["id"], "impuls", "Imp Text", impuls_id=imp)
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis, 60)
    e_auf = testdaten.lege_eintrag_an(db, lehrperson["id"], "aufnahme", "Notiz", aufnahme_id=aid)
    stamm = [
        ("antworten", f"WHERE frage_id = {f1}", "2026-11-23T10:00:00Z", None),
        ("tagebucheintraege", f"WHERE id = {e_frei}", "2026-11-24T10:00:00Z", None),
        (
            "tagebucheintraege",
            f"WHERE id = {e_imp}",
            "2026-11-25T10:00:00Z",
            "2026-11-26T10:00:00Z",
        ),
        ("tagebucheintraege", f"WHERE id = {e_auf}", "2026-11-27T10:00:00Z", None),
    ]
    for tabelle, wo, erstellt, geaendert in stamm:
        db.execute(
            f"UPDATE {tabelle} SET erstellt = ?, geaendert = ? {wo}",
            (erstellt, geaendert or erstellt),
        )
    db.commit()
    heute_ist(date(2026, 11, 30))
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson/eintraege").text
    assert "bereich--eintraege" in text
    reihenfolge = [
        "Gesprochener Eintrag",
        "Zum Impuls: Impuls Jetzt",
        "Freier Eintrag",
        "Runde Eins",
    ]
    stellen = [text.index(x) for x in reihenfolge]
    assert stellen == sorted(stellen)
    for marke in ("Runde", "Tagebuch", "Impuls"):
        assert f">{marke}</span>" in text
    assert "1 von 2 Fragen beantwortet" in text
    assert "Aufnahme, 1 Min." in text
    assert text.count("geändert") == 1
    assert "Nur du und die Projektleiterin sehen sie." in text
    assert f'href="/lehrperson/runden/{rid}"' in text
    assert f'href="/lehrperson/tagebuch/{e_frei}"' in text


def test_meine_eintraege_aufnahme_ohne_dauer(client, db, lehrperson, einstellungen, welt):
    aid = testdaten.lege_aufnahme_an(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    db.execute("UPDATE aufnahmen SET dauer_sekunden = NULL WHERE id = ?", (aid,))
    testdaten.lege_eintrag_an(db, lehrperson["id"], "aufnahme", None, aufnahme_id=aid)
    db.commit()
    text = client.get("/lehrperson/eintraege").text
    assert "Aufnahme</" in text
    assert "Aufnahme," not in text


def test_meine_eintraege_verschobene_runde(client, db, lehrperson, heute_ist):
    rid, (f1, _) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], "Antwort A")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    assert "Runde Eins" in client.get("/lehrperson/eintraege").text
    db.execute("UPDATE runden SET freischaltdatum = '2026-12-14' WHERE id = ?", (rid,))
    db.commit()
    text = client.get("/lehrperson/eintraege").text
    assert "Runde Eins" not in text and "Antwort A" not in text
    assert db.execute("SELECT text FROM antworten").fetchall()[0][0] == "Antwort A"


def test_meine_eintraege_leer(client, welt):
    text = client.get("/lehrperson/eintraege").text
    assert "Noch keine Einträge." in text
    assert "Ersten Tagebucheintrag schreiben" in text
