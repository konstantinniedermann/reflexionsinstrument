"""Jinja2-Templates, eigenes Modul, damit Router-Module sie ohne Zirkelimport nutzen."""

import sqlite3
from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.csrf import csrf_feld
from app.db import verbinde
from app.formatierung import formatiere
from app.inhalte import STANDARD_TITEL, lies_titel
from app.zeit import datum_kurz, zeitplan


def instrument_titel(request: Request) -> dict[str, str]:
    """Titel des Instruments fuer jede Seite, auch Fehlerseiten: darf nie selbst scheitern."""
    titel = STANDARD_TITEL
    einstellungen = getattr(request.app.state, "einstellungen", None)
    if einstellungen is not None:
        try:
            conn = verbinde(einstellungen.db_pfad)
            try:
                titel = lies_titel(conn)
            finally:
                conn.close()
        except sqlite3.Error:
            pass
    return {"instrument_titel": titel}


templates = Jinja2Templates(
    directory=Path(__file__).parent / "templates", context_processors=[instrument_titel]
)


def konto_von(request: Request):
    """Angemeldetes Konto oder None (das State-Attribut fehlt, wenn nicht geprueft wurde)."""
    return getattr(request.state, "konto", None)


templates.env.globals["konto_von"] = konto_von
templates.env.globals["csrf_feld"] = csrf_feld


def datum_filter(wert: date | str | None, mit_jahr: bool = True) -> str:
    if not wert:
        return ""
    if isinstance(wert, str):
        wert = date.fromisoformat(wert)
    return datum_kurz(wert, mit_jahr)


templates.env.filters["formatiert"] = formatiere
templates.env.filters["datum"] = datum_filter
templates.env.globals["zeitplan"] = zeitplan


def zahl(anzahl: int, einzahl: str, mehrzahl: str) -> str:
    return f"{anzahl} {einzahl if anzahl == 1 else mehrzahl}"


templates.env.globals["zahl"] = zahl
