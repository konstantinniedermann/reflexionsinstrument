"""Zugaenge: Anlegen, Pruefen, Passwoerter und Loeschen."""

import re
import secrets
import sqlite3
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import bcrypt

BCRYPT_RUNDEN: int = 12

MAX_PASSWORT_BYTES = 72
MIN_PASSWORT_ZEICHEN = 8
MAX_ANZEIGENAME = 60
BENUTZERNAME_MUSTER = re.compile(r"[a-z0-9.\-]{3,40}")

KONSONANTEN = "bdfgkmnprstvz"
VOKALE = "aeu"


class EingabeFehler(ValueError):
    """Ungueltige Eingabe; `feld` nennt das betroffene Formularfeld."""

    def __init__(self, feld: str, meldung: str):
        super().__init__(meldung)
        self.feld = feld


@dataclass(frozen=True)
class Konto:
    id: int
    anzeigename: str
    benutzername: str
    rolle: str
    sitzungsversion: int

    @classmethod
    def aus_zeile(cls, zeile: sqlite3.Row) -> "Konto":
        return cls(
            id=zeile["id"],
            anzeigename=zeile["anzeigename"],
            benutzername=zeile["benutzername"],
            rolle=zeile["rolle"],
            sitzungsversion=zeile["sitzungsversion"],
        )


def normalisiere_benutzername(text: str) -> str:
    return text.strip().lower()


def _pruefe_anzeigename(text: str) -> str:
    name = text.strip()
    if not name:
        raise EingabeFehler("anzeigename", "Bitte einen Namen eingeben.")
    if len(name) > MAX_ANZEIGENAME:
        raise EingabeFehler("anzeigename", "Der Name ist zu lang (höchstens 60 Zeichen).")
    return name


def _pruefe_benutzername(text: str) -> str:
    name = normalisiere_benutzername(text)
    if not BENUTZERNAME_MUSTER.fullmatch(name):
        raise EingabeFehler(
            "benutzername",
            "Der Benutzername darf nur Kleinbuchstaben, Ziffern, Punkt und Bindestrich "
            "enthalten (3 bis 40 Zeichen).",
        )
    return name


def pruefe_neues_passwort(passwort: str) -> None:
    if len(passwort) < MIN_PASSWORT_ZEICHEN:
        raise EingabeFehler("passwort", "Das Passwort braucht mindestens 8 Zeichen.")
    if len(passwort.encode("utf-8")) > MAX_PASSWORT_BYTES:
        raise EingabeFehler("passwort", "Das Passwort ist zu lang.")


def hash_passwort(passwort: str) -> str:
    salz = bcrypt.gensalt(rounds=BCRYPT_RUNDEN)
    return bcrypt.hashpw(passwort.encode("utf-8"), salz).decode("ascii")


@lru_cache(maxsize=4)
def _dummy_hash(runden: int) -> bytes:
    return bcrypt.hashpw(b"dummy-passwort", bcrypt.gensalt(rounds=runden))


def passwort_stimmt(passwort: str, passwort_hash: str | None) -> bool:
    daten = passwort.encode("utf-8")
    if passwort_hash is None:
        # Gleiche Rechenzeit wie bei einem echten Zugang, damit sich unbekannte
        # Benutzernamen nicht an der Antwortzeit erkennen lassen.
        if len(daten) <= MAX_PASSWORT_BYTES:
            bcrypt.checkpw(daten, _dummy_hash(BCRYPT_RUNDEN))
        return False
    if len(daten) > MAX_PASSWORT_BYTES:
        return False
    try:
        return bcrypt.checkpw(daten, passwort_hash.encode("ascii"))
    except ValueError:
        return False


def passwort_vorschlag() -> str:
    def silbe() -> str:
        return secrets.choice(KONSONANTEN) + secrets.choice(VOKALE)

    def block() -> str:
        return silbe() + silbe()

    return f"{block()}-{block()}-{block()}-{secrets.randbelow(100):02d}"


def lege_konto_an(
    db: sqlite3.Connection,
    anzeigename: str,
    benutzername: str,
    passwort: str,
    rolle: str = "lehrperson",
) -> Konto:
    name = _pruefe_anzeigename(anzeigename)
    login = _pruefe_benutzername(benutzername)
    pruefe_neues_passwort(passwort)
    # Zufaellige Startversion: Eine wiederverwendete Konto-ID (SQLite vergibt die hoechste
    # id nach einem Loeschen neu) darf alte Anmelde-Cookies nicht wieder gueltig machen.
    version = secrets.randbelow(2**31) + 1
    try:
        cursor = db.execute(
            "INSERT INTO konten (anzeigename, benutzername, passwort_hash, rolle, sitzungsversion)"
            " VALUES (?, ?, ?, ?, ?)",
            (name, login, hash_passwort(passwort), rolle, version),
        )
    except sqlite3.IntegrityError as fehler:
        if "benutzername" in str(fehler):
            raise EingabeFehler("benutzername", "Diesen Benutzernamen gibt es schon.") from fehler
        raise
    return Konto(cursor.lastrowid, name, login, rolle, version)


def finde_konto(db: sqlite3.Connection, konto_id: int) -> Konto | None:
    zeile = db.execute("SELECT * FROM konten WHERE id = ?", (konto_id,)).fetchone()
    return Konto.aus_zeile(zeile) if zeile else None


def finde_hash(db: sqlite3.Connection, benutzername: str) -> tuple[Konto, str] | None:
    zeile = db.execute(
        "SELECT * FROM konten WHERE benutzername = ?", (normalisiere_benutzername(benutzername),)
    ).fetchone()
    return (Konto.aus_zeile(zeile), zeile["passwort_hash"]) if zeile else None


def lehrpersonen(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT id, anzeigename, benutzername, erstellt FROM konten"
        " WHERE rolle = 'lehrperson' ORDER BY anzeigename COLLATE NOCASE, id"
    ).fetchall()


def setze_passwort(db: sqlite3.Connection, konto_id: int, passwort: str) -> None:
    pruefe_neues_passwort(passwort)
    db.execute(
        "UPDATE konten SET passwort_hash = ?, sitzungsversion = sitzungsversion + 1 WHERE id = ?",
        (hash_passwort(passwort), konto_id),
    )


def zaehle_daten(db: sqlite3.Connection, konto_id: int) -> dict[str, int]:
    return {
        tabelle: db.execute(
            f"SELECT COUNT(*) FROM {tabelle} WHERE konto_id = ?",
            (konto_id,),
        ).fetchone()[0]
        for tabelle in ("antworten", "tagebucheintraege", "aufnahmen")
    }


def loesche_konto(db: sqlite3.Connection, konto_id: int, aufnahmen_verzeichnis: Path) -> None:
    """Loescht Aufnahme-Dateien, dann das Konto samt Daten (Kaskade), in einer Transaktion."""
    db.execute("BEGIN IMMEDIATE")
    try:
        namen = db.execute("SELECT dateiname FROM aufnahmen WHERE konto_id = ?", (konto_id,))
        for zeile in namen.fetchall():
            # Nur der Dateiname zaehlt: ein manipulierter Eintrag darf nichts ausserhalb
            # des Ordners treffen.
            name = Path(zeile["dateiname"]).name
            if name in ("", ".", ".."):
                continue
            (aufnahmen_verzeichnis / name).unlink(missing_ok=True)
        db.execute("DELETE FROM konten WHERE id = ?", (konto_id,))
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise
