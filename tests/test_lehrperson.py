import re
from datetime import date
from pathlib import Path

import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von

from app.texte import REGISTER


def _erster_tag(db, tag="2026-11-23"):
    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', ?)", (tag,))
    db.commit()


def _inhalte(db):
    _erster_tag(db)
    runde_id, frage_ids = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_runde_an(db, "Runde Geheim", "2026-11-30")
    testdaten.lege_impuls_an(db, "Impuls Eins", "2026-11-23")
    db.commit()
    return runde_id, frage_ids


def test_start_ohne_inhalte(client, lehrperson):
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson").text
    assert "Hallo, Anna Beispiel" in text
    assert "Noch keine Runde." in text
    assert not re.search(r"Woche \d", text)


def test_start_mit_inhalten(client, lehrperson, db, heute_ist):
    _inhalte(db)
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson").text
    assert "Woche 1" in text
    assert "Runde Eins" in text
    assert "Nächste Runde ab Mo 30.11." in text
    assert "Runde Geheim" not in text
    assert "Impuls Eins" in text
    assert "Dazu schreiben" in text
    assert "Jetzt beantworten" in text
    assert REGISTER["hinweis_wer_sieht_was"].vorschlag[:40] in text
    assert 'class="inhalt bereich--start"' in text
    assert re.search(r'<a [^>]*href="/lehrperson"[^>]*aria-current="page"', text) or re.search(
        r'<a [^>]*aria-current="page"[^>]*href="/lehrperson"', text
    )
    assert 'href="/lehrperson/eintraege"' in text


def test_start_vor_erster_runde(client, lehrperson, db, heute_ist):
    _inhalte(db)
    heute_ist(date(2026, 11, 22))
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson").text
    assert "Die erste Runde erscheint am Mo 23.11." in text
    assert "Impuls dieser Woche" not in text


def test_start_antwortstand(client, lehrperson, db, heute_ist):
    _, frage_ids = _inhalte(db)
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    testdaten.lege_antwort_an(db, frage_ids[0], lehrperson["id"])
    db.commit()
    assert "Angefangen, 1 von 2" in client.get("/lehrperson").text
    testdaten.lege_antwort_an(db, frage_ids[1], lehrperson["id"], None, 3)
    db.commit()
    text = client.get("/lehrperson").text
    assert "Beantwortet" in text
    assert "Angefangen" not in text


def test_start_zahl_eintraege(client, lehrperson, db, heute_ist):
    _inhalte(db)
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    testdaten.lege_eintrag_an(db, lehrperson["id"])
    db.commit()
    assert "1 Eintrag " in client.get("/lehrperson").text
    testdaten.lege_eintrag_an(db, lehrperson["id"])
    db.commit()
    assert "2 Einträge" in client.get("/lehrperson").text


def test_info(client, lehrperson, db):
    db.execute(
        "INSERT INTO info_abschnitte (titel, inhalt, reihenfolge) VALUES "
        "('Abschnitt A', 'Text **x** hier', 2), ('Abschnitt B', 'Text B', 1)"
    )
    db.commit()
    als_lehrperson(client, lehrperson)
    text = client.get("/lehrperson/info").text
    assert text.index("Abschnitt B") < text.index("Abschnitt A") < text.index("Datenschutz")
    assert len(re.findall(r"<details[^>]* open", text)) == 1
    assert re.search(r"<details[^>]* open[^>]*>\s*<summary>Abschnitt B", text)
    assert REGISTER["hinweis_datenspeicherung"].vorschlag[:40] in text
    assert "<strong>x</strong>" in text
    assert 'class="inhalt bereich--info"' in text


def test_kein_inline(client, lehrperson):
    als_lehrperson(client, lehrperson)
    for pfad in ("/lehrperson", "/lehrperson/info"):
        text = client.get(pfad).text
        assert "style=" not in text
        assert not re.search(r"<script(?![^>]*\bsrc=)", text)
        assert not re.search(r"<[^>]*\son[a-z]+=", text)


def test_auftraggeberin_403(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    assert client.get("/lehrperson/info").status_code == 403


def _entwurf_attribute(text: str) -> list[str]:
    return re.findall(r'data-entwurf="([^"]*)"', text)


def test_data_entwurf_attribute(client, lehrperson, db, heute_ist):
    runde_id, _ = _inhalte(db)
    impuls_id = testdaten.lege_impuls_an(db, "Impuls Zwei", "2026-11-23")
    leitfrage_id = testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    k = lehrperson["id"]
    runde = client.get(f"/lehrperson/runden/{runde_id}").text
    assert _entwurf_attribute(runde) == [f"{k}:runde-{runde_id}"]
    assert 'src="/static/js/entwurf.js"' in runde
    assert "Nicht gespeicherter Text wurde wiederhergestellt." in runde
    assert _entwurf_attribute(client.get("/lehrperson/tagebuch/neu/frei").text) == [f"{k}:neu-frei"]
    assert _entwurf_attribute(client.get(f"/lehrperson/tagebuch/neu/impuls/{impuls_id}").text) == [
        f"{k}:neu-impuls-{impuls_id}"
    ]
    assert _entwurf_attribute(
        client.get(f"/lehrperson/tagebuch/neu/leitfrage/{leitfrage_id}").text
    ) == [f"{k}:neu-leitfrage-{leitfrage_id}"]
    eintrag_id = testdaten.lege_eintrag_an(db, k, "frei", "Hallo")
    db.commit()
    seite = client.get(f"/lehrperson/tagebuch/{eintrag_id}").text
    assert _entwurf_attribute(seite) == [f"{k}:tagebuch-{eintrag_id}"]
    assert "data-entwurf-verwerfen" not in seite
    # Start und Info haben kein Formular mit Entwurf, aber das Skript braucht nur das Abmelden
    assert _entwurf_attribute(client.get("/lehrperson").text) == []


def test_verwerfen_nach_dem_anlegen(client, lehrperson, db, heute_ist):
    _erster_tag(db)
    impuls_id = testdaten.lege_impuls_an(db, "Impuls Zwei", "2026-11-23")
    leitfrage_id = testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    db.commit()
    heute_ist(date(2026, 11, 24))
    als_lehrperson(client, lehrperson)
    k = lehrperson["id"]
    faelle = [
        ("/lehrperson/tagebuch/neu/frei", f"{k}:neu-frei"),
        (f"/lehrperson/tagebuch/neu/impuls/{impuls_id}", f"{k}:neu-impuls-{impuls_id}"),
        (f"/lehrperson/tagebuch/neu/leitfrage/{leitfrage_id}", f"{k}:neu-leitfrage-{leitfrage_id}"),
    ]
    for pfad, schluessel in faelle:
        antwort = client.post(pfad, data={"csrf": csrf_von(client, pfad), "text": "Mein Text"})
        assert antwort.status_code == 303
        ziel = antwort.headers["location"]
        assert ziel.endswith("?erledigt=gespeichert")
        seite = client.get(ziel).text
        assert f'data-entwurf-verwerfen="{schluessel}"' in seite
        # ohne die Bestätigung (spätere Besuche) kein Verwerfen
        assert "data-entwurf-verwerfen" not in client.get(ziel.split("?")[0]).text


def test_skript_nur_auf_lehrpersonen_seiten(client, lehrperson, auftraggeberin):
    als_lehrperson(client, lehrperson)
    assert 'src="/static/js/entwurf.js"' in client.get("/lehrperson/tagebuch/neu/frei").text
    client.cookies.clear()
    als_leitung(client, auftraggeberin)
    text = client.get("/verwaltung").text
    assert "entwurf.js" not in text
    assert "data-entwurf" not in text


def test_entwurf_js_ist_klein_und_ohne_netz():
    quelle = (Path(__file__).parent.parent / "app/static/js/entwurf.js").read_text(encoding="utf-8")
    assert len(quelle.splitlines()) <= 120
    assert "fetch(" not in quelle
    assert "localStorage" not in quelle
    assert "sessionStorage" in quelle
