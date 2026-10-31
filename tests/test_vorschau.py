import re
from datetime import date
from pathlib import Path

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von

from app.routen.ohne_speichern import MELDUNG_VORSCHAU
from app.routen.verwaltung_vorschau import VorschauTag, band_vorschau, standardtag, vorschau_tage
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
            assert z in (V, "/abmelden", "/manifest.webmanifest") or z.startswith(
                ("/static/", tag)
            ), (
                seite,
                z,
            )
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


def _runde_am_7_12(db):
    _erster_tag(db)
    rid, fragen = testdaten.lege_runde_an(
        db,
        "Runde Zwei",
        "2026-12-07",
        fragen=(("freitext", "Frage A"), ("skala", "Frage B")),
    )
    db.commit()
    return rid, fragen


def _runde_und_csrf(leitung, db):
    rid, fragen = _runde_am_7_12(db)
    ids = [f if isinstance(f, int) else f["id"] for f in fragen]
    csrf = csrf_von(leitung, f"{V}/2026-12-07/runden/{rid}")
    return rid, ids, csrf


def test_post_runde_speichert_nichts(leitung, db):
    rid, (f1, f2), csrf = _runde_und_csrf(leitung, db)
    vorher = testdaten.abzug(db)
    antwort = leitung.post(
        f"{V}/2026-12-07/runden/{rid}",
        data={"csrf": csrf, f"antwort_{f1}": "Mein Text", f"antwort_{f2}": "4"},
    )
    assert antwort.status_code == 200
    assert re.search(r'role="status"[^>]*>[^<]*' + re.escape(MELDUNG_VORSCHAU), antwort.text)
    assert re.search(r"<textarea[^>]*>\s*Mein Text", antwort.text)
    assert re.search(
        r'<input[^>]*value="4"[^>]*checked|<input[^>]*checked[^>]*value="4"', antwort.text
    )
    assert testdaten.abzug(db) == vorher


def test_post_runde_ungueltig_400(leitung, db):
    rid, (f1, f2), csrf = _runde_und_csrf(leitung, db)
    vorher = testdaten.abzug(db)
    url = f"{V}/2026-12-07/runden/{rid}"
    antwort = leitung.post(url, data={"csrf": csrf, f"antwort_{f2}": "7"})
    assert antwort.status_code == 400
    assert "Bitte einen Wert von 1 bis 5 wählen." in antwort.text
    assert MELDUNG_VORSCHAU not in antwort.text
    antwort = leitung.post(url, data={"csrf": csrf, f"antwort_{f1}": "x" * 20_001})
    assert antwort.status_code == 400
    assert "höchstens 20\u00a0000 Zeichen" in antwort.text
    assert testdaten.abzug(db) == vorher


def test_post_runde_nicht_sichtbar_404(leitung, db):
    rid, _, csrf = _runde_und_csrf(leitung, db)
    vorher = testdaten.abzug(db)
    assert leitung.post(f"{V}/2026-12-06/runden/{rid}", data={"csrf": csrf}).status_code == 404
    assert leitung.post(f"{V}/2026-12-07/runden/999", data={"csrf": csrf}).status_code == 404
    assert testdaten.abzug(db) == vorher


def test_post_ohne_csrf_403(leitung, db):
    _runde_am_7_12(db)
    antwort = leitung.post(f"{V}/2026-12-07/runden/999", data={})
    assert antwort.status_code == 403
    assert "Formular abgelaufen" in antwort.text


def test_post_tagebuch(leitung, db):
    _, _, csrf = _runde_und_csrf(leitung, db)
    iid = testdaten.lege_impuls_an(db, "Impuls Spaet", "2026-12-14")
    db.commit()
    vorher = testdaten.abzug(db)
    basis = f"{V}/2026-12-07/tagebuch/neu"
    antwort = leitung.post(f"{basis}/frei", data={"csrf": csrf, "text": "Notiz"})
    assert antwort.status_code == 200
    assert MELDUNG_VORSCHAU in antwort.text
    assert re.search(r"<textarea[^>]*>\s*Notiz", antwort.text)
    antwort = leitung.post(f"{basis}/frei", data={"csrf": csrf, "text": " "})
    assert antwort.status_code == 400
    assert "Der Eintrag ist noch leer." in antwort.text
    for text in ("x", ""):
        antwort = leitung.post(f"{basis}/impuls/{iid}", data={"csrf": csrf, "text": text})
        assert antwort.status_code == 404
    antwort = leitung.post(f"{basis}/leitfrage/999", data={"csrf": csrf, "text": "x"})
    assert antwort.status_code == 404
    assert testdaten.abzug(db) == vorher


def test_post_escapt(leitung, db):
    _, _, csrf = _runde_und_csrf(leitung, db)
    antwort = leitung.post(
        f"{V}/2026-12-07/tagebuch/neu/frei",
        data={"csrf": csrf, "text": "<script>x</script> **f**"},
    )
    assert "&lt;script&gt;x&lt;/script&gt;" in antwort.text
    assert "**f**" in antwort.text
    assert "<script>x" not in antwort.text and "<strong>f" not in antwort.text


def _d(tag, monat=11):
    return date(2026, monat, tag)


def test_standardtag():
    assert standardtag(_d(16), _d(23)) == _d(23)
    assert standardtag(_d(1, 12), _d(23)) == _d(1, 12)
    assert standardtag(_d(16), None) == _d(16)


def test_vorschau_tage():
    runden = [
        {"titel": "D", "freischaltdatum": "2026-11-16"},
        {"titel": "A", "freischaltdatum": "2026-11-23"},
        {"titel": "B", "freischaltdatum": "2026-11-23"},
        {"titel": "C", "freischaltdatum": "2026-11-30"},
        {"titel": "E", "freischaltdatum": "2026-11-09"},
    ]
    assert vorschau_tage(runden, _d(16), _d(23)) == [
        VorschauTag(_d(9), False, None, ["E"]),
        VorschauTag(_d(16), True, None, ["D"]),
        VorschauTag(_d(23), False, 1, ["A", "B"]),
        VorschauTag(_d(30), False, 2, ["C"]),
    ]
    assert vorschau_tage([], _d(16), _d(23)) == [VorschauTag(_d(16), True, None, [])]


def test_auswahlseite(leitung, db):
    _erster_tag(db)
    testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_runde_an(db, "Runde Zwei", "2026-11-23")
    db.commit()
    text = leitung.get(V).text
    assert "<h1>Vorschau</h1>" in text
    assert re.search(
        r'href="/verwaltung/vorschau/2026-11-16"[^>]*>[^<]*(<[^>]+>\s*)*Heute, Mo 16.11.2026', text
    )
    assert 'href="/verwaltung/vorschau/2026-11-23"' in text
    assert "Woche 1, ab Mo 23.11.2026: Runde Eins · Runde Zwei" in " ".join(text.split())
    assert re.search(r'<input[^>]*name="am"[^>]*required', text) or re.search(
        r'<input[^>]*required[^>]*name="am"', text
    )
    assert 'href="/gast"' in text
    assert "Diese Ansicht ist öffentlich" in text
    assert re.search(r'href="/verwaltung"[^>]*>\s*‹ Verwaltung', text)


def test_auswahl_weiterleitungen(leitung, db):
    _erster_tag(db)
    leitung.follow_redirects = False
    for abfrage, ziel in [
        ("?am=2026-11-30", f"{V}/2026-11-30"),
        ("?am=2026-11-30&ziel=info", f"{V}/2026-11-30/info"),
        ("?ziel=info", f"{V}/2026-11-23/info"),
    ]:
        antwort = leitung.get(V + abfrage)
        assert antwort.status_code == 303, abfrage
        assert antwort.headers["location"] == ziel
    for abfrage in ("?ziel=x", "?am=abc", "?am=2026-02-30", "?am=2019-01-01", "?am="):
        antwort = leitung.get(V + abfrage)
        assert antwort.status_code == 200, abfrage
        assert "Vorschau" in antwort.text


def test_links_in_verwaltung(leitung, db):
    rid, _ = testdaten.lege_runde_an(db, "Runde Eins", "2026-12-07")
    db.commit()
    start = leitung.get("/verwaltung").text
    assert re.search(r'<a class="karte karte--link" href="/verwaltung/vorschau"', start)
    assert re.search(
        r'<nav class="verwaltungsnavigation".*href="/verwaltung/vorschau".*</nav>', start, re.DOTALL
    )
    text = leitung.get("/verwaltung/inhalte").text
    assert re.search(r'href="/verwaltung/vorschau"[^>]*>\s*So sieht es eine Lehrperson', text)
    text = leitung.get("/verwaltung/inhalte/info").text
    assert 'href="/verwaltung/vorschau?ziel=info"' in text
    text = leitung.get(f"/verwaltung/inhalte/runden/{rid}").text
    link = f'href="/verwaltung/vorschau/2026-12-07/runden/{rid}"'
    assert re.search(link + r"[^>]*>\s*Diese Runde ansehen", text)
    db.execute("UPDATE runden SET freischaltdatum = '2026-12-14'")
    db.commit()
    text = leitung.get(f"/verwaltung/inhalte/runden/{rid}").text
    assert f'href="/verwaltung/vorschau/2026-12-14/runden/{rid}"' in text


def test_kommentarzeilen_bleiben(leitung):
    for datei in ("start.html", "rahmen.html"):
        text = (Path("app/templates/verwaltung") / datei).read_text(encoding="utf-8")
        assert "{# #19:" in text
        assert "{# Trennzeile zwischen #18 und #19, nicht ändern #}" in text
