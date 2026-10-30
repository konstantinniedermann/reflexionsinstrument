"""Eingabemaske der Auftraggeberin: Uebersicht der Inhalte und Allgemeines."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import InhaltFehler
from app.inhalte import lies_projektstart, lies_titel, speichere_allgemein, zaehle_inhalte
from app.sitzung import braucht_auftraggeberin
from app.texte import lies_texte, lies_textstand
from app.vorlagen import templates
from app.zeit import hole_heute

router = APIRouter(prefix="/verwaltung/inhalte", dependencies=[Depends(braucht_auftraggeberin)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
HEUTE = Annotated[date, Depends(hole_heute)]

# Der Text kommt aus dieser Tabelle, nie aus der Adresse.
ERLEDIGT = {"gespeichert": "Gespeichert.", "angelegt": "Angelegt.", "geloescht": "Gelöscht."}


def _meldung(request: Request) -> str | None:
    return ERLEDIGT.get(request.query_params.get("erledigt", ""))


def _weiter(pfad: str, erledigt: str | None = None, anker: str | None = None):
    ziel = pfad if erledigt is None else f"{pfad}?erledigt={erledigt}"
    if anker:
        ziel = f"{ziel}#{anker}"
    return RedirectResponse(ziel, status_code=303)


def _oder_404(zeile):
    if zeile is None:
        raise HTTPException(404)
    return zeile


@router.get("")
def uebersicht(request: Request, db: DB):
    zahlen = zaehle_inhalte(db)
    hinweise = lies_texte(db, "hinweise")
    start = lies_projektstart(db)
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/uebersicht.html",
        {
            "zahlen": zahlen,
            "projektstart": start,
            "begruessung_offen": not lies_textstand(db, "begruessung").bestaetigt,
            "hinweise_bestaetigt": sum(1 for h in hinweise if h.bestaetigt),
            "hinweise_gesamt": len(hinweise),
        },
    )


def _allgemein_seite(request: Request, db: sqlite3.Connection, status=200, werte=None, fehler=None):
    stand = lies_textstand(db, "begruessung")
    start = lies_projektstart(db)
    gespeichert = {
        "titel": lies_titel(db),
        "begruessung": stand.inhalt,
        "projektstart": "" if start is None else start.isoformat(),
    }
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/allgemein.html",
        {
            "stand": stand,
            "werte": werte or gespeichert,
            "fehler": fehler or {},
            "meldung": _meldung(request),
        },
        status_code=status,
    )


@router.get("/allgemein")
def allgemein(request: Request, db: DB):
    return _allgemein_seite(request, db)


@router.post("/allgemein", dependencies=[Depends(pruefe_csrf)])
def allgemein_speichern(
    request: Request,
    db: DB,
    titel: Annotated[str, Form()] = "",
    begruessung: Annotated[str, Form()] = "",
    projektstart: Annotated[str, Form()] = "",
):
    try:
        speichere_allgemein(db, titel, begruessung, projektstart)
    except InhaltFehler as fehler:
        werte = {"titel": titel, "begruessung": begruessung, "projektstart": projektstart}
        return _allgemein_seite(request, db, 400, werte, {fehler.feld: fehler.meldung})
    return _weiter("/verwaltung/inhalte/allgemein", "gespeichert")
