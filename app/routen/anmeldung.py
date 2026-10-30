"""Login-Seite, Anmelden und Abmelden."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse

from app.csrf import pruefe_csrf
from app.db import hole_db
from app.konten import Konto, finde_hash, normalisiere_benutzername, passwort_stimmt
from app.sitzung import STARTSEITE, abmelden, aktuelles_konto, anmelden, braucht_konto
from app.vorlagen import templates

router = APIRouter()

MELDUNG_FALSCH = "Benutzername oder Passwort stimmt nicht."
MELDUNG_GESPERRT = "Zu viele Fehlversuche. Bitte in 15 Minuten nochmals versuchen."


def client_adresse(request: Request) -> str:
    """Adresse des Besuchers; hinter dem fly-Proxy steht sie in `Fly-Client-IP`."""
    if request.app.state.einstellungen.produktion:
        adresse = request.headers.get("fly-client-ip")
        if adresse:
            return adresse
    return request.client.host if request.client else ""


def _login_seite(request: Request, status: int, benutzername: str = "", fehler: str = ""):
    return templates.TemplateResponse(
        request,
        "anmelden.html",
        {"benutzername": benutzername, "fehler": fehler},
        status_code=status,
    )


def _weiter(konto: Konto) -> RedirectResponse:
    return RedirectResponse(STARTSEITE[konto.rolle], status_code=303)


@router.get("/")
def startseite(request: Request, konto: Annotated[Konto | None, Depends(aktuelles_konto)]):
    if konto is not None:
        return _weiter(konto)
    return _login_seite(request, 200)


@router.get("/anmelden")
@router.get("/abmelden")
def formularadresse_per_get():
    """Tab-Wiederherstellung oder Lesezeichen auf eine Formularadresse: zurueck zum Start."""
    return RedirectResponse("/", status_code=303)


@router.post("/anmelden", dependencies=[Depends(pruefe_csrf)])
def anmelden_senden(
    request: Request,
    db: Annotated[sqlite3.Connection, Depends(hole_db)],
    benutzername: Annotated[str, Form()] = "",
    passwort: Annotated[str, Form()] = "",
    dauerhaft: Annotated[str, Form()] = "",
):
    schutz = request.app.state.anmeldeschutz
    name = normalisiere_benutzername(benutzername)
    adresse = client_adresse(request)
    if not schutz.versuch_beginnen(name, adresse):
        return _login_seite(request, 429, benutzername, MELDUNG_GESPERRT)
    gefunden = finde_hash(db, name)
    konto, passwort_hash = gefunden if gefunden else (None, None)
    if konto is None or not passwort_stimmt(passwort, passwort_hash):
        return _login_seite(request, 400, benutzername, MELDUNG_FALSCH)
    schutz.erfolg(name, adresse)
    anmelden(request, konto, dauerhaft == "1")
    return _weiter(konto)


@router.post("/abmelden", dependencies=[Depends(braucht_konto), Depends(pruefe_csrf)])
def abmelden_senden(request: Request):
    abmelden(request)
    return RedirectResponse("/", status_code=303)
