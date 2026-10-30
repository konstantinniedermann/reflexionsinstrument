"""Inhalte der Seiten, getrennt von Route und Ansicht (Lehrperson, Gast, Vorschau)."""

import sqlite3

from app import inhalte
from app.ansicht import Ansicht
from app.eintraege import Stand, anzahl_tagebucheintraege, rundenstand
from app.konten import finde_konto
from app.sichtbar import aktueller_impuls, naechste_freischaltung, sichtbare_runden
from app.texte import lies_text
from app.zeit import woche

VORLAGEN: dict[str, str] = {
    "start": "lehrperson/start.html",
    "info": "lehrperson/info.html",
}


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
