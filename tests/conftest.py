import re
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.db import verbinde
from app.konten import lege_konto_an
from app.main import erstelle_app


@pytest.fixture
def einstellungen(tmp_path):
    return Einstellungen(
        daten_verzeichnis=tmp_path / "daten",
        geheimer_schluessel="test-schluessel",
        produktion=False,
    )


@pytest.fixture
def client(einstellungen):
    with TestClient(erstelle_app(einstellungen), follow_redirects=False) as c:
        yield c


@pytest.fixture(autouse=True)
def schnelles_bcrypt(monkeypatch):
    monkeypatch.setattr("app.konten.BCRYPT_RUNDEN", 4)


def _lege_an(einstellungen, anzeigename, benutzername, passwort, rolle="lehrperson"):
    conn = verbinde(einstellungen.db_pfad)
    try:
        konto = lege_konto_an(conn, anzeigename, benutzername, passwort, rolle)
    finally:
        conn.close()
    return {"id": konto.id, "benutzername": benutzername, "passwort": passwort}


@pytest.fixture
def lehrperson(client, einstellungen):
    return _lege_an(einstellungen, "Anna Beispiel", "lp.anna", "anna-pass-1")


@pytest.fixture
def zweite_lehrperson(client, einstellungen):
    return _lege_an(einstellungen, "Ben Beispiel", "lp.ben", "ben-pass-12")


@pytest.fixture
def auftraggeberin(client, einstellungen):
    return _lege_an(
        einstellungen, "Projektleitung", "projektleitung", "leitung-pass-1", "auftraggeberin"
    )


def csrf_von(client, pfad="/") -> str:
    """Liest das versteckte csrf-Feld der Seite `pfad`."""
    treffer = re.search(r'name="csrf" value="([0-9a-f]+)"', client.get(pfad).text)
    assert treffer, f"kein csrf-Feld auf {pfad}"
    return treffer.group(1)


def anmelden(client, benutzername, passwort, dauerhaft=True, headers=None):
    """Meldet ueber die Login-Seite an; folgt keiner Weiterleitung."""
    daten = {"csrf": csrf_von(client), "benutzername": benutzername, "passwort": passwort}
    if dauerhaft:
        daten["dauerhaft"] = "1"
    return client.post("/anmelden", data=daten, headers=headers, follow_redirects=False)


@pytest.fixture
def festes_heute(client) -> date:
    """Setzt den Stichtag der App auf einen Montag und gibt ihn zurueck."""
    fest = date(2026, 11, 30)
    client.app.state.heute = lambda: fest
    return fest


@pytest.fixture
def db(einstellungen, client):
    """Verbindung zur Test-Datenbank; die Migration hat `client` schon ausgefuehrt."""
    conn = verbinde(einstellungen.db_pfad)
    yield conn
    conn.close()


def als_leitung(client, auftraggeberin):
    assert (
        anmelden(client, auftraggeberin["benutzername"], auftraggeberin["passwort"]).status_code
        == 303
    )
    return client


def als_lehrperson(client, lehrperson):
    assert anmelden(client, lehrperson["benutzername"], lehrperson["passwort"]).status_code == 303
    return client


def lege_antwort_an(db, frage_id, konto_id, text="Antwort", aufnahme_id=None) -> int:
    """Legt eine Antwort an, wie #16 sie spaeter speichert."""
    return db.execute(
        "INSERT INTO antworten (frage_id, konto_id, text, aufnahme_id) VALUES (?, ?, ?, ?)",
        (frage_id, konto_id, text, aufnahme_id),
    ).lastrowid


def lege_eintrag_an(db, konto_id, art="frei", impuls_id=None, leitfrage_id=None) -> int:
    """Legt einen Tagebucheintrag an; der Text wird aus der Quelle kopiert wie in #16."""
    impuls_text = leitfrage_text = None
    if impuls_id is not None:
        impuls_text = db.execute("SELECT text FROM impulse WHERE id = ?", (impuls_id,)).fetchone()[
            0
        ]
    if leitfrage_id is not None:
        leitfrage_text = db.execute(
            "SELECT text FROM leitfragen WHERE id = ?", (leitfrage_id,)
        ).fetchone()[0]
    return db.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text, impuls_id, impuls_text, "
        "leitfrage_id, leitfrage_text) VALUES (?, ?, 'Text', ?, ?, ?, ?)",
        (konto_id, art, impuls_id, impuls_text, leitfrage_id, leitfrage_text),
    ).lastrowid
