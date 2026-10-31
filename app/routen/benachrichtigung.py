"""Benachrichtigungen (#37): Manifest, Service Worker, Abo pro Gerät, Senden in der Verwaltung."""

import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import LAENGE_KURZ, InhaltFehler, kurzer_text
from app.inhalte import lies_titel
from app.konten import Konto
from app.push import verschicke_an_alle
from app.push_abos import anzahl_abos, loesche_abo, pruefe_abo, speichere_abo
from app.sichtbar import aktueller_impuls
from app.sitzung import braucht_auftraggeberin, braucht_konto
from app.vorlagen import templates
from app.zeit import hole_heute

STATIC = Path(__file__).parent.parent / "static"
FARBE = "#f1f1f1"
SYMBOLE = [180, 192, 512]

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
KONTO = Annotated[Konto, Depends(braucht_konto)]

router = APIRouter()
verwaltung_router = APIRouter(prefix="/verwaltung", dependencies=[Depends(braucht_auftraggeberin)])


def _vapid(request: Request):
    vapid = request.app.state.vapid
    if vapid is None:
        raise HTTPException(404)
    return vapid


@router.get("/manifest.webmanifest")
def manifest(db: DB):
    titel = lies_titel(db)
    return JSONResponse(
        {
            "name": titel,
            "short_name": titel,
            "lang": "de",
            "start_url": "/",
            "scope": "/",
            "display": "standalone",
            "background_color": FARBE,
            "theme_color": FARBE,
            "icons": [
                {"src": f"/static/bilder/symbol-{n}.png", "sizes": f"{n}x{n}", "type": "image/png"}
                for n in SYMBOLE
            ],
        },
        media_type="application/manifest+json",
    )


@router.get("/sw.js")
def service_worker():
    # An der Wurzel ausgeliefert, damit er für die ganze Seite gilt.
    return FileResponse(STATIC / "js" / "sw.js", media_type="text/javascript")


@router.post("/benachrichtigung/abo", dependencies=[Depends(pruefe_csrf)])
def abo_speichern(
    request: Request,
    db: DB,
    konto: KONTO,
    endpunkt: Annotated[str, Form()] = "",
    p256dh: Annotated[str, Form()] = "",
    auth: Annotated[str, Form()] = "",
):
    _vapid(request)
    try:
        abo = pruefe_abo(endpunkt, p256dh, auth)
    except ValueError as fehler:
        raise HTTPException(400) from fehler
    speichere_abo(db, konto.id, abo)
    return Response(status_code=204)


@router.post("/benachrichtigung/abo/loeschen", dependencies=[Depends(pruefe_csrf)])
def abo_loeschen(db: DB, konto: KONTO, endpunkt: Annotated[str, Form()] = ""):
    loesche_abo(db, konto.id, endpunkt)
    return Response(status_code=204)


def _zahl(wert: str | None) -> int:
    return int(wert) if wert and wert.isdigit() else 0


def _seite(request: Request, db: sqlite3.Connection, status=200, **kontext):
    eingerichtet = request.app.state.vapid is not None
    abfrage = request.query_params
    ergebnis = None
    if abfrage.get("gesendet", "").isdigit():
        ergebnis = {k: _zahl(abfrage.get(k)) for k in ("gesendet", "entfernt", "nicht")}
    if "text" not in kontext:
        # Vorschlag: der aktuelle Impuls. Nach dem Senden leer, damit nichts doppelt hinausgeht.
        impuls = None if ergebnis else aktueller_impuls(db, hole_heute(request))
        kontext["text"] = impuls["text"] if impuls else ""
    return templates.TemplateResponse(
        request,
        "verwaltung/benachrichtigung.html",
        {
            "eingerichtet": eingerichtet,
            "anzahl": anzahl_abos(db) if eingerichtet else 0,
            "laenge": LAENGE_KURZ,
            "ergebnis": ergebnis,
            **kontext,
        },
        status_code=status,
    )


@verwaltung_router.get("/benachrichtigung")
def benachrichtigung(request: Request, db: DB):
    return _seite(request, db)


@verwaltung_router.post("/benachrichtigung", dependencies=[Depends(pruefe_csrf)])
def senden(request: Request, db: DB, text: Annotated[str, Form()] = ""):
    vapid = _vapid(request)
    try:
        nachricht = kurzer_text(text, "text", LAENGE_KURZ, "Bitte einen Text eingeben.")
    except InhaltFehler as fehler:
        return _seite(request, db, status=400, text=text, fehler=str(fehler))
    ergebnis = verschicke_an_alle(db, vapid, lies_titel(db), nachricht)
    return RedirectResponse(
        f"/verwaltung/benachrichtigung?gesendet={ergebnis.gesendet}"
        f"&entfernt={ergebnis.entfernt}&nicht={ergebnis.nicht_erreicht}",
        status_code=303,
    )
