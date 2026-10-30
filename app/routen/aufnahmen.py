"""Sprachaufnahmen: Anhoeren (Lehrperson: eigene, Auftraggeberin: alle)."""

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse

from app.aufnahmen import aufnahme, aufnahme_pfad, eigene_aufnahme
from app.db import hole_db
from app.konten import Konto
from app.sitzung import braucht_auftraggeberin, braucht_lehrperson
from app.typen import Id

router = APIRouter()
lehrperson = APIRouter(prefix="/lehrperson", dependencies=[Depends(braucht_lehrperson)])
verwaltung = APIRouter(prefix="/verwaltung", dependencies=[Depends(braucht_auftraggeberin)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]


def _verzeichnis(request: Request) -> Path:
    return request.app.state.einstellungen.aufnahmen_verzeichnis


def _ausliefern(request: Request, zeile: sqlite3.Row | None) -> FileResponse:
    """Fremd, unbekannt, ungueltiger Name oder fehlende Datei sind nicht unterscheidbar."""
    if zeile is None:
        raise HTTPException(404)
    pfad = aufnahme_pfad(_verzeichnis(request), zeile["dateiname"])
    if pfad is None or not pfad.is_file():
        raise HTTPException(404)
    return FileResponse(
        pfad,
        media_type=zeile["mime_typ"],
        filename=f"aufnahme-{zeile['id']}{pfad.suffix}",
        content_disposition_type="inline",
        headers={"Cross-Origin-Resource-Policy": "same-origin"},
    )


@lehrperson.get("/aufnahmen/{aufnahme_id}")
def eigene_abspielen(
    request: Request,
    aufnahme_id: Id,
    db: DB,
    konto: Annotated[Konto, Depends(braucht_lehrperson)],
):
    return _ausliefern(request, eigene_aufnahme(db, konto.id, aufnahme_id))


@verwaltung.get("/aufnahmen/{aufnahme_id}")
def alle_abspielen(request: Request, aufnahme_id: Id, db: DB):
    return _ausliefern(request, aufnahme(db, aufnahme_id))


router.include_router(lehrperson)
router.include_router(verwaltung)
