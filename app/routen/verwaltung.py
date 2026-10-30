"""Verwaltung der Auftraggeberin: Zugaenge der Lehrpersonen."""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.csrf import pruefe_csrf
from app.db import hole_db
from app.konten import (
    EingabeFehler,
    Konto,
    finde_konto,
    lege_konto_an,
    lehrpersonen,
    loesche_konto,
    passwort_vorschlag,
    setze_passwort,
    zaehle_daten,
)
from app.sitzung import braucht_auftraggeberin
from app.vorlagen import templates

router = APIRouter(prefix="/verwaltung", dependencies=[Depends(braucht_auftraggeberin)])

# Der Text kommt aus dieser Tabelle, nie aus der Adresse.
BESTAETIGUNGEN = {"geloescht": "Der Zugang wurde gelöscht."}

DB = Annotated[sqlite3.Connection, Depends(hole_db)]


def _lehrperson_oder_404(db: sqlite3.Connection, konto_id: int) -> Konto:
    konto = finde_konto(db, konto_id)
    if konto is None or konto.rolle != "lehrperson":
        raise HTTPException(404)
    return konto


def _zahl(anzahl: int, einzahl: str, mehrzahl: str) -> str:
    return f"{anzahl} {einzahl if anzahl == 1 else mehrzahl}"


def _zugaenge_seite(request: Request, db: sqlite3.Connection, status=200, **kontext):
    kontext.setdefault("vorschlag", passwort_vorschlag())
    kontext.setdefault("werte", {})
    kontext.setdefault("fehler", {})
    kontext.setdefault("meldung", BESTAETIGUNGEN.get(request.query_params.get("erledigt", "")))
    return templates.TemplateResponse(
        request,
        "verwaltung/zugaenge.html",
        {"lehrpersonen": lehrpersonen(db), **kontext},
        status_code=status,
    )


@router.get("")
def start(request: Request):
    return templates.TemplateResponse(request, "verwaltung/start.html")


@router.get("/zugaenge")
def zugaenge(request: Request, db: DB):
    return _zugaenge_seite(request, db)


@router.post("/zugaenge", dependencies=[Depends(pruefe_csrf)])
def zugang_anlegen(
    request: Request,
    db: DB,
    anzeigename: Annotated[str, Form()] = "",
    benutzername: Annotated[str, Form()] = "",
    passwort: Annotated[str, Form()] = "",
):
    try:
        konto = lege_konto_an(db, anzeigename, benutzername, passwort)
    except EingabeFehler as fehler:
        werte = {"anzeigename": anzeigename, "benutzername": benutzername, "passwort": passwort}
        return _zugaenge_seite(
            request, db, status=400, werte=werte, fehler={fehler.feld: str(fehler)}
        )
    return templates.TemplateResponse(
        request,
        "verwaltung/zugang_bestaetigt.html",
        {"ueberschrift": "Zugang angelegt", "zugang": konto, "passwort": passwort},
    )


def _passwort_seite(request: Request, konto: Konto, status=200, passwort=None, fehler=""):
    return templates.TemplateResponse(
        request,
        "verwaltung/passwort.html",
        {"zugang": konto, "passwort": passwort or passwort_vorschlag(), "fehler": fehler},
        status_code=status,
    )


@router.get("/zugaenge/{konto_id}/passwort")
def passwort_formular(request: Request, konto_id: int, db: DB):
    return _passwort_seite(request, _lehrperson_oder_404(db, konto_id))


@router.post("/zugaenge/{konto_id}/passwort", dependencies=[Depends(pruefe_csrf)])
def passwort_setzen(request: Request, konto_id: int, db: DB, passwort: Annotated[str, Form()] = ""):
    konto = _lehrperson_oder_404(db, konto_id)
    try:
        setze_passwort(db, konto.id, passwort)
    except EingabeFehler as fehler:
        return _passwort_seite(request, konto, 400, passwort, str(fehler))
    return templates.TemplateResponse(
        request,
        "verwaltung/zugang_bestaetigt.html",
        {"ueberschrift": "Neues Passwort gesetzt", "zugang": konto, "passwort": passwort},
    )


@router.get("/zugaenge/{konto_id}/loeschen")
def loeschen_formular(request: Request, konto_id: int, db: DB):
    konto = _lehrperson_oder_404(db, konto_id)
    zahlen = zaehle_daten(db, konto.id)
    folgen = [
        _zahl(zahlen["antworten"], "Antwort", "Antworten"),
        _zahl(zahlen["tagebucheintraege"], "Tagebucheintrag", "Tagebucheinträge"),
        _zahl(zahlen["aufnahmen"], "Aufnahme", "Aufnahmen"),
    ]
    return templates.TemplateResponse(
        request,
        "verwaltung/loeschen.html",
        {"zugang": konto, "folgen": f"{folgen[0]}, {folgen[1]} und {folgen[2]}"},
    )


@router.post("/zugaenge/{konto_id}/loeschen", dependencies=[Depends(pruefe_csrf)])
def loeschen(request: Request, konto_id: int, db: DB):
    konto = _lehrperson_oder_404(db, konto_id)
    loesche_konto(db, konto.id, request.app.state.einstellungen.aufnahmen_verzeichnis)
    return RedirectResponse("/verwaltung/zugaenge?erledigt=geloescht", status_code=303)
