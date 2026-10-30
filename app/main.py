"""FastAPI-App: Lebenszyklus (Migration beim Start) und Grundrouten."""

import sqlite3
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.config import Einstellungen, lade_einstellungen
from app.db import hole_db, migriere, verbinde
from app.sicherheit import SicherheitsHeaderMiddleware

APP_VERZEICHNIS = Path(__file__).parent
templates = Jinja2Templates(directory=APP_VERZEICHNIS / "templates")


def erstelle_app(einstellungen: Einstellungen | None = None) -> FastAPI:
    if einstellungen is None:
        einstellungen = lade_einstellungen()

    @asynccontextmanager
    async def lebenszyklus(app: FastAPI) -> AsyncIterator[None]:
        einstellungen.daten_verzeichnis.mkdir(parents=True, exist_ok=True)
        einstellungen.aufnahmen_verzeichnis.mkdir(parents=True, exist_ok=True)
        conn = verbinde(einstellungen.db_pfad)
        try:
            migriere(conn)
        finally:
            conn.close()
        yield

    app = FastAPI(lifespan=lebenszyklus, docs_url=None, redoc_url=None, openapi_url=None)
    app.state.einstellungen = einstellungen
    app.add_middleware(SicherheitsHeaderMiddleware, produktion=einstellungen.produktion)
    app.mount("/static", StaticFiles(directory=APP_VERZEICHNIS / "static"), name="static")

    @app.get("/")
    def start(request: Request):
        return templates.TemplateResponse(request, "start.html", {})

    @app.get("/healthz")
    def healthz(db: Annotated[sqlite3.Connection, Depends(hole_db)]):
        try:
            db.execute("SELECT 1")
        except sqlite3.Error:
            return JSONResponse({"status": "fehler"}, status_code=503)
        return {"status": "ok"}

    return app
