"""Fachlogik der Eingabemaske: Grundlagen (Titel, erster Tag, Begruessung) und Zaehler."""

import sqlite3
from datetime import date

from app.db import transaktion
from app.eingaben import LAENGE_TITEL_INSTRUMENT, InhaltFehler, datum_feld, kurzer_text
from app.texte import speichere_text
from app.zeit import lies_datum

STANDARD_TITEL = "Reflexionsinstrument"


def _lies_einstellung(db: sqlite3.Connection, schluessel: str) -> str | None:
    zeile = db.execute(
        "SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    return None if zeile is None else zeile["wert"]


def lies_titel(db: sqlite3.Connection) -> str:
    return _lies_einstellung(db, "titel") or STANDARD_TITEL


def lies_projektstart(db: sqlite3.Connection) -> date | None:
    wert = _lies_einstellung(db, "projektstart")
    return None if wert is None else lies_datum(wert)


def _setze_einstellung(db: sqlite3.Connection, schluessel: str, wert: str | None) -> None:
    if wert is None:
        db.execute("DELETE FROM einstellungen WHERE schluessel = ?", (schluessel,))
    else:
        db.execute(
            "INSERT INTO einstellungen (schluessel, wert) VALUES (?, ?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
            (schluessel, wert),
        )


def speichere_allgemein(
    db: sqlite3.Connection, titel: str, begruessung: str, projektstart: str
) -> None:
    with transaktion(db):
        sauberer_titel = kurzer_text(
            titel, "titel", LAENGE_TITEL_INSTRUMENT, "Bitte einen Titel eingeben."
        )
        try:
            speichere_text(db, "begruessung", begruessung)
        except InhaltFehler as fehler:
            raise InhaltFehler("begruessung", fehler.meldung) from fehler
        start = datum_feld(projektstart, "projektstart", pflicht=False)
        _setze_einstellung(db, "titel", sauberer_titel)
        _setze_einstellung(db, "projektstart", start)


def zaehle_inhalte(db: sqlite3.Connection) -> dict[str, int]:
    def anzahl(sql: str) -> int:
        return db.execute(sql).fetchone()[0]

    return {
        "info_abschnitte": anzahl("SELECT COUNT(*) FROM info_abschnitte"),
        "runden": anzahl("SELECT COUNT(*) FROM runden"),
        "fragen": anzahl("SELECT COUNT(*) FROM fragen"),
        "runden_ohne_fragen": anzahl(
            "SELECT COUNT(*) FROM runden r "
            "WHERE NOT EXISTS (SELECT 1 FROM fragen f WHERE f.runde_id = r.id)"
        ),
        "leitfragen": anzahl("SELECT COUNT(*) FROM leitfragen"),
        "impulse": anzahl("SELECT COUNT(*) FROM impulse"),
    }
