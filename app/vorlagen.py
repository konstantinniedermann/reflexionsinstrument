"""Jinja2-Templates, eigenes Modul, damit Router-Module sie ohne Zirkelimport nutzen."""

from datetime import date
from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.csrf import csrf_feld
from app.formatierung import formatiere
from app.zeit import datum_kurz, zeitplan

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


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
