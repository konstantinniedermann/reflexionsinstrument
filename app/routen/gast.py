"""Gast-Ansicht ohne Anmeldung: freigeschaltete Inhalte ansehen, nichts speichern."""

from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends

from app.ansicht import Ansicht, fuer_gast
from app.routen.ohne_speichern import DB_LESEND, MELDUNG_GAST, registriere_seiten
from app.texte import lies_text
from app.zeit import hole_heute

# Bewusst ohne `dependencies`: keine Sitzung, kein Konto, kein eigenes Cookie.
router = APIRouter(prefix="/gast")

AUSGANG = ("Anmelden", "/")


def hole_ansicht_gast(db: DB_LESEND, heute: Annotated[date, Depends(hole_heute)]) -> Ansicht:
    return fuer_gast(heute, lies_text(db, "hinweis_gast"), AUSGANG)


registriere_seiten(router, hole_ansicht_gast, MELDUNG_GAST)
