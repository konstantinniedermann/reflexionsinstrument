"""Dateien der Aufnahmen: Namensmuster, Pfad, Format, Schreiben, Loeschen, Waisen."""

import logging
import os
import re
import secrets
import shutil
import sqlite3
import time
from pathlib import Path
from typing import BinaryIO, NamedTuple

from app import groesse

MAX_DAUER_SEKUNDEN = 600
TOLERANZ_SEKUNDEN = 10
MAX_BYTES = 15 * 1024 * 1024
MAX_ANFRAGE_BYTES = groesse.GRENZE_UPLOAD
RESERVE_BYTES = 50 * 1024 * 1024
WAISEN_ALTER_SEKUNDEN = 3600
BLOCK_BYTES = 1024 * 1024

DATEINAME = re.compile(r"[0-9a-f]{32}\.(webm|m4a|ogg)")
WAISE = re.compile(r"[0-9a-f]{32}\.(webm|m4a|ogg)(\.teil)?")
MELDUNG_400 = "Diese Aufnahme liess sich nicht speichern. Bitte neu aufnehmen."

_log = logging.getLogger(__name__)


def aufnahme_pfad(verzeichnis: Path, dateiname: str) -> Path | None:
    """Pfad im Aufnahmen-Ordner; `None`, wenn der Name nicht zum Muster passt."""
    if not DATEINAME.fullmatch(dateiname):
        return None
    return verzeichnis / dateiname


def loesche_dateien(verzeichnis: Path, dateinamen: list[str]) -> None:
    """Loescht Dateien still: ohne Muster oder fehlend wird uebersprungen, Fehler nur geloggt."""
    for name in dateinamen:
        pfad = aufnahme_pfad(verzeichnis, name)
        if pfad is None:
            continue
        try:
            pfad.unlink(missing_ok=True)
        except OSError:
            # Ohne Dateinamen: die Namen sind personenbezogen verknuepfbar.
            _log.warning("Aufnahme-Datei liess sich nicht loeschen")


def aufnahmen_von_eintraegen(db: sqlite3.Connection, aufnahme_ids: list[int]) -> list[sqlite3.Row]:
    """Zeilen (`id`, `dateiname`) der genannten Aufnahmen."""
    if not aufnahme_ids:
        return []
    platzhalter = ", ".join("?" * len(aufnahme_ids))
    return db.execute(
        f"SELECT id, dateiname FROM aufnahmen WHERE id IN ({platzhalter}) ORDER BY id",
        aufnahme_ids,
    ).fetchall()


class AufnahmeFehler(Exception):
    def __init__(self, status: int, meldung: str = MELDUNG_400):
        super().__init__(meldung)
        self.status = status
        self.meldung = meldung


class Datei(NamedTuple):
    name: str
    mime_typ: str
    groesse: int


def erkenne_format(anfang: bytes) -> tuple[str, str] | None:
    """`(mime_typ, endung)` aus den ersten Bytes; `None`, wenn unbekannt."""
    if anfang[4:8] == b"ftyp":
        return "audio/mp4", ".m4a"
    if anfang.startswith(b"\x1aE\xdf\xa3"):
        return "audio/webm", ".webm"
    if anfang.startswith(b"OggS"):
        return "audio/ogg", ".ogg"
    return None


def lies_dauer(wert: str) -> int | None:
    """Leer ergibt `None`; sonst ASCII-Ziffern bis 610, alles andere ist ein 400."""
    if wert == "":
        return None
    if re.fullmatch(r"[0-9]{1,6}", wert) and int(wert) <= MAX_DAUER_SEKUNDEN + TOLERANZ_SEKUNDEN:
        return int(wert)
    raise AufnahmeFehler(400)


def schreibe_datei(quelle: BinaryIO, verzeichnis: Path) -> Datei:
    """Prueft Groesse, Platz und Format, schreibt dann ueber `.teil` atomar in den Ordner."""
    groesse_bytes = quelle.seek(0, os.SEEK_END)
    if groesse_bytes == 0:
        raise AufnahmeFehler(400)
    if groesse_bytes > MAX_BYTES:
        raise AufnahmeFehler(413)
    if shutil.disk_usage(verzeichnis).free - groesse_bytes < RESERVE_BYTES:
        _log.warning("Aufnahme abgelehnt: Speicherplatz knapp")
        raise AufnahmeFehler(503)
    quelle.seek(0)
    format_ = erkenne_format(quelle.read(12))
    if format_ is None:
        raise AufnahmeFehler(400)
    mime_typ, endung = format_
    quelle.seek(0)
    name = secrets.token_hex(16) + endung
    ziel = verzeichnis / name
    teil = verzeichnis / (name + ".teil")
    try:
        fd = os.open(teil, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as ausgabe:
            while block := quelle.read(BLOCK_BYTES):
                ausgabe.write(block)
        os.replace(teil, ziel)
    except BaseException:
        teil.unlink(missing_ok=True)
        raise
    return Datei(name, mime_typ, groesse_bytes)


def raeume_waisen(db: sqlite3.Connection, verzeichnis: Path, jetzt: float | None = None) -> int:
    """Loescht alte Dateien mit Aufnahme-Namen, die keine Zeile hat; Rueckgabe: Anzahl."""
    grenze = (time.time() if jetzt is None else jetzt) - WAISEN_ALTER_SEKUNDEN
    bekannt = {r["dateiname"] for r in db.execute("SELECT dateiname FROM aufnahmen")}
    geloescht = 0
    with os.scandir(verzeichnis) as eintraege:
        for eintrag in eintraege:
            if not WAISE.fullmatch(eintrag.name) or eintrag.name in bekannt:
                continue
            try:
                if not eintrag.is_file(follow_symlinks=False):
                    continue
                if eintrag.stat(follow_symlinks=False).st_mtime >= grenze:
                    continue
                os.unlink(eintrag.path)
                geloescht += 1
            except OSError:
                _log.warning("Aufnahme-Datei liess sich nicht loeschen")
    return geloescht


def eigene_aufnahme(db: sqlite3.Connection, konto_id: int, aufnahme_id: int) -> sqlite3.Row | None:
    """Aufnahme, nur wenn sie dem Konto gehoert."""
    return db.execute(
        "SELECT * FROM aufnahmen WHERE id = ? AND konto_id = ?", (aufnahme_id, konto_id)
    ).fetchone()


def aufnahme(db: sqlite3.Connection, aufnahme_id: int) -> sqlite3.Row | None:
    """Aufnahme eines beliebigen Kontos (nur fuer die Auftraggeberin)."""
    return db.execute("SELECT * FROM aufnahmen WHERE id = ?", (aufnahme_id,)).fetchone()
