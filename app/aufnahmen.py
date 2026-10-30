"""Dateien der Aufnahmen. Grundstock aus #16: Namensmuster, Pfad, Loeschen."""

import logging
import re
import sqlite3
from pathlib import Path

DATEINAME = re.compile(r"[0-9a-f]{32}\.(webm|m4a|ogg)")

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
