"""Allgemeine Routen: Startseite und Health-Check."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from app.db import hole_db
from app.vorlagen import templates

router = APIRouter()


@router.get("/")
def start(request: Request):
    return templates.TemplateResponse(request, "start.html", {})


@router.get("/healthz")
def healthz(db: Annotated[sqlite3.Connection, Depends(hole_db)]):
    try:
        db.execute("SELECT 1")
    except sqlite3.Error:
        return JSONResponse({"status": "fehler"}, status_code=503)
    return {"status": "ok"}
