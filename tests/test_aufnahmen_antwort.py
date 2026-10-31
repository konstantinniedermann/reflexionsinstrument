import re
from datetime import date
from io import BytesIO

import pytest
import testdaten
from conftest import als_lehrperson, als_leitung, csrf_von

from app import aufnahmen
from app.db import transaktion

WEBM = b"\x1aE\xdf\xa3" + bytes(60)
JETZT = "2026-11-24T10:00:00Z"
ALT = "2026-11-01T00:00:00Z"


@pytest.fixture
def verzeichnis(einstellungen):
    return einstellungen.aufnahmen_verzeichnis


@pytest.fixture
def frage_id(db):
    _, fragen = testdaten.lege_runde_an(
        db, titel="Runde", freischaltdatum="2026-10-01", fragen=(("freitext", "Frage 1"),)
    )
    db.commit()
    return fragen[0]


def neue_datei(verzeichnis):
    return aufnahmen.schreibe_datei(BytesIO(WEBM), verzeichnis)


def mit_aufnahme(db, verzeichnis, frage_id, konto_id, text="Getippt"):
    datei = neue_datei(verzeichnis)
    with transaktion(db):
        aufnahme_id = aufnahmen.lege_aufnahme_an(db, konto_id, datei, 5)
        antwort_id = testdaten.lege_antwort_an(
            db, frage_id, konto_id, text=text, aufnahme_id=aufnahme_id
        )
    return antwort_id, aufnahme_id, datei


def antwort(db, frage_id, konto_id):
    return db.execute(
        "SELECT * FROM antworten WHERE frage_id = ? AND konto_id = ?", (frage_id, konto_id)
    ).fetchone()


def anzahl_aufnahmen(db, konto_id):
    return db.execute("SELECT COUNT(*) FROM aufnahmen WHERE konto_id = ?", (konto_id,)).fetchone()[
        0
    ]


def test_neue_antwort_nur_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    aufnahmen.haenge_an_antwort(db, kid, frage_id, neue_datei(verzeichnis), 7, verzeichnis, JETZT)
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] is None
    assert zeile["skalawert"] is None
    assert zeile["aufnahme_id"] is not None
    assert zeile["erstellt"] == zeile["geaendert"] == JETZT
    assert aufnahmen.aufnahme_der_antwort(db, kid, frage_id)["dauer_sekunden"] == 7


def test_textantwort_erhaelt_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    testdaten.lege_antwort_an(db, frage_id, kid, text="Getippt")
    db.execute("UPDATE antworten SET erstellt = ?, geaendert = ?", (ALT, ALT))
    db.commit()
    aufnahmen.haenge_an_antwort(
        db, kid, frage_id, neue_datei(verzeichnis), None, verzeichnis, JETZT
    )
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert zeile["geaendert"] == JETZT
    assert zeile["erstellt"] == ALT
    assert zeile["aufnahme_id"] is not None


def test_ersetzen_loescht_alte_datei(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    erste = neue_datei(verzeichnis)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, erste, 1, verzeichnis, JETZT)
    # Text setzen, damit er den Ersatz ueberlebt
    db.execute("UPDATE antworten SET text = 'Getippt' WHERE konto_id = ?", (kid,))
    db.commit()
    zweite = neue_datei(verzeichnis)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, zweite, 2, verzeichnis, JETZT)
    assert anzahl_aufnahmen(db, kid) == 1
    assert not (verzeichnis / erste.name).exists()
    assert (verzeichnis / zweite.name).exists()
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert aufnahmen.aufnahme_der_antwort(db, kid, frage_id)["dateiname"] == zweite.name


def test_loeschen_text_bleibt(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    *_, datei = mit_aufnahme(db, verzeichnis, frage_id, kid)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    zeile = antwort(db, frage_id, kid)
    assert zeile["text"] == "Getippt"
    assert zeile["aufnahme_id"] is None
    assert not (verzeichnis / datei.name).exists()
    assert anzahl_aufnahmen(db, kid) == 0


def test_loeschen_nur_aufnahme_loescht_zeile(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    _, _, datei = mit_aufnahme(db, verzeichnis, frage_id, kid, text=None)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    assert antwort(db, frage_id, kid) is None
    assert not (verzeichnis / datei.name).exists()


def test_loeschen_ohne_aufnahme(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    testdaten.lege_antwort_an(db, frage_id, kid, text="Nur Text")
    db.commit()
    vorher = testdaten.abzug(db)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is False
    assert testdaten.abzug(db) == vorher


def test_fremde_antwort_unberuehrt(db, verzeichnis, frage_id, lehrperson, zweite_lehrperson):
    kid, zid = lehrperson["id"], zweite_lehrperson["id"]
    mit_aufnahme(db, verzeichnis, frage_id, zid)
    dateien = sorted(p.name for p in verzeichnis.iterdir())
    fremd_vorher = antwort(db, frage_id, zid)
    aufnahmen.haenge_an_antwort(db, kid, frage_id, neue_datei(verzeichnis), 3, verzeichnis, JETZT)
    assert aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT) is True
    assert tuple(antwort(db, frage_id, zid)) == tuple(fremd_vorher)
    assert anzahl_aufnahmen(db, zid) == 1
    assert all((verzeichnis / n).exists() for n in dateien)


def test_in_laufender_transaktion(db, verzeichnis, frage_id, lehrperson):
    kid = lehrperson["id"]
    datei = neue_datei(verzeichnis)
    with transaktion(db):
        with pytest.raises(RuntimeError):
            aufnahmen.haenge_an_antwort(db, kid, frage_id, datei, None, verzeichnis, JETZT)
        with pytest.raises(RuntimeError):
            aufnahmen.loesche_aufnahme_der_antwort(db, kid, frage_id, verzeichnis, JETZT)


def test_datenbankfehler_alte_aufnahme_bleibt(db, verzeichnis, frage_id, lehrperson, monkeypatch):
    kid = lehrperson["id"]
    *_, alt = mit_aufnahme(db, verzeichnis, frage_id, kid)
    vorher = testdaten.abzug(db)

    def kaputt(*args, **kwargs):
        raise RuntimeError("Datenbankfehler")

    monkeypatch.setattr(aufnahmen, "lege_aufnahme_an", kaputt)
    neu = neue_datei(verzeichnis)
    with pytest.raises(RuntimeError, match="Datenbankfehler"):
        aufnahmen.haenge_an_antwort(db, kid, frage_id, neu, None, verzeichnis, JETZT)
    assert testdaten.abzug(db) == vorher
    assert (verzeichnis / alt.name).exists()


# --- Task 6: Routen und Seite ---

RUNDE_TAG = date(2026, 11, 24)


@pytest.fixture
def runde(db, lehrperson, heute_ist, client):
    heute_ist(RUNDE_TAG)
    rid, (f1, f2) = testdaten.lege_runde_an(
        db,
        titel="Runde",
        freischaltdatum="2026-11-23",
        fragen=(("freitext", "Wie lief es heute?"), ("skala", "Wie ruhig?")),
    )
    db.commit()
    als_lehrperson(client, lehrperson)
    return rid, f1, f2


def adresse(rid, fid, ende="aufnahme"):
    return f"/lehrperson/runden/{rid}/fragen/{fid}/{ende}"


def hochladen(client, pfad, **felder):
    daten = {"csrf": csrf_von(client, "/lehrperson/info"), **felder}
    return client.post(
        pfad,
        files={"aufnahme": ("a.webm", WEBM, "audio/webm")},
        data=daten,
        follow_redirects=False,
    )


def test_antwort_seite(client, runde):
    rid, f1, _ = runde
    r = client.get(adresse(rid, f1))
    assert r.status_code == 200
    for teil in (
        "Wie lief es heute?",
        "Deine geschriebene Antwort bleibt erhalten.",
        f'data-anker="frage-{f1}"',
        f'href="/lehrperson/runden/{rid}#frage-{f1}"',
        'class="inhalt bereich--runden"',
        "/static/js/aufnahme.js",
    ):
        assert teil in r.text
    assert "ersetzt die bisherige" not in r.text
    assert 'name="text"' not in r.text


def test_antwort_hochladen(client, runde, db, lehrperson):
    rid, f1, _ = runde
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], text="Getippt")
    db.commit()
    r = hochladen(client, adresse(rid, f1), dauer_sekunden="3")
    assert r.status_code == 303
    assert r.headers["location"] == f"/lehrperson/runden/{rid}?erledigt=gespeichert#frage-{f1}"
    assert antwort(db, f1, lehrperson["id"])["text"] == "Getippt"
    assert antwort(db, f1, lehrperson["id"])["aufnahme_id"] is not None
    assert "Die neue Aufnahme ersetzt die bisherige." in client.get(adresse(rid, f1)).text


def test_antwort_ueber_einer_mib(client, runde, db, einstellungen, verzeichnis):
    rid, f1, _ = runde
    gross = testdaten.WEBM_ANFANG + bytes(int(2.5 * 1024 * 1024))
    csrf = csrf_von(client, "/lehrperson/info")
    r = client.post(
        adresse(rid, f1),
        files={"aufnahme": ("a.webm", gross, "audio/webm")},
        data={"csrf": csrf},
        follow_redirects=False,
    )
    assert r.status_code == 303
    name = db.execute("SELECT dateiname FROM aufnahmen").fetchone()[0]
    assert (verzeichnis / name).read_bytes() == gross


def test_antwort_fehler_nach_schreiben_raeumt_auf(
    client, runde, db, lehrperson, verzeichnis, monkeypatch
):
    rid, f1, _ = runde
    testdaten.lege_antwort_an(db, f1, lehrperson["id"], text="Getippt")
    db.commit()

    def kaputt(*_args, **_kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(aufnahmen, "haenge_an_antwort", kaputt)
    with pytest.raises(RuntimeError):
        hochladen(client, adresse(rid, f1))
    assert list(verzeichnis.iterdir()) == []
    assert anzahl_aufnahmen(db, lehrperson["id"]) == 0
    zeile = antwort(db, f1, lehrperson["id"])
    assert zeile["text"] == "Getippt"
    assert zeile["aufnahme_id"] is None


def test_antwort_ungueltig_400(client, runde, einstellungen, db):
    rid, f1, _ = runde
    vorher = testdaten.abzug(db)
    r = client.post(
        adresse(rid, f1),
        files={"aufnahme": ("a.webm", b"kein Ton", "audio/webm")},
        data={"csrf": csrf_von(client, "/lehrperson/info")},
    )
    assert r.status_code == 400
    assert testdaten.abzug(db) == vorher
    assert list(einstellungen.aufnahmen_verzeichnis.iterdir()) == []


@pytest.mark.parametrize("fall", ["skala", "andere_runde", "unsichtbar", "unbekannt"])
def test_antwort_404(client, runde, db, einstellungen, fall):
    rid, _, f2 = runde
    _, (fremd,) = testdaten.lege_runde_an(
        db, titel="Andere", freischaltdatum="2026-11-16", fragen=(("freitext", "Andere"),)
    )
    spaet, (fspaet,) = testdaten.lege_runde_an(
        db, titel="Spaet", freischaltdatum="2026-11-30", fragen=(("freitext", "Spaet"),)
    )
    db.commit()
    ziel = {
        "skala": (rid, f2),
        "andere_runde": (rid, fremd),
        "unsichtbar": (spaet, fspaet),
        "unbekannt": (rid, 999),
    }[fall]
    vorher = testdaten.abzug(db)
    ordner = sorted(einstellungen.aufnahmen_verzeichnis.iterdir())
    assert client.get(adresse(*ziel)).status_code == 404
    assert hochladen(client, adresse(*ziel)).status_code == 404
    assert client.get(adresse(*ziel, "aufnahme/loeschen")).status_code == 404
    daten = {"csrf": csrf_von(client, "/lehrperson/info")}
    assert client.post(adresse(*ziel, "aufnahme/loeschen"), data=daten).status_code == 404
    assert testdaten.abzug(db) == vorher
    assert sorted(einstellungen.aufnahmen_verzeichnis.iterdir()) == ordner


def test_aufnahme_loeschen_route(client, runde, db, lehrperson, verzeichnis):
    rid, f1, _ = runde
    _, _, datei = mit_aufnahme(db, verzeichnis, f1, lehrperson["id"])
    seite = client.get(adresse(rid, f1, "aufnahme/loeschen"))
    assert seite.status_code == 200
    for teil in (
        "Die Aufnahme zu dieser Frage löschen? Deine geschriebene Antwort bleibt.",
        "Endgültig löschen",
        "Abbrechen",
    ):
        assert teil in seite.text
    r = client.post(
        adresse(rid, f1, "aufnahme/loeschen"),
        data={"csrf": csrf_von(client, adresse(rid, f1, "aufnahme/loeschen"))},
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert (
        r.headers["location"] == f"/lehrperson/runden/{rid}?erledigt=aufnahme_geloescht#frage-{f1}"
    )
    runde_seite = client.get(f"/lehrperson/runden/{rid}?erledigt=aufnahme_geloescht")
    assert "Die Aufnahme wurde gelöscht." in runde_seite.text
    assert "Getippt" in runde_seite.text
    assert not (verzeichnis / datei.name).exists()


def test_aufnahme_loeschen_fremd_404(client, runde, db, lehrperson, zweite_lehrperson, verzeichnis):
    rid, f1, _ = runde
    _, _, datei = mit_aufnahme(db, verzeichnis, f1, lehrperson["id"])
    client.cookies.clear()
    als_lehrperson(client, zweite_lehrperson)
    vorher = testdaten.abzug(db)
    pfad = adresse(rid, f1, "aufnahme/loeschen")
    assert client.get(pfad).status_code == 404
    assert client.post(pfad, data={"csrf": csrf_von(client, "/lehrperson/info")}).status_code == 404
    assert testdaten.abzug(db) == vorher
    assert (verzeichnis / datei.name).exists()


def test_runde_platz(client, runde, db, lehrperson, verzeichnis):
    rid, f1, f2 = runde
    seite = client.get(f"/lehrperson/runden/{rid}").text
    assert f'name="anker" value="aufnahme-{f1}"' in seite
    assert "Antwort einsprechen" in seite
    assert f'value="aufnahme-{f2}"' not in seite
    _, aid, _ = mit_aufnahme(db, verzeichnis, f1, lehrperson["id"])
    seite = client.get(f"/lehrperson/runden/{rid}").text
    assert f'<audio controls preload="none" src="/lehrperson/aufnahmen/{aid}"' in seite
    assert "5 Sek." in seite
    assert re.search(rf'name="anker" value="aufnahme-{f1}"[^>]*>Aufnahme ersetzen<', seite)
    assert "Antwort einsprechen" not in seite
    assert f'href="{adresse(rid, f1, "aufnahme/loeschen")}">Aufnahme löschen' in seite


def test_runde_gast_ohne_platz(client, db, lehrperson, verzeichnis, auftraggeberin, runde):
    rid, f1, _ = runde
    mit_aufnahme(db, verzeichnis, f1, lehrperson["id"])
    client.cookies.clear()
    gast = client.get(f"/gast/runden/{rid}")
    assert gast.status_code == 200
    als_leitung(client, auftraggeberin)
    vorschau = client.get(f"/verwaltung/vorschau/2026-11-24/runden/{rid}")
    assert vorschau.status_code == 200
    for r in (gast, vorschau):
        assert "Wie lief es heute?" in r.text
        for teil in ("Antwort einsprechen", "/aufnahme", "<audio"):
            assert teil not in r.text


def test_speichern_und_einsprechen(client, runde):
    rid, f1, _ = runde
    r = client.post(
        f"/lehrperson/runden/{rid}",
        data={
            "csrf": csrf_von(client, f"/lehrperson/runden/{rid}"),
            f"antwort_{f1}": "Neu",
            "anker": f"aufnahme-{f1}",
        },
        follow_redirects=False,
    )
    assert r.status_code == 303
    assert r.headers["location"] == adresse(rid, f1)
    assert client.get(r.headers["location"]).status_code == 200


def test_loeschen_falsche_runde_404(client, runde, db, lehrperson, verzeichnis):
    rid, f1, _ = runde
    fremde_runde, (fremd,) = testdaten.lege_runde_an(
        db, titel="Andere", freischaltdatum="2026-11-16", fragen=(("freitext", "Andere"),)
    )
    db.commit()
    _, _, datei = mit_aufnahme(db, verzeichnis, f1, lehrperson["id"])
    vorher = testdaten.abzug(db)
    for runde_id, frage_id in ((fremde_runde, f1), (rid, fremd)):
        pfad = adresse(runde_id, frage_id, "aufnahme/loeschen")
        assert client.get(pfad).status_code == 404
        daten = {"csrf": csrf_von(client, "/lehrperson/info")}
        assert client.post(pfad, data=daten).status_code == 404
    assert testdaten.abzug(db) == vorher
    assert (verzeichnis / datei.name).exists()
