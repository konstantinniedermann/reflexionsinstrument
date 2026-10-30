"""Tagebuch-Aufnahme speichern: Grenzen vor dem Parsen, nichts bleibt bei Fehlern liegen."""

import os
import re
import shutil
import time
from collections import namedtuple
from datetime import date
from pathlib import Path

import pytest
import starlette.requests
import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von
from fastapi.routing import APIRoute, iter_route_contexts

from app import aufnahmen, eintraege, groesse
from app.main import erstelle_app
from app.texte import lies_text

WEBM = testdaten.WEBM_ANFANG + bytes(60)
MP4 = bytes(4) + b"ftypM4A " + bytes(60)
SEITE = "/lehrperson/tagebuch/neu/aufnahme"
ORT = re.compile(r"^/lehrperson/tagebuch/(\d+)\?erledigt=gespeichert$")


def sende(client, dateien, **felder):
    daten = {"csrf": csrf_von(client, SEITE), **felder}
    return client.post(SEITE, files=dateien, data=daten)


def datei(inhalt=WEBM, name="aufnahme.webm", typ="audio/webm"):
    return {"aufnahme": (name, inhalt, typ)}


def ordner(einstellungen):
    return sorted(p.name for p in einstellungen.aufnahmen_verzeichnis.iterdir())


@pytest.fixture
def lp(client, lehrperson):
    return als_lehrperson(client, lehrperson)


def test_seite(lp, db):
    r = lp.get(SEITE)
    assert r.status_code == 200
    assert re.search(r"<h1>\s*Frei sprechen\s*</h1>", r.text)
    for schluessel in ("hinweis_tagebuch", "hinweis_aufnahme"):
        assert lies_text(db, schluessel).split("\n")[0] in r.text
    for teil in (
        'enctype="multipart/form-data"',
        'name="aufnahme"',
        'accept="audio/*"',
        'maxlength="20000"',
        'name="dauer_sekunden"',
        'class="inhalt bereich--tagebuch"',
        "Etwas dazuschreiben (freiwillig)",
        "Stattdessen schreiben",
        "Dieser Browser kann hier nicht aufnehmen.",
    ):
        assert teil in r.text
    assert "style=" not in r.text
    assert not re.search(r"<script(?![^>]*\ssrc=)", r.text)
    assert not re.search(r"<[^>]+\son\w+=", r.text)


def test_upload_ok(lp, lehrperson, db, einstellungen):
    r = sende(lp, datei(MP4, "bild.html", "text/html"), dauer_sekunden="42", text=" Notiz\r\nzwei ")
    assert r.status_code == 303
    treffer = ORT.match(r.headers["location"])
    assert treffer
    zeile = db.execute("SELECT * FROM aufnahmen").fetchone()
    assert zeile["konto_id"] == lehrperson["id"]
    assert zeile["mime_typ"] == "audio/mp4"
    assert zeile["groesse_bytes"] == len(MP4)
    assert zeile["dauer_sekunden"] == 42
    assert zeile["dateiname"].endswith(".m4a")
    assert (einstellungen.aufnahmen_verzeichnis / zeile["dateiname"]).read_bytes() == MP4
    e = db.execute("SELECT * FROM tagebucheintraege").fetchone()
    assert e["id"] == int(treffer.group(1))
    assert e["art"] == "aufnahme"
    assert e["text"] == "Notiz\nzwei"
    assert e["aufnahme_id"] == zeile["id"]
    assert e["erstellt"] == e["geaendert"]
    seite = lp.get(r.headers["location"])
    assert "Gespeichert." in seite.text
    assert "<audio" in seite.text
    assert f'src="/lehrperson/aufnahmen/{zeile["id"]}"' in seite.text


def test_upload_ohne_text_und_dauer(lp, db):
    assert sende(lp, datei()).status_code == 303
    assert db.execute("SELECT text FROM tagebucheintraege").fetchone()["text"] is None
    assert db.execute("SELECT dauer_sekunden FROM aufnahmen").fetchone()[0] is None


UNGUELTIG = {
    "ohne_datei": ({}, {}, MELDUNG := "Diese Aufnahme liess sich nicht speichern."),
    "leer": (datei(b""), {}, MELDUNG),
    "textfeld": ({}, {"aufnahme": "x"}, MELDUNG),
    "unbekanntes_format": (datei(b"ID3\x04" + bytes(60)), {}, MELDUNG),
    "dauer_buchstaben": (datei(), {"dauer_sekunden": "abc"}, MELDUNG),
    "dauer_negativ": (datei(), {"dauer_sekunden": "-1"}, MELDUNG),
    "dauer_611": (datei(), {"dauer_sekunden": "611"}, MELDUNG),
    "dauer_riesig": (datei(), {"dauer_sekunden": "9" * 20}, MELDUNG),
    "text_zu_lang": (datei(), {"text": "x" * 20_001}, "höchstens 20 000 Zeichen"),
}


@pytest.mark.parametrize("fall", UNGUELTIG)
def test_upload_ungueltig(lp, db, einstellungen, fall):
    dateien, felder, meldung = UNGUELTIG[fall]
    vorher = testdaten.abzug(db)
    r = sende(lp, dateien, **felder)
    assert r.status_code == 400
    # Tausendertrennzeichen ist ein geschuetztes Leerzeichen
    assert meldung in re.sub(r"\s", " ", r.text)
    assert testdaten.abzug(db) == vorher
    assert ordner(einstellungen) == []


def _kein_parsen(monkeypatch):
    async def form(self, *args, **kwargs):
        raise AssertionError("geparst")

    monkeypatch.setattr(starlette.requests.Request, "form", form)


def test_zu_gross_ohne_parsen(lp, monkeypatch):
    _kein_parsen(monkeypatch)
    r = lp.post(
        SEITE,
        content=b"x" * (aufnahmen.MAX_ANFRAGE_BYTES + 1),
        headers={"content-type": "multipart/form-data; boundary=x"},
    )
    assert r.status_code == 413
    assert "Zu gross" in r.text


def test_sehr_lange_content_length_413(lp, monkeypatch):
    _kein_parsen(monkeypatch)
    r = lp.post(
        SEITE,
        content=b"x",
        headers={"content-type": "multipart/form-data; boundary=x", "content-length": "9" * 5000},
    )
    assert r.status_code == 413
    assert "Zu gross" in r.text


def test_ohne_anmeldung_ohne_parsen(client, monkeypatch):
    _kein_parsen(monkeypatch)
    r = client.post(SEITE, files=datei(), data={"csrf": "x"})
    assert r.status_code == 303
    assert r.headers["location"] == "/"


def test_ohne_content_length_411(lp, einstellungen):
    def teile():
        yield b"--x\r\n"
        yield b"--x--\r\n"

    r = lp.post(SEITE, content=teile(), headers={"content-type": "multipart/form-data; boundary=x"})
    assert r.status_code == 411
    assert ordner(einstellungen) == []


def test_datei_zu_gross(lp, einstellungen, monkeypatch):
    monkeypatch.setattr(aufnahmen, "MAX_BYTES", 1000)
    r = sende(lp, datei(WEBM + bytes(1000)))
    assert r.status_code == 413
    assert ordner(einstellungen) == []


def test_ohne_csrf_403(lp, einstellungen):
    r = lp.post(SEITE, files=datei())
    assert r.status_code == 403
    assert "Formular abgelaufen" in r.text
    assert ordner(einstellungen) == []


def test_speicher_knapp_503(lp, db, einstellungen, monkeypatch):
    Platz = namedtuple("Platz", "total used free")
    monkeypatch.setattr(shutil, "disk_usage", lambda pfad: Platz(100, 100, 0))
    vorher = testdaten.abzug(db)
    r = sende(lp, datei())
    assert r.status_code == 503
    assert ordner(einstellungen) == []
    assert testdaten.abzug(db) == vorher


def test_fehler_nach_schreiben_raeumt_auf(lp, db, einstellungen, monkeypatch):
    def kaputt(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(eintraege, "lege_tagebucheintrag_an", kaputt)
    csrf = csrf_von(lp, SEITE)
    with pytest.raises(RuntimeError):
        lp.post(SEITE, files=datei(), data={"csrf": csrf})
    assert db.execute("SELECT COUNT(*) FROM aufnahmen").fetchone()[0] == 0
    assert ordner(einstellungen) == []


def test_waisen_nach_upload(lp, einstellungen):
    waise = einstellungen.aufnahmen_verzeichnis / ("a" * 32 + ".webm")
    waise.write_bytes(WEBM)
    alt = time.time() - 7200
    os.utime(waise, (alt, alt))
    assert sende(lp, datei()).status_code == 303
    assert not waise.exists()
    assert len(ordner(einstellungen)) == 1


def _ohne_body_parameter(dependant):
    return not dependant.body_params and all(
        _ohne_body_parameter(d) for d in dependant.dependencies
    )


def test_upload_routen_ohne_body_parameter(einstellungen):
    gefunden = 0
    for r in iter_route_contexts(erstelle_app(einstellungen).routes):
        if not isinstance(r.original_route, APIRoute) or "POST" not in (r.methods or ()):
            continue
        pfad = re.sub(r"\{[^}]+\}", "1", r.path)
        if any(m.fullmatch(pfad) for m in groesse.UPLOAD_PFADE):
            gefunden += 1
            assert _ohne_body_parameter(r.original_route.dependant), r.path
    assert gefunden >= 1


def test_eintrag_loeschen_mit_echter_datei(lp, db, einstellungen):
    r = sende(lp, datei())
    eid = ORT.match(r.headers["location"]).group(1)
    aid = db.execute("SELECT id FROM aufnahmen").fetchone()[0]
    csrf = csrf_von(lp, f"/lehrperson/tagebuch/{eid}/loeschen")
    assert lp.post(f"/lehrperson/tagebuch/{eid}/loeschen", data={"csrf": csrf}).status_code == 303
    assert ordner(einstellungen) == []
    assert db.execute("SELECT COUNT(*) FROM aufnahmen").fetchone()[0] == 0
    assert lp.get(f"/lehrperson/aufnahmen/{aid}").status_code == 404


def test_auftraggeberin_403(client, auftraggeberin):
    als_leitung(client, auftraggeberin)
    assert client.get(SEITE).status_code == 403


def test_aufraeumen_fehler_aendert_nichts(lp, db, einstellungen, monkeypatch, caplog):
    def kaputt(*args, **kwargs):
        raise OSError("kaputt")

    monkeypatch.setattr(aufnahmen.os, "scandir", kaputt)
    with caplog.at_level("WARNING"):
        r = sende(lp, datei())
    monkeypatch.undo()
    assert r.status_code == 303
    assert db.execute("SELECT COUNT(*) FROM tagebucheintraege").fetchone()[0] == 1
    assert len(ordner(einstellungen)) == 1
    meldungen = [x.getMessage() for x in caplog.records if "Aufraeumen" in x.getMessage()]
    assert meldungen == ["Aufraeumen der Aufnahmen fehlgeschlagen"]


MELDUNGEN = (
    "verweigert",
    "kein-mikrofon",
    "besetzt",
    "nicht-unterstuetzt",
    "angehalten",
    "noch-eine-minute",
    "hoechstdauer",
    "zu-gross",
    "keine-verbindung",
    "abgemeldet",
    "abgelaufen",
    "ungueltig",
    "serverfehler",
    "wird-gespeichert",
)


def test_aufnehmen_markup(lp):
    text = lp.get(SEITE).text
    assert 'data-max-dauer="600"' in text
    assert 'data-max-bytes="15728640"' in text
    assert re.search(r'<script src="/static/js/aufnahme\.js" defer></script>', text)
    for name in MELDUNGEN:
        assert re.search(rf'<[^>]+data-meldung="{name}"[^>]*\shidden', text), name
    # Der Start-Knopf steckt in einem versteckten Teil: ohne JavaScript nicht sichtbar.
    start = text.index('data-aktion="start"')
    offen = [m.start() for m in re.finditer(r"<div[^>]*\shidden", text[:start])]
    assert offen
    assert "</div>" not in text[offen[-1] : start]
    assert "Das Mikrofon ist nicht freigegeben." in text
    assert "So gibst du das Mikrofon frei" in text
    assert re.search(r'href="/lehrperson/tagebuch/neu/frei"[^>]*>\s*Stattdessen schreiben', text)
    assert "data-entwurf" not in text
    assert "style=" not in text
    assert not re.search(r"<script(?![^>]*\ssrc=)", text)
    assert not re.search(r"<[^>]+\son\w+=", text)


def test_skript_nur_auf_aufnahme_seiten(lp):
    for pfad in ("/lehrperson", "/lehrperson/tagebuch/neu", "/lehrperson/tagebuch/neu/frei"):
        r = lp.get(pfad)
        assert r.status_code == 200, pfad
        assert "aufnahme.js" not in r.text, pfad


def test_wahl_frei_sprechen(lp):
    text = lp.get("/lehrperson/tagebuch/neu").text
    assert 'href="/lehrperson/tagebuch/neu/aufnahme"' in text
    assert "Frei sprechen" in text
    assert "Eintrag einsprechen, zum Beispiel direkt nach dem Unterricht." in text


def _wahl_ohne_link(text):
    assert "Frei sprechen" in text
    assert "In dieser Ansicht nicht verfügbar." in text
    assert "karte--ruhend" in text
    assert "/aufnahme" not in text
    assert "Eintrag einsprechen" not in text


def test_wahl_gast_ohne_link(client, auftraggeberin, heute_ist):
    heute_ist(date(2026, 11, 24))
    r = client.get("/gast/tagebuch/neu")
    assert r.status_code == 200
    _wahl_ohne_link(r.text)
    als_leitung(client, auftraggeberin)
    r = client.get("/verwaltung/vorschau/2026-11-24/tagebuch/neu")
    assert r.status_code == 200
    _wahl_ohne_link(r.text)


def test_eintrag_ohne_platzhalter():
    vorlage = Path(__file__).parent.parent / "app/templates/lehrperson/tagebuch_eintrag.html"
    assert "#17:" not in vorlage.read_text(encoding="utf-8")
