"""Seiten der Lehrperson."""

import re
import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app import inhalte
from app.ansicht import Ansicht, hole_ansicht_lehrperson
from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import InhaltFehler
from app.eintraege import (
    aendere_tagebucheintrag,
    hole_tagebucheintrag,
    lege_tagebucheintrag_an,
    lies_runden_eingaben,
    loesche_antworten_der_runde,
    loesche_tagebucheintrag,
    speichere_antworten,
)
from app.seiten_lehrperson import (
    VORLAGEN,
    hole_bezug,
    kontext_eintraege,
    kontext_info,
    kontext_runde,
    kontext_start,
    kontext_tagebuch_eintrag,
    kontext_tagebuch_neu,
    kontext_tagebuch_wahl,
)
from app.sichtbar import sichtbare_runde
from app.sitzung import braucht_lehrperson
from app.typen import Id
from app.vorlagen import templates

router = APIRouter(prefix="/lehrperson", dependencies=[Depends(braucht_lehrperson)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
ANSICHT = Annotated[Ansicht, Depends(hole_ansicht_lehrperson)]

# Der Text kommt aus dieser Tabelle, nie aus der Adresse.
ERLEDIGT = {
    "gespeichert": "Gespeichert.",
    "geloescht": "Gelöscht.",
    "aufnahme_geloescht": "Die Aufnahme wurde gelöscht.",
}


def _meldung(request: Request) -> str | None:
    return ERLEDIGT.get(request.query_params.get("erledigt", ""))


def _weiter(pfad: str, erledigt: str | None = None, anker: str | None = None):
    ziel = pfad if erledigt is None else f"{pfad}?erledigt={erledigt}"
    if anker:
        ziel = f"{ziel}#{anker}"
    return RedirectResponse(ziel, status_code=303)


@router.get("")
def start(request: Request, db: DB, ansicht: ANSICHT):
    kontext = kontext_start(db, ansicht) | {"meldung": _meldung(request)}
    return templates.TemplateResponse(request, VORLAGEN["start"], kontext)


@router.get("/info")
def info(request: Request, db: DB, ansicht: ANSICHT):
    kontext = kontext_info(db, ansicht) | {"meldung": _meldung(request)}
    return templates.TemplateResponse(request, VORLAGEN["info"], kontext)


ANKER = re.compile(r"(frage|aufnahme)-([0-9]{1,10})")


@router.get("/runden/{runde_id}")
def runde_anzeigen(request: Request, db: DB, ansicht: ANSICHT, runde_id: Id):
    kontext = kontext_runde(db, ansicht, runde_id, meldung=_meldung(request))
    return templates.TemplateResponse(request, VORLAGEN["runde"], kontext)


@router.post("/runden/{runde_id}", dependencies=[Depends(pruefe_csrf)])
async def runde_speichern(request: Request, db: DB, ansicht: ANSICHT, runde_id: Id):
    if sichtbare_runde(db, runde_id, ansicht.stichtag) is None:
        raise HTTPException(404)
    formular = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    fragen = inhalte.fragen(db, runde_id)
    try:
        eingaben = lies_runden_eingaben(fragen, formular)
    except InhaltFehler as e:
        kontext = kontext_runde(
            db, ansicht, runde_id, eingaben=formular, fehler={e.feld: e.meldung}
        )
        return templates.TemplateResponse(request, VORLAGEN["runde"], kontext, status_code=400)
    speichere_antworten(db, ansicht.konto_id, eingaben)
    pfad = ansicht.url(f"/runden/{runde_id}")
    treffer = ANKER.fullmatch(formular.get("anker", ""))
    if treffer is None:
        return _weiter(pfad, "gespeichert")
    art, nummer = treffer.group(1), int(treffer.group(2))
    if art == "aufnahme":
        if any(f["id"] == nummer and f["typ"] == "freitext" for f in fragen):
            return _weiter(f"{pfad}/fragen/{nummer}/aufnahme")
        return _weiter(pfad, "gespeichert")
    return _weiter(pfad, "gespeichert", f"frage-{nummer}")


def _loeschseite(request: Request, db: sqlite3.Connection, ansicht: Ansicht, runde_id: int):
    runde = sichtbare_runde(db, runde_id, ansicht.stichtag)
    if runde is None:
        raise HTTPException(404)
    pfad = ansicht.url(f"/runden/{runde_id}")
    kontext = {
        "ansicht": ansicht,
        "bereich": "runden",
        "meldung": None,
        "frage_text": f"Alle deine Antworten zu «{runde['titel']}» löschen? "
        "Das lässt sich nicht rückgängig machen.",
        "aktion": f"{pfad}/loeschen",
        "zurueck": pfad,
    }
    return templates.TemplateResponse(request, VORLAGEN["runde_loeschen"], kontext)


@router.get("/runden/{runde_id}/loeschen")
def runde_loeschen_fragen(request: Request, db: DB, ansicht: ANSICHT, runde_id: Id):
    return _loeschseite(request, db, ansicht, runde_id)


@router.post("/runden/{runde_id}/loeschen", dependencies=[Depends(pruefe_csrf)])
def runde_loeschen(request: Request, db: DB, ansicht: ANSICHT, runde_id: Id):
    if sichtbare_runde(db, runde_id, ansicht.stichtag) is None:
        raise HTTPException(404)
    verzeichnis = request.app.state.einstellungen.aufnahmen_verzeichnis
    loesche_antworten_der_runde(db, ansicht.konto_id, runde_id, verzeichnis)
    return _weiter(ansicht.url("/eintraege"), "geloescht")


@router.get("/tagebuch/neu")
def tagebuch_wahl(request: Request, db: DB, ansicht: ANSICHT):
    kontext = kontext_tagebuch_wahl(db, ansicht)
    return templates.TemplateResponse(request, VORLAGEN["tagebuch_wahl"], kontext)


# Art im Pfad -> Art in der Datenbank
ART_IN_DB = {"frei": "frei", "impuls": "impuls", "leitfrage": "leitfragen"}


def _neu_anzeigen(request: Request, db, ansicht, art: str, bezug_id: int | None):
    kontext = kontext_tagebuch_neu(db, ansicht, art, bezug_id)
    return templates.TemplateResponse(request, VORLAGEN["tagebuch_neu"], kontext)


def _neu_anlegen(request: Request, db, ansicht, art: str, bezug_id: int | None, text: str):
    bezug = hole_bezug(db, ansicht, art, bezug_id)
    try:
        neu = lege_tagebucheintrag_an(
            db,
            ansicht.konto_id,
            ART_IN_DB[art],
            text,
            impuls=bezug if art == "impuls" else None,
            leitfrage=bezug if art == "leitfrage" else None,
        )
    except InhaltFehler as e:
        kontext = kontext_tagebuch_neu(
            db, ansicht, art, bezug_id, text=text, fehler={e.feld: e.meldung}
        )
        return templates.TemplateResponse(
            request, VORLAGEN["tagebuch_neu"], kontext, status_code=400
        )
    return _weiter(ansicht.url(f"/tagebuch/{neu}"), "gespeichert")


@router.get("/tagebuch/neu/frei")
def neu_frei_anzeigen(request: Request, db: DB, ansicht: ANSICHT):
    return _neu_anzeigen(request, db, ansicht, "frei", None)


@router.post("/tagebuch/neu/frei", dependencies=[Depends(pruefe_csrf)])
def neu_frei(request: Request, db: DB, ansicht: ANSICHT, text: Annotated[str, Form()] = ""):
    return _neu_anlegen(request, db, ansicht, "frei", None, text)


@router.get("/tagebuch/neu/impuls/{impuls_id}")
def neu_impuls_anzeigen(request: Request, db: DB, ansicht: ANSICHT, impuls_id: Id):
    return _neu_anzeigen(request, db, ansicht, "impuls", impuls_id)


@router.post("/tagebuch/neu/impuls/{impuls_id}", dependencies=[Depends(pruefe_csrf)])
def neu_impuls(
    request: Request, db: DB, ansicht: ANSICHT, impuls_id: Id, text: Annotated[str, Form()] = ""
):
    return _neu_anlegen(request, db, ansicht, "impuls", impuls_id, text)


@router.get("/tagebuch/neu/leitfrage/{leitfrage_id}")
def neu_leitfrage_anzeigen(request: Request, db: DB, ansicht: ANSICHT, leitfrage_id: Id):
    return _neu_anzeigen(request, db, ansicht, "leitfrage", leitfrage_id)


@router.post("/tagebuch/neu/leitfrage/{leitfrage_id}", dependencies=[Depends(pruefe_csrf)])
def neu_leitfrage(
    request: Request, db: DB, ansicht: ANSICHT, leitfrage_id: Id, text: Annotated[str, Form()] = ""
):
    return _neu_anlegen(request, db, ansicht, "leitfrage", leitfrage_id, text)


def _eigener_eintrag(db, ansicht: Ansicht, eintrag_id: int):
    eintrag = hole_tagebucheintrag(db, ansicht.konto_id, eintrag_id)
    if eintrag is None:
        raise HTTPException(404)
    return eintrag


@router.get("/tagebuch/{eintrag_id}")
def eintrag_anzeigen(request: Request, db: DB, ansicht: ANSICHT, eintrag_id: Id):
    eintrag = _eigener_eintrag(db, ansicht, eintrag_id)
    kontext = kontext_tagebuch_eintrag(db, ansicht, eintrag, meldung=_meldung(request))
    return templates.TemplateResponse(request, VORLAGEN["tagebuch_eintrag"], kontext)


@router.post("/tagebuch/{eintrag_id}", dependencies=[Depends(pruefe_csrf)])
def eintrag_aendern(
    request: Request, db: DB, ansicht: ANSICHT, eintrag_id: Id, text: Annotated[str, Form()] = ""
):
    eintrag = _eigener_eintrag(db, ansicht, eintrag_id)
    try:
        aendere_tagebucheintrag(db, ansicht.konto_id, eintrag_id, text)
    except InhaltFehler as e:
        meldung = e.meldung if text.strip() else ZUM_LOESCHEN
        kontext = kontext_tagebuch_eintrag(
            db, ansicht, eintrag, text=text, fehler={e.feld: meldung}
        )
        return templates.TemplateResponse(
            request, VORLAGEN["tagebuch_eintrag"], kontext, status_code=400
        )
    return _weiter(ansicht.url(f"/tagebuch/{eintrag_id}"), "gespeichert")


ZUM_LOESCHEN = "Zum Löschen bitte ‹Eintrag löschen› wählen."


@router.get("/tagebuch/{eintrag_id}/loeschen")
def eintrag_loeschen_fragen(request: Request, db: DB, ansicht: ANSICHT, eintrag_id: Id):
    _eigener_eintrag(db, ansicht, eintrag_id)
    kontext = {
        "ansicht": ansicht,
        "bereich": "tagebuch",
        "meldung": None,
        "frage_text": "Diesen Eintrag löschen? Das lässt sich nicht rückgängig machen.",
        "aktion": ansicht.url(f"/tagebuch/{eintrag_id}/loeschen"),
        "zurueck": ansicht.url(f"/tagebuch/{eintrag_id}"),
    }
    return templates.TemplateResponse(request, VORLAGEN["runde_loeschen"], kontext)


@router.post("/tagebuch/{eintrag_id}/loeschen", dependencies=[Depends(pruefe_csrf)])
def eintrag_loeschen(request: Request, db: DB, ansicht: ANSICHT, eintrag_id: Id):
    verzeichnis = request.app.state.einstellungen.aufnahmen_verzeichnis
    if not loesche_tagebucheintrag(db, ansicht.konto_id, eintrag_id, verzeichnis):
        raise HTTPException(404)
    return _weiter(ansicht.url("/eintraege"), "geloescht")


@router.get("/eintraege")
def eintraege(request: Request, db: DB, ansicht: ANSICHT):
    kontext = kontext_eintraege(db, ansicht, meldung=_meldung(request))
    return templates.TemplateResponse(request, VORLAGEN["eintraege"], kontext)
