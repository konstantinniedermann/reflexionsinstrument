import re
from datetime import date

import testdaten
from conftest import als_lehrperson, als_leitung

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
