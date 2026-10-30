"""FastAPI-App: Lebenszyklus (Migration beim Start), Middleware und Router."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app import zeit
from app.anmeldeschutz import Anmeldeschutz
from app.config import Einstellungen, lade_einstellungen
from app.cookies import CookieMiddleware
from app.db import migriere, verbinde
from app.routen import allgemein, anmeldung, lehrperson, verwaltung
from app.sicherheit import SicherheitsHeaderMiddleware
from app.vorlagen import templates
from app.zugriff import KeinZugriff, NichtAngemeldet

APP_VERZEICHNIS = Path(__file__).parent

FEHLERTEXTE = {
    404: ("Nicht gefunden", "Diese Seite gibt es nicht."),
    405: ("Nicht möglich", "Diese Seite gibt es so nicht."),
}
FEHLER_ALLGEMEIN = ("Das hat nicht geklappt", "Bitte versuche es später nochmals.")


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
    app.state.anmeldeschutz = Anmeldeschutz()
    app.state.heute = zeit.heute

    def fehlerseite(request: Request, status: int, titel: str, meldung: str):
        return templates.TemplateResponse(
            request, "fehler.html", {"titel": titel, "meldung": meldung}, status_code=status
        )

    @app.exception_handler(NichtAngemeldet)
    async def nicht_angemeldet(request: Request, exc: NichtAngemeldet):
        return RedirectResponse("/", status_code=303)

    @app.exception_handler(KeinZugriff)
    async def kein_zugriff(request: Request, exc: KeinZugriff):
        return fehlerseite(request, 403, exc.titel, exc.text)

    @app.exception_handler(StarletteHTTPException)
    async def http_fehler(request: Request, exc: StarletteHTTPException):
        titel, meldung = FEHLERTEXTE.get(exc.status_code, FEHLER_ALLGEMEIN)
        antwort = fehlerseite(request, exc.status_code, titel, meldung)
        antwort.headers.update(exc.headers or {})
        return antwort

    @app.exception_handler(RequestValidationError)
    async def ungueltige_anfrage(request: Request, exc: RequestValidationError):
        return fehlerseite(request, 404, *FEHLERTEXTE[404])

    # Zuletzt hinzugefuegt = aeusserste Schicht: Header gelten auch fuer Fehlerantworten.
    app.add_middleware(CookieMiddleware)
    app.add_middleware(SicherheitsHeaderMiddleware, produktion=einstellungen.produktion)
    app.mount("/static", StaticFiles(directory=APP_VERZEICHNIS / "static"), name="static")
    app.include_router(allgemein.router)
    app.include_router(anmeldung.router)
    app.include_router(lehrperson.router)
    app.include_router(verwaltung.router)
    return app
