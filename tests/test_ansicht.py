import re
import sqlite3
from datetime import date
from typing import Annotated

import pytest

from app.ansicht import Ansicht, fuer_gast, fuer_lehrperson, fuer_vorschau
from app.konten import Konto

TAG = date(2026, 11, 30)


def test_konto_nur_bei_lehrperson():
    for args in [
        ("gast", TAG, "/gast", 1),
        ("vorschau", TAG, "/x", 2),
        ("lehrperson", TAG, "/lehrperson", None),
    ]:
        with pytest.raises(ValueError):
            Ansicht(*args)


def test_fuer_lehrperson():
    konto = Konto(id=7, anzeigename="A", benutzername="a", rolle="lehrperson", sitzungsversion=1)
    ansicht = fuer_lehrperson(konto, TAG)
    assert ansicht.speichert and ansicht.zeigt_eintraege
    assert ansicht.url("/runden/3") == "/lehrperson/runden/3"
    assert ansicht.konto_id == 7
    assert ansicht.stichtag == TAG
    assert ansicht.ausgang is None


def test_fuer_gast():
    ansicht = fuer_gast(TAG, "Band", ("Anmelden", "/"))
    assert ansicht.basis == "/gast"
    assert ansicht.konto_id is None
    assert not ansicht.speichert
    assert ansicht.band == "Band"
    assert ansicht.ausgang == ("Anmelden", "/")


def test_fuer_vorschau():
    ansicht = fuer_vorschau(date(2026, 12, 7), "B", ("Vorschau beenden", "/verwaltung/vorschau"))
    assert ansicht.url("/info") == "/verwaltung/vorschau/2026-12-07/info"
    assert not ansicht.zeigt_eintraege


@pytest.fixture
def seiten_client(einstellungen):
    from fastapi import Depends, Request
    from fastapi.testclient import TestClient

    from app.db import hole_db
    from app.main import erstelle_app
    from app.seiten_lehrperson import (
        VORLAGEN,
        kontext_info,
        kontext_runde,
        kontext_start,
        kontext_tagebuch_neu,
        kontext_tagebuch_wahl,
    )
    from app.vorlagen import templates
    from app.zeit import hole_heute, lies_datum

    kontexte = {
        "start": kontext_start,
        "info": kontext_info,
        "tagebuch_wahl": kontext_tagebuch_wahl,
    }
    app = erstelle_app(einstellungen)

    @app.get("/test-gast/runde/{runde_id}")
    def test_gast_runde(
        request: Request,
        runde_id: int,
        db: Annotated[sqlite3.Connection, Depends(hole_db)],
        heute: Annotated[date, Depends(hole_heute)],
    ):
        ansicht = fuer_gast(heute, "Band Gast", ("Anmelden", "/"))
        kontext = kontext_runde(db, ansicht, runde_id)
        return templates.TemplateResponse(request, VORLAGEN["runde"], kontext)

    @app.get("/test-meldung/runde/{runde_id}/{frage_id}")
    def test_runde_meldung(
        request: Request,
        runde_id: int,
        frage_id: int,
        db: Annotated[sqlite3.Connection, Depends(hole_db)],
        heute: Annotated[date, Depends(hole_heute)],
    ):
        ansicht = fuer_gast(heute, "Band Gast", ("Anmelden", "/"))
        feld = f"antwort_{frage_id}"
        kontext = kontext_runde(
            db,
            ansicht,
            runde_id,
            eingaben={feld: "Neu"},
            fehler={feld: "Zu lang"},
            meldung="Nicht gespeichert.",
        )
        return templates.TemplateResponse(request, VORLAGEN["runde"], kontext)

    @app.get("/test-gast/tagebuch/impuls/{impuls_id}")
    def test_gast_tagebuch_impuls(
        request: Request,
        impuls_id: int,
        db: Annotated[sqlite3.Connection, Depends(hole_db)],
        heute: Annotated[date, Depends(hole_heute)],
    ):
        ansicht = fuer_gast(heute, "Band Gast", ("Anmelden", "/"))
        kontext = kontext_tagebuch_neu(db, ansicht, "impuls", impuls_id)
        return templates.TemplateResponse(request, VORLAGEN["tagebuch_neu"], kontext)

    @app.get("/test-meldung/tagebuch")
    def test_tagebuch_meldung(
        request: Request,
        db: Annotated[sqlite3.Connection, Depends(hole_db)],
        heute: Annotated[date, Depends(hole_heute)],
    ):
        ansicht = fuer_gast(heute, "Band Gast", ("Anmelden", "/"))
        kontext = kontext_tagebuch_neu(
            db,
            ansicht,
            "frei",
            text="Mein Text",
            fehler={"text": "Der Eintrag ist noch leer."},
            meldung="Nicht gespeichert.",
        )
        return templates.TemplateResponse(request, VORLAGEN["tagebuch_neu"], kontext)

    @app.get("/test-gast/{seite}")
    def test_gast(
        request: Request,
        seite: str,
        db: Annotated[sqlite3.Connection, Depends(hole_db)],
        heute: Annotated[date, Depends(hole_heute)],
    ):
        ansicht = fuer_gast(heute, "Band Gast", ("Anmelden", "/"))
        return templates.TemplateResponse(request, VORLAGEN[seite], kontexte[seite](db, ansicht))

    @app.get("/test-vorschau/{am}/{seite}")
    def test_vorschau(
        request: Request, am: str, seite: str, db: Annotated[sqlite3.Connection, Depends(hole_db)]
    ):
        ansicht = fuer_vorschau(
            lies_datum(am), "Band Vorschau", ("Vorschau beenden", "/verwaltung/vorschau")
        )
        return templates.TemplateResponse(request, VORLAGEN[seite], kontexte[seite](db, ansicht))

    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_gast_start_ohne_persoenliches(seiten_client, db, lehrperson, heute_ist):
    import testdaten

    _, frage_ids = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_antwort_an(db, frage_ids[0], lehrperson["id"])
    testdaten.lege_eintrag_an(db, lehrperson["id"])
    db.commit()
    seiten_client.app.state.heute = lambda: date(2026, 11, 24)
    text = seiten_client.get("/test-gast/start").text
    assert "Willkommen" in text
    assert "Band Gast" in text
    assert re.search(r'href="/"[^>]*>\s*Anmelden', text)
    assert "Anna Beispiel" not in text
    assert "Eintrag" not in text
    assert "Angefangen" not in text
    assert "/lehrperson/eintraege" not in text and "/gast/eintraege" not in text
    links = re.findall(r'href="(/[^"]*)"', text)
    assert any(link.startswith("/gast") for link in links)
    for link in links:
        assert link in ("/", "/static/css/style.css") or link.startswith("/gast"), link


def test_vorschau_rechnet_mit_stichtag(seiten_client, db):
    import testdaten

    db.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')")
    testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_runde_an(db, "Runde Drei", "2026-12-07")
    testdaten.lege_runde_an(db, "Runde Vier", "2026-12-14")
    db.commit()
    seiten_client.app.state.heute = lambda: date(2026, 11, 24)
    text = seiten_client.get("/test-vorschau/2026-12-07/start").text
    assert "Woche 3" in text
    assert "Runde Drei" in text
    assert "Runde Vier" not in text
    assert "Nächste Runde ab Mo 14.12." in text
    links = re.findall(r'href="(/[^"]*)"', text)
    praefix = "/verwaltung/vorschau/2026-12-07/"
    assert any(link.startswith(praefix) for link in links)
    for link in links:
        assert link in (
            "/static/css/style.css",
            "/verwaltung/vorschau",
            praefix.rstrip("/"),
        ) or link.startswith(praefix), link
    assert "/lehrperson" not in text


def test_gast_runde(seiten_client, db, lehrperson):
    import testdaten

    rid, (f1, _) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], "Geheimer Text")
    db.commit()
    seiten_client.app.state.heute = lambda: date(2026, 11, 24)
    text = seiten_client.get(f"/test-gast/runde/{rid}").text
    assert 'name="csrf"' in text
    assert f'action="/gast/runden/{rid}"' in text
    assert "data-entwurf" not in text
    assert "entwurf.js" not in text
    assert "löschen" not in text
    assert "Geheimer Text" not in text
    assert "Zuletzt gespeichert" not in text


def test_kontext_runde_eingaben_fehler_meldung(seiten_client, db):
    import testdaten

    rid, (f1, _) = testdaten.lege_runde_an(db, "Runde Eins", "2026-11-23")
    db.commit()
    seiten_client.app.state.heute = lambda: date(2026, 11, 24)
    text = seiten_client.get(f"/test-meldung/runde/{rid}/{f1}").text
    assert re.search(rf'name="antwort_{f1}"[^>]*>\s*Neu</textarea>', text)
    assert f'aria-describedby="fehler-antwort_{f1}"' in text
    assert re.search(rf'id="fehler-antwort_{f1}">Zu lang<', text)
    assert re.search(r'role="status">Nicht gespeichert\.<', text)


def test_gast_tagebuch(seiten_client, db):
    import testdaten

    imp = testdaten.lege_impuls_an(db, "Impuls Eins", "2026-11-23")
    testdaten.lege_leitfrage_an(db, "Leitfrage Eins")
    db.commit()
    seiten_client.app.state.heute = lambda: date(2026, 11, 24)
    wahl = seiten_client.get("/test-gast/tagebuch_wahl").text
    assert f'href="/gast/tagebuch/neu/impuls/{imp}"' in wahl
    assert 'href="/gast/tagebuch/neu/frei"' in wahl
    assert 'href="/gast/tagebuch/neu/leitfrage/1"' in wahl
    assert "/lehrperson" not in wahl
    formular = seiten_client.get(f"/test-gast/tagebuch/impuls/{imp}").text
    assert 'action="/gast/tagebuch/neu/impuls/' in formular
    assert 'name="csrf"' in formular
    assert "data-entwurf" not in formular
    assert "entwurf.js" not in formular
    assert "Impuls Eins" in formular


def test_tagebuch_meldung_und_fehler(seiten_client):
    text = seiten_client.get("/test-meldung/tagebuch").text
    assert "Mein Text" in text
    assert "Der Eintrag ist noch leer." in text
    assert "Nicht gespeichert." in text
