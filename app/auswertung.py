"""Zahlen der Seite «Eintraege» (Auftraggeberin). Fachlogik ohne FastAPI, ohne eigenes SQL."""

import sqlite3
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from app import konten, zeit
from app.aufnahmen import aufnahme_pfad
from app.eintraege import (
    Eintrag,
    Stand,
    Zeile,
    anzahl_tagebucheintraege,
    rundenstand,
)
from app.export import woche_von
from app.sichtbar import sichtbare_runden


@dataclass(frozen=True)
class Personenkarte:
    konto_id: int
    anzeigename: str
    runden: int  # sichtbare Runden mit mindestens einer Frage
    beantwortet: int  # davon: jede Frage beantwortet
    angefangen: int  # davon: mindestens eine, aber nicht alle
    tagebucheintraege: int
    zuletzt: date | None  # Zuerich; None, solange nichts geschrieben wurde
    stand: dict[int, Stand]


def personenkarten(db: sqlite3.Connection, heute: date, zeilen: list[Zeile]) -> list[Personenkarte]:
    """Eine Karte je Lehrperson, in der Reihenfolge von `lehrpersonen`."""
    offene = [r["id"] for r in sichtbare_runden(db, heute) if r["anzahl_fragen"] > 0]
    zuletzt: dict[int, str] = {}
    for z in zeilen:  # ISO-Text in UTC: der Textvergleich entspricht dem Zeitvergleich
        zuletzt[z.konto_id] = max(z.geaendert, zuletzt.get(z.konto_id, ""))
    ergebnis = []
    for person in konten.lehrpersonen(db):
        stand = rundenstand(db, person["id"])
        staende = [stand[runde_id] for runde_id in offene if runde_id in stand]
        ergebnis.append(
            Personenkarte(
                konto_id=person["id"],
                anzeigename=person["anzeigename"],
                runden=len(offene),
                beantwortet=sum(1 for s in staende if s.beantwortet == s.fragen),
                angefangen=sum(1 for s in staende if 0 < s.beantwortet < s.fragen),
                tagebucheintraege=anzahl_tagebucheintraege(db, person["id"]),
                zuletzt=zeit.lokal(zuletzt[person["id"]]).date()
                if person["id"] in zuletzt
                else None,
                stand=stand,
            )
        )
    return ergebnis


@dataclass(frozen=True)
class Karte:
    eintrag: Eintrag
    woche: int | None  # None ohne Projektstart


def karten(eintraege: list[Eintrag], projektstart: date | None) -> list[Karte]:
    return [Karte(e, woche_von(e.erstellt, projektstart)) for e in eintraege]


@dataclass(frozen=True)
class Exportstand:
    zeilen: int
    aufnahmen: int
    bytes: int


def exportstand(zeilen: list[Zeile], verzeichnis: Path) -> Exportstand:
    """Was der Gesamtexport jetzt enthielte; fehlende Dateien und Namen ohne Muster zaehlen 0 Bytes."""
    mit_aufnahme = [z for z in zeilen if z.aufnahme_id is not None]
    gesamt = 0
    for z in mit_aufnahme:
        pfad = aufnahme_pfad(verzeichnis, z.aufnahme_dateiname) if z.aufnahme_dateiname else None
        try:
            gesamt += pfad.stat().st_size if pfad else 0
        except OSError:
            pass
    return Exportstand(len(zeilen), len(mit_aufnahme), gesamt)


def groesse_text(anzahl_bytes: int) -> str:
    if anzahl_bytes < 1_000_000:
        return "weniger als 1 MB"
    return f"etwa {round(anzahl_bytes / 1_000_000)} MB"
