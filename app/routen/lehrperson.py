"""Seiten der Lehrperson."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse

from app.ansicht import Ansicht, hole_ansicht_lehrperson
from app.db import hole_db
from app.seiten_lehrperson import VORLAGEN, kontext_info, kontext_start
from app.sitzung import braucht_lehrperson
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
