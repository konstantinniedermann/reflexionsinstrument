"""Ansicht der Auftraggeberin: Eintraege lesen, anhoeren, exportieren (#18)."""

import sqlite3
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse

from app import zeit
from app.auswertung import exportstand, groesse_text, karten, personenkarten
from app.db import hole_db
from app.eintraege import Zeile, alle_zeilen, gruppiere
from app.export import als_csv, exportzeilen
from app.export_zip import DATEI_FEHLT, zip_dateien, zip_strom
from app.inhalte import lies_projektstart
from app.sitzung import braucht_auftraggeberin
from app.vorlagen import templates
from app.zeit import hole_heute

router = APIRouter(prefix="/verwaltung/eintraege", dependencies=[Depends(braucht_auftraggeberin)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
HEUTE = Annotated[date, Depends(hole_heute)]
LehrpersonFilter = Annotated[int | None, Query(ge=1, le=2**63 - 1)]


@router.get("")
def uebersicht(request: Request, db: DB, heute: HEUTE, lehrperson: LehrpersonFilter = None):
    alle = alle_zeilen(db)  # eine Abfrage: Karten, Liste und Export-Stand zeigen denselben Stand
    zeilen = alle
    personen = personenkarten(db, heute, alle)
    gewaehlt = None
    if lehrperson is not None:
        gewaehlt = next((p for p in personen if p.konto_id == lehrperson), None)
        if gewaehlt is None:
            raise HTTPException(404)
        zeilen = [z for z in zeilen if z.konto_id == lehrperson]
    start = lies_projektstart(db)
    stand = exportstand(alle, request.app.state.einstellungen.aufnahmen_verzeichnis)
    return templates.TemplateResponse(
        request,
        "verwaltung/eintraege/uebersicht.html",
        {
            "woche": zeit.woche(heute, start) if start else None,
            "personen": personen,
            "gewaehlt": gewaehlt,
            "karten": karten(gruppiere(zeilen), start),
            "staende": {p.konto_id: p.stand for p in personen},
            "stand": stand,
            "groesse": groesse_text(stand.bytes),
        },
    )


def _anhang(name: str, heute: date, endung: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="reflexion-{name}-{heute.isoformat()}.{endung}"'
    }


@router.get("/tabelle.csv")
def tabelle(request: Request, db: DB, heute: HEUTE):
    ez = exportzeilen(alle_zeilen(db), lies_projektstart(db))
    basis = str(request.base_url).rstrip("/")

    def link(z: Zeile) -> str:
        return f"{basis}/verwaltung/aufnahmen/{z.aufnahme_id}" if z.aufnahme_id is not None else ""

    return Response(
        als_csv(ez, link),
        media_type="text/csv; charset=utf-8",
        headers=_anhang("tabelle", heute, "csv"),
    )


@router.get("/gesamtexport.zip")
def gesamtexport(request: Request, db: DB, heute: HEUTE):
    # Alles lesen, bevor die Antwort beginnt: der Generator hält keine Datenbankverbindung.
    ez = exportzeilen(alle_zeilen(db), lies_projektstart(db))
    dateien = zip_dateien(ez, request.app.state.einstellungen.aufnahmen_verzeichnis)

    def tabelle_im_zip(enthalten: dict[int, str]) -> bytes:
        def name(z: Zeile) -> str:
            if z.aufnahme_id is None:
                return ""
            return enthalten.get(z.aufnahme_id, DATEI_FEHLT)

        return als_csv(ez, name)

    return StreamingResponse(
        zip_strom(dateien, tabelle_im_zip),
        media_type="application/zip",
        headers=_anhang("gesamtexport", heute, "zip"),
    )
