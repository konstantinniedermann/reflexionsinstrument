"""Inhalte der Seiten, getrennt von Route und Ansicht (Lehrperson, Gast, Vorschau)."""

import sqlite3
from collections.abc import Mapping

from fastapi import HTTPException

from app import inhalte
from app.ansicht import Ansicht
from app.eintraege import (
    Eintrag,
    Stand,
    antworten_der_runde,
    anzahl_tagebucheintraege,
    gruppiere,
    rundenstand,
    zeilen_von,
)
from app.konten import finde_konto
from app.sichtbar import (
    aktueller_impuls,
    naechste_freischaltung,
    sichtbare_runde,
    sichtbare_runden,
    sichtbarer_impuls,
)
from app.texte import lies_text
from app.zeit import woche

VORLAGEN: dict[str, str] = {
    "start": "lehrperson/start.html",
    "info": "lehrperson/info.html",
    "runde": "lehrperson/runde.html",
    "runde_loeschen": "lehrperson/loeschen.html",
    "tagebuch_wahl": "lehrperson/tagebuch_wahl.html",
    "tagebuch_neu": "lehrperson/tagebuch_neu.html",
    "tagebuch_eintrag": "lehrperson/tagebuch_eintrag.html",
    "eintraege": "lehrperson/eintraege.html",
}

MELDUNG_FEHLER = "Bitte prüfe die markierten Felder."


def _entwurf(ansicht: Ansicht, formular: str) -> str | None:
    """Schlüssel für den Entwurfsschutz im Browser; nur im Modus Lehrperson (sonst kein Schutz)."""
    return f"{ansicht.konto_id}:{formular}" if ansicht.speichert else None


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
        "hinweis_benachrichtigung": lies_text(db, "hinweis_benachrichtigung"),
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
        "entwurf": _entwurf(ansicht, f"runde-{runde_id}"),
    }


def kontext_tagebuch_wahl(db: sqlite3.Connection, ansicht: Ansicht) -> dict:
    return {
        "ansicht": ansicht,
        "bereich": "tagebuch",
        "meldung": None,
        "impuls": aktueller_impuls(db, ansicht.stichtag),
        "leitfragen": inhalte.leitfragen(db),
    }


ARTEN_NEU = {
    "frei": "Freier Eintrag",
    "impuls": "Zum Impuls",
    "leitfrage": "Zur Leitfrage",
}


def hole_bezug(
    db: sqlite3.Connection, ansicht: Ansicht, art: str, bezug_id: int | None
) -> sqlite3.Row | None:
    """Impuls (am Stichtag sichtbar) oder Leitfrage; unbekannt oder nicht sichtbar: 404."""
    if art == "frei":
        return None
    if bezug_id is None:
        raise HTTPException(404)
    if art == "impuls":
        bezug = sichtbarer_impuls(db, bezug_id, ansicht.stichtag)
    else:
        bezug = inhalte.leitfrage(db, bezug_id)
    if bezug is None:
        raise HTTPException(404)
    return bezug


def kontext_tagebuch_neu(
    db: sqlite3.Connection,
    ansicht: Ansicht,
    art: str,
    bezug_id: int | None = None,
    text: str | None = None,
    fehler: dict[str, str] | None = None,
    meldung: str | None = None,
) -> dict:
    """Formular fuer einen neuen Eintrag; `art` ist `frei`, `impuls` oder `leitfrage`."""
    bezug = hole_bezug(db, ansicht, art, bezug_id)
    fehler = fehler or {}
    return {
        "ansicht": ansicht,
        "bereich": "tagebuch",
        "meldung": meldung or (MELDUNG_FEHLER if fehler else None),
        "titel": ARTEN_NEU[art],
        "bezug": bezug,
        "bezug_art": art,
        "aktion": ansicht.url(
            "/tagebuch/neu/frei" if bezug is None else f"/tagebuch/neu/{art}/{bezug['id']}"
        ),
        "text": text or "",
        "fehler": fehler.get("text"),
        "hinweis": lies_text(db, "hinweis_tagebuch"),
        "entwurf": _entwurf(ansicht, "neu-frei" if bezug is None else f"neu-{art}-{bezug['id']}"),
    }


ARTEN_EINTRAG = {
    "frei": "Freier Eintrag",
    "leitfragen": "Zur Leitfrage",
    "impuls": "Zum Impuls",
    "aufnahme": "Gesprochener Eintrag",
}


def _neu_schluessel(eintrag: sqlite3.Row) -> str:
    """Formular «neu», aus dem der Eintrag entstand (aus Art und Bezug, nicht aus der Adresse)."""
    if eintrag["art"] == "impuls" and eintrag["impuls_id"] is not None:
        return f"neu-impuls-{eintrag['impuls_id']}"
    if eintrag["art"] == "leitfragen" and eintrag["leitfrage_id"] is not None:
        return f"neu-leitfrage-{eintrag['leitfrage_id']}"
    return "neu-frei"


def kontext_tagebuch_eintrag(
    db: sqlite3.Connection,
    ansicht: Ansicht,
    eintrag: sqlite3.Row,
    text: str | None = None,
    fehler: dict[str, str] | None = None,
    meldung: str | None = None,
    neu_angelegt: bool = False,
) -> dict:
    """Ein eigener Eintrag; `eintrag` kommt aus `hole_tagebucheintrag` (nur eigene).

    `neu_angelegt`: die Seite folgt direkt auf das Anlegen; dann gehört der Entwurf des
    Formulars «neu» zu Art und Bezug dieses Eintrags und kann verworfen werden."""
    fehler = fehler or {}
    aufnahme = None
    if eintrag["aufnahme_id"] is not None:
        aufnahme = db.execute(
            "SELECT id, dauer_sekunden FROM aufnahmen WHERE id = ? AND konto_id = ?",
            (eintrag["aufnahme_id"], ansicht.konto_id),
        ).fetchone()
    return {
        "ansicht": ansicht,
        "bereich": "tagebuch",
        "meldung": meldung or (MELDUNG_FEHLER if fehler else None),
        "eintrag": eintrag,
        "art_text": ARTEN_EINTRAG[eintrag["art"]],
        "bezug_text": eintrag["impuls_text"] or eintrag["leitfrage_text"],
        "bezug_art": eintrag["art"],
        "aufnahme": aufnahme,
        "text": (eintrag["text"] or "") if text is None else text,
        "fehler": fehler.get("text"),
        "geaendert": eintrag["geaendert"] != eintrag["erstellt"],
        "entwurf": _entwurf(ansicht, f"tagebuch-{eintrag['id']}"),
        "entwurf_verwerfen": (
            _entwurf(ansicht, _neu_schluessel(eintrag))
            if neu_angelegt and eintrag["art"] != "aufnahme"
            else None
        ),
    }


def _kurz(text: str | None, laenge: int) -> str:
    einzeilig = " ".join((text or "").split())
    return einzeilig if len(einzeilig) <= laenge else einzeilig[: laenge - 1].rstrip() + "…"


def _karte(db: sqlite3.Connection, karte: Eintrag) -> dict:
    """Marke, Titel, Vorschau und Adresse einer Karte von «Meine Einträge»."""
    z = karte.zeilen[0]
    basis = {"erstellt": karte.erstellt, "geaendert": karte.geaendert}
    if karte.art == "runde":
        fragen = len(inhalte.fragen(db, karte.runde_id))
        erster = next((a.text for a in karte.zeilen if a.text), None)
        return basis | {
            "marke": "Runde",
            "titel": z.runde_titel,
            "kopfzeile": f"{len(karte.zeilen)} von {fragen} Fragen beantwortet",
            "vorschau": _kurz(erster, 200),
            "pfad": f"/runden/{karte.runde_id}",
        }
    pfad = f"/tagebuch/{karte.eintrag_id}"
    if z.tagebuch_art == "impuls":
        return basis | {
            "marke": "Impuls",
            "titel": f"Zum Impuls: {_kurz(z.frage, 60)}",
            "vorschau": _kurz(z.text, 200),
            "pfad": pfad,
        }
    if z.tagebuch_art == "leitfragen":
        titel = f"Zur Leitfrage: {_kurz(z.frage, 60)}"
    elif z.tagebuch_art == "aufnahme":
        dauer = z.aufnahme_dauer_sekunden
        return basis | {
            "marke": "Tagebuch",
            "titel": "Gesprochener Eintrag",
            "aufnahme": True,
            "dauer": dauer,
            "vorschau": _kurz(z.text, 200),
            "pfad": pfad,
        }
    else:
        titel = "Freier Eintrag"
    return basis | {
        "marke": "Tagebuch",
        "titel": titel,
        "vorschau": _kurz(z.text, 200),
        "pfad": pfad,
    }


def kontext_eintraege(db: sqlite3.Connection, ansicht: Ansicht, meldung: str | None = None) -> dict:
    """«Meine Einträge» der angemeldeten Lehrperson, ohne gerade nicht freigeschaltete Runden."""
    karten = [
        k
        for k in gruppiere(zeilen_von(db, ansicht.konto_id))
        if k.art != "runde" or sichtbare_runde(db, k.runde_id, ansicht.stichtag) is not None
    ]
    return {
        "ansicht": ansicht,
        "bereich": "eintraege",
        "meldung": meldung,
        "karten": [_karte(db, k) for k in karten],
    }
