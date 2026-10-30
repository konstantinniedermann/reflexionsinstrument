"""Allgemeine Routen: Health-Check."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from app.db import hole_db

router = APIRouter()


@router.get("/healthz")
def healthz(db: Annotated[sqlite3.Connection, Depends(hole_db)]):
    try:
        db.execute("SELECT 1")
    except sqlite3.Error:
        return JSONResponse({"status": "fehler"}, status_code=503)
    return {"status": "ok"}
