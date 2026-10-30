"""Tabelle der Eintraege fuer Excel (CSV). Fachlogik ohne FastAPI."""

import csv
import io
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime

from app import zeit
from app.eintraege import Zeile

SPALTEN = (
    "Lehrperson",
    "Woche",
    "Datum",
    "Geändert",
    "Angeleitet oder freiwillig",
    "Art",
    "Runde",
    "Frage",
    "Antwort",
    "Skalawert",
    "Aufnahme",
)
ART_TEXT = {"runde": "Runde", "tagebuch": "Tagebuch", "impuls": "Impuls"}

_FORMEL_ANFAENGE = ("=", "+", "-", "@", "\t", "\r")
_DATUM_FORMAT = "%d.%m.%Y %H:%M"


def zelle(wert: str | int | None) -> str:
    """Zellenwert fuer die CSV: ohne ausfuehrbare Formel, Zeilenumbrueche als `\\n`."""
    if wert is None:
        return ""
    text = str(wert)
    formel = text.startswith(_FORMEL_ANFAENGE)  # vor der Normalisierung: '\r' zaehlt mit
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return f"'{text}" if formel else text


def woche_von(zeitstempel: str, projektstart: date | None) -> int | None:
    if projektstart is None:
        return None
    return zeit.woche(zeit.lokal(zeitstempel).date(), projektstart)


@dataclass(frozen=True)
class Exportzeile:
    zeile: Zeile
    woche: int | None
    erstellt: datetime  # Zuerich
    geaendert: datetime | None  # Zuerich; None, solange nie geaendert


def _sortierschluessel(eintrag: Exportzeile) -> tuple:
    z = eintrag.zeile
    # Tagebucheintraege haben kein Freischaltdatum und keine Reihenfolge: nie None vergleichen.
    return (
        eintrag.woche or 0,
        z.anzeigename.casefold(),
        z.konto_id,
        z.erstellt,
        z.runde_freischaltdatum or "",
        z.frage_reihenfolge or 0,
        z.quelle,
        z.id,
    )


def exportzeilen(zeilen: list[Zeile], projektstart: date | None) -> list[Exportzeile]:
    ergebnis = [
        Exportzeile(
            zeile=z,
            woche=woche_von(z.erstellt, projektstart),
            erstellt=zeit.lokal(z.erstellt),
            geaendert=None if z.geaendert == z.erstellt else zeit.lokal(z.geaendert),
        )
        for z in zeilen
    ]
    return sorted(ergebnis, key=_sortierschluessel)


def als_csv(eintraege: list[Exportzeile], aufnahme: Callable[[Zeile], str]) -> bytes:
    """Tabelle mit BOM und Semikolon, damit Excel sie mit Doppelklick richtig oeffnet."""
    puffer = io.StringIO()
    schreiber = csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    schreiber.writerow(SPALTEN)
    for e in eintraege:
        z = e.zeile
        werte = (
            z.anzeigename,
            e.woche,
            e.erstellt.strftime(_DATUM_FORMAT),
            None if e.geaendert is None else e.geaendert.strftime(_DATUM_FORMAT),
            "angeleitet" if z.angeleitet else "freiwillig",
            ART_TEXT[z.art],
            z.runde_titel,
            z.frage,
            z.text,
            z.skalawert,
            aufnahme(z),
        )
        schreiber.writerow(zelle(w) for w in werte)
    return ("﻿" + puffer.getvalue()).encode("utf-8")
