"""Seiten, die nichts speichern: gemeinsam fuer die Ansicht ohne Konto und die Vorschau."""

import sqlite3
from collections.abc import Callable
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.ansicht import Ansicht
from app.db import hole_db
from app.seiten_lehrperson import (
    VORLAGEN,
    kontext_info,
    kontext_runde,
    kontext_start,
    kontext_tagebuch_neu,
    kontext_tagebuch_wahl,
)
from app.typen import Id
from app.vorlagen import templates

MELDUNG_GAST = "Nicht gespeichert. In der Ansicht ohne Konto wird nichts gespeichert."
MELDUNG_VORSCHAU = "Nicht gespeichert. In der Vorschau wird nichts gespeichert."


def hole_db_lesend(db: Annotated[sqlite3.Connection, Depends(hole_db)]) -> sqlite3.Connection:
    """Dieselbe Verbindung wie `hole_db`, aber jeder Schreibversuch scheitert in SQLite."""
    db.execute("PRAGMA query_only = ON")
    return db


DB_LESEND = Annotated[sqlite3.Connection, Depends(hole_db_lesend)]


def registriere_seiten(
    router: APIRouter, hole_ansicht: Callable[..., Ansicht], meldung: str
) -> None:
    """Haengt die Seiten an `router`; Gast und Vorschau unterscheiden sich nur in Ansicht und Meldung."""
    ANSICHT = Annotated[Ansicht, Depends(hole_ansicht)]

    @router.get("")
    def start(request: Request, db: DB_LESEND, ansicht: ANSICHT):
        return templates.TemplateResponse(request, VORLAGEN["start"], kontext_start(db, ansicht))

    @router.get("/info")
    def info(request: Request, db: DB_LESEND, ansicht: ANSICHT):
        return templates.TemplateResponse(request, VORLAGEN["info"], kontext_info(db, ansicht))

    @router.get("/runden/{runde_id}")
    def runde(request: Request, db: DB_LESEND, ansicht: ANSICHT, runde_id: Id):
        kontext = kontext_runde(db, ansicht, runde_id)
        return templates.TemplateResponse(request, VORLAGEN["runde"], kontext)

    @router.get("/tagebuch/neu")
    def tagebuch_wahl(request: Request, db: DB_LESEND, ansicht: ANSICHT):
        kontext = kontext_tagebuch_wahl(db, ansicht)
        return templates.TemplateResponse(request, VORLAGEN["tagebuch_wahl"], kontext)

    def neu(request: Request, db, ansicht: Ansicht, art: str, bezug_id: int | None):
        kontext = kontext_tagebuch_neu(db, ansicht, art, bezug_id)
        return templates.TemplateResponse(request, VORLAGEN["tagebuch_neu"], kontext)

    @router.get("/tagebuch/neu/frei")
    def neu_frei(request: Request, db: DB_LESEND, ansicht: ANSICHT):
        return neu(request, db, ansicht, "frei", None)

    @router.get("/tagebuch/neu/impuls/{impuls_id}")
    def neu_impuls(request: Request, db: DB_LESEND, ansicht: ANSICHT, impuls_id: Id):
        return neu(request, db, ansicht, "impuls", impuls_id)

    @router.get("/tagebuch/neu/leitfrage/{leitfrage_id}")
    def neu_leitfrage(request: Request, db: DB_LESEND, ansicht: ANSICHT, leitfrage_id: Id):
        return neu(request, db, ansicht, "leitfrage", leitfrage_id)
