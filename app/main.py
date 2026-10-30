"""FastAPI-App: Lebenszyklus (Migration beim Start), Middleware und Router."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import Einstellungen, lade_einstellungen
from app.db import migriere, verbinde
from app.routen import allgemein
from app.sicherheit import SicherheitsHeaderMiddleware

APP_VERZEICHNIS = Path(__file__).parent


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
    app.include_router(allgemein.router)
    return app
