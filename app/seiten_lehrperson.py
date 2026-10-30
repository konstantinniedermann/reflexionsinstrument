"""Inhalte der Seiten, getrennt von Route und Ansicht (Lehrperson, Gast, Vorschau)."""

import sqlite3
from collections.abc import Mapping

from fastapi import HTTPException

from app import inhalte
from app.ansicht import Ansicht
from app.eintraege import Stand, antworten_der_runde, anzahl_tagebucheintraege, rundenstand
from app.konten import finde_konto
from app.sichtbar import (
    aktueller_impuls,
    naechste_freischaltung,
    sichtbare_runde,
    sichtbare_runden,
)
from app.texte import lies_text
from app.zeit import woche

VORLAGEN: dict[str, str] = {
    "start": "lehrperson/start.html",
    "info": "lehrperson/info.html",
    "runde": "lehrperson/runde.html",
    "runde_loeschen": "lehrperson/loeschen.html",
}

MELDUNG_FEHLER = "Bitte prüfe die markierten Felder."


def _marke(stand: Stand | None) -> tuple[str, str] | None:
    """Text und Klasse der Marke einer Runde; ohne Stand oder ohne Fragen keine Marke."""
    if stand is None or stand.fragen == 0:
        return None
    if stand.beantwortet == 0:
        return "Jetzt beantworten", "marke--offen"
    if stand.beantwortet >= stand.fragen:
        return "Beantwortet", "marke--erledigt"
    return f"Angefangen, {stand.beantwortet} von {stand.fragen}", "marke"


def kontext_start(db: sqlite3.Connection, ansicht: Ansicht) -> dict:
    konto_id = ansicht.konto_id
    projektstart = inhalte.lies_projektstart(db)
    konto = finde_konto(db, konto_id) if konto_id is not None else None
    staende = rundenstand(db, konto_id) if konto_id is not None else {}
    sichtbare = sichtbare_runden(db, ansicht.stichtag)
    return {
        "ansicht": ansicht,
        "bereich": "start",
        "anzeigename": konto.anzeigename if konto else None,
        "woche": woche(ansicht.stichtag, projektstart) if projektstart else None,
        "begruessung": lies_text(db, "begruessung"),
        "hinweis": lies_text(db, "hinweis_wer_sieht_was"),
        "impuls": aktueller_impuls(db, ansicht.stichtag),
        "runden": [
            {"runde": zeile, "marke": _marke(staende.get(zeile["id"]))} for zeile in sichtbare
        ],
        "naechste": naechste_freischaltung(db, ansicht.stichtag),
        "anzahl_eintraege": (
            anzahl_tagebucheintraege(db, konto_id) if ansicht.zeigt_eintraege else None
        ),
    }


def kontext_info(db: sqlite3.Connection, ansicht: Ansicht) -> dict:
    return {
        "ansicht": ansicht,
        "bereich": "info",
        "abschnitte": inhalte.info_abschnitte(db),
        "datenschutz": lies_text(db, "hinweis_datenspeicherung"),
    }


def kontext_runde(
    db: sqlite3.Connection,
    ansicht: Ansicht,
    runde_id: int,
    eingaben: Mapping[str, str] | None = None,
    fehler: dict[str, str] | None = None,
    meldung: str | None = None,
) -> dict:
    """Formularwerte aus `eingaben` ersetzen gespeicherte Antworten; Felder ohne Wert behalten sie."""
    runde = sichtbare_runde(db, runde_id, ansicht.stichtag)
    if runde is None:
        raise HTTPException(404)
    konto_id = ansicht.konto_id
    antworten = antworten_der_runde(db, konto_id, runde_id) if konto_id is not None else {}
    fehler = fehler or {}
    zeilen = []
    for frage in inhalte.fragen(db, runde_id):
        feld = f"antwort_{frage['id']}"
        antwort = antworten.get(frage["id"])
        if eingaben is not None and feld in eingaben:
            wert = eingaben[feld]
        elif antwort is None:
            wert = ""
        elif frage["typ"] == "skala":
            wert = "" if antwort["skalawert"] is None else str(antwort["skalawert"])
        else:
            wert = antwort["text"] or ""
        zeilen.append({"frage": frage, "feld": feld, "wert": wert, "fehler": fehler.get(feld)})
    return {
        "ansicht": ansicht,
        "bereich": "runden",
        "meldung": meldung or (MELDUNG_FEHLER if fehler else None),
        "runde": runde,
        "zeilen": zeilen,
        "antworten": antworten,
        "zuletzt": max((a["geaendert"] for a in antworten.values()), default=None),
        "hinweis": lies_text(db, "hinweis_tagebuch"),
    }
