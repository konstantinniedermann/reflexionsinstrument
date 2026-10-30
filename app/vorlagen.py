"""Jinja2-Templates, eigenes Modul, damit Router-Module sie ohne Zirkelimport nutzen."""

from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from app.csrf import csrf_feld

templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


def konto_von(request: Request):
    """Angemeldetes Konto oder None (das State-Attribut fehlt, wenn nicht geprueft wurde)."""
    return getattr(request.state, "konto", None)


templates.env.globals["konto_von"] = konto_von
templates.env.globals["csrf_feld"] = csrf_feld
