"""Was an einem Stichtag sichtbar ist. Einzige Stelle mit der Regel «Datum <= Stichtag»."""

import sqlite3
from datetime import date

from app import inhalte
from app.zeit import ist_erreicht


def sichtbare_runden(db: sqlite3.Connection, stichtag: date) -> list[sqlite3.Row]:
    return [
        zeile
        for zeile in inhalte.runden(db)
        if ist_erreicht(date.fromisoformat(zeile["freischaltdatum"]), stichtag)
    ]


def naechste_freischaltung(db: sqlite3.Connection, stichtag: date) -> date | None:
    spaetere = [
        datum
        for zeile in inhalte.runden(db)
        if not ist_erreicht(datum := date.fromisoformat(zeile["freischaltdatum"]), stichtag)
    ]
    return min(spaetere, default=None)


def sichtbare_runde(db: sqlite3.Connection, runde_id: int, stichtag: date) -> sqlite3.Row | None:
    zeile = inhalte.runde(db, runde_id)
    if zeile is None or not ist_erreicht(date.fromisoformat(zeile["freischaltdatum"]), stichtag):
        return None
    return zeile


def _sichtbare_impulse(db: sqlite3.Connection, stichtag: date) -> list[sqlite3.Row]:
    return [
        zeile
        for zeile in inhalte.impulse(db)
        if ist_erreicht(date.fromisoformat(zeile["sichtbar_ab"]), stichtag)
    ]


def aktueller_impuls(db: sqlite3.Connection, stichtag: date) -> sqlite3.Row | None:
    """Spaetestes `sichtbar_ab`, bei Gleichstand die hoechste `id` (Sortierung der Abfrage)."""
    sichtbare = _sichtbare_impulse(db, stichtag)
    return sichtbare[-1] if sichtbare else None


def sichtbarer_impuls(db: sqlite3.Connection, impuls_id: int, stichtag: date) -> sqlite3.Row | None:
    zeile = inhalte.impuls(db, impuls_id)
    if zeile is None or not ist_erreicht(date.fromisoformat(zeile["sichtbar_ab"]), stichtag):
        return None
    return zeile
