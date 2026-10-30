"""Antworten und Tagebuch einer Lehrperson. Fachlogik ohne FastAPI."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app import zeit
from app.aufnahmen import aufnahmen_von_eintraegen, loesche_dateien
from app.db import transaktion
from app.eingaben import InhaltFehler, langer_text
from app.inhalte import SKALA_MAX, SKALA_MIN

Eingabe = tuple[str | None, int | None]  # (text, skalawert)


def antworten_der_runde(
    db: sqlite3.Connection, konto_id: int, runde_id: int
) -> dict[int, sqlite3.Row]:
    """Antworten des Kontos zu den Fragen der Runde, nach `frage_id`."""
    zeilen = db.execute(
        "SELECT a.* FROM antworten a JOIN fragen f ON f.id = a.frage_id "
        "WHERE a.konto_id = ? AND f.runde_id = ?",
        (konto_id, runde_id),
    ).fetchall()
    return {z["frage_id"]: z for z in zeilen}


def _lies_skala(wert: str, feld: str) -> int | None:
    if wert == "":
        return None
    # Nur ASCII-Ziffern: isdigit() liesse auch andere Schriften zu.
    if wert.isascii() and wert.isdigit() and SKALA_MIN <= int(wert) <= SKALA_MAX:
        return int(wert)
    raise InhaltFehler(feld, f"Bitte einen Wert von {SKALA_MIN} bis {SKALA_MAX} wählen.")


def lies_runden_eingaben(
    fragen: list[sqlite3.Row], formular: Mapping[str, str]
) -> dict[int, Eingabe]:
    """Prueft die Felder `antwort_{id}` der Fragen; fehlende Felder bleiben weg."""
    ergebnis: dict[int, Eingabe] = {}
    for frage in fragen:
        feld = f"antwort_{frage['id']}"
        if feld not in formular:
            continue
        wert = formular[feld]
        if frage["typ"] == "skala":
            ergebnis[frage["id"]] = (None, _lies_skala(wert, feld))
        else:
            ergebnis[frage["id"]] = (langer_text(wert, feld, None), None)
    return ergebnis


def speichere_antworten(
    db: sqlite3.Connection,
    konto_id: int,
    eingaben: dict[int, Eingabe],
    jetzt: str | None = None,
) -> int:
    """Speichert nur Geaendertes; gibt die Anzahl geaenderter Zeilen zurueck."""
    jetzt = jetzt or zeit.zeitstempel()
    geaendert = 0
    with transaktion(db):
        for frage_id, (text, skalawert) in eingaben.items():
            alt = db.execute(
                "SELECT id, text, skalawert, aufnahme_id FROM antworten "
                "WHERE frage_id = ? AND konto_id = ?",
                (frage_id, konto_id),
            ).fetchone()
            leer = text is None and skalawert is None
            if alt is None:
                if leer:
                    continue
                db.execute(
                    "INSERT INTO antworten (frage_id, konto_id, text, skalawert, erstellt, "
                    "geaendert) VALUES (?, ?, ?, ?, ?, ?)",
                    (frage_id, konto_id, text, skalawert, jetzt, jetzt),
                )
            elif leer and alt["aufnahme_id"] is None:
                db.execute("DELETE FROM antworten WHERE id = ?", (alt["id"],))
            elif (alt["text"], alt["skalawert"]) == (text, skalawert):
                continue
            else:
                db.execute(
                    "UPDATE antworten SET text = ?, skalawert = ?, geaendert = ? WHERE id = ?",
                    (text, skalawert, jetzt, alt["id"]),
                )
            geaendert += 1
    return geaendert


def entferne_aufnahmen(db: sqlite3.Connection, aufnahme_ids: list[int]) -> list[str]:
    """Loescht die Zeilen in `aufnahmen` und gibt die Dateinamen zurueck.

    Innerhalb der Transaktion aufrufen; die Dateien loescht der Aufrufer erst nach dem COMMIT
    mit `aufnahmen.loesche_dateien`.
    """
    zeilen = aufnahmen_von_eintraegen(db, aufnahme_ids)
    for zeile in zeilen:
        db.execute("DELETE FROM aufnahmen WHERE id = ?", (zeile["id"],))
    return [zeile["dateiname"] for zeile in zeilen]


def loesche_antworten_der_runde(
    db: sqlite3.Connection, konto_id: int, runde_id: int, aufnahmen_verzeichnis: Path
) -> int:
    """Loescht alle Antworten des Kontos zur Runde samt Aufnahmen; gibt die Anzahl zurueck."""
    if db.in_transaction:
        raise RuntimeError(
            "Dateien werden erst nach dem COMMIT geloescht; keine laufende Transaktion"
        )
    with transaktion(db):
        zeilen = antworten_der_runde(db, konto_id, runde_id).values()
        aufnahme_ids = [z["aufnahme_id"] for z in zeilen if z["aufnahme_id"] is not None]
        for zeile in zeilen:
            db.execute("DELETE FROM antworten WHERE id = ?", (zeile["id"],))
        dateinamen = entferne_aufnahmen(db, aufnahme_ids)
    loesche_dateien(aufnahmen_verzeichnis, dateinamen)
    return len(zeilen)


@dataclass(frozen=True)
class Stand:
    beantwortet: int
    fragen: int


def rundenstand(db: sqlite3.Connection, konto_id: int) -> dict[int, Stand]:
    """Fuer jede Runde: wie viele ihrer Fragen das Konto beantwortet hat."""
    zeilen = db.execute(
        "SELECT r.id AS runde_id, COUNT(f.id) AS fragen, COUNT(a.id) AS beantwortet "
        "FROM runden r LEFT JOIN fragen f ON f.runde_id = r.id "
        "LEFT JOIN antworten a ON a.frage_id = f.id AND a.konto_id = ? "
        "GROUP BY r.id",
        (konto_id,),
    ).fetchall()
    return {z["runde_id"]: Stand(z["beantwortet"], z["fragen"]) for z in zeilen}
