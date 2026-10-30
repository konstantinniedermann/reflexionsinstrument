"""Sprachaufnahmen: Speichern (Tagebuch) und Anhoeren (Lehrperson: eigene, Auftraggeberin: alle)."""

import re
import sqlite3
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from starlette.datastructures import UploadFile

from app import aufnahmen, eintraege, groesse
from app.ansicht import Ansicht, hole_ansicht_lehrperson
from app.aufnahmen import AufnahmeFehler, aufnahme, aufnahme_pfad, eigene_aufnahme
from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import InhaltFehler
from app.groesse import ZuGross
from app.konten import Konto
from app.sitzung import braucht_auftraggeberin, braucht_lehrperson
from app.texte import lies_text
from app.typen import Id
from app.vorlagen import templates

router = APIRouter()
lehrperson = APIRouter(prefix="/lehrperson", dependencies=[Depends(braucht_lehrperson)])
verwaltung = APIRouter(prefix="/verwaltung", dependencies=[Depends(braucht_auftraggeberin)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
ANSICHT = Annotated[Ansicht, Depends(hole_ansicht_lehrperson)]
TAGEBUCH_AKTION = "/lehrperson/tagebuch/neu/aufnahme"


async def begrenze_upload(request: Request) -> None:
    """Prueft die Groesse der Anfrage, bevor ein Byte geparst wird."""
    laenge = request.headers.get("content-length")
    if laenge is None:
        raise HTTPException(411)
    # Ziffernzahl vor int() begrenzen: int() lehnt sehr lange Ziffernfolgen mit ValueError ab.
    if (
        len(laenge) > groesse.ZIFFERN_HOECHSTENS
        or not re.fullmatch(r"[0-9]+", laenge)
        or int(laenge) > aufnahmen.MAX_ANFRAGE_BYTES
    ):
        raise ZuGross()
    await request.form(max_files=1, max_fields=5)


async def _lies_aufnahme(request: Request) -> tuple[UploadFile, int | None, str]:
    formular = await request.form()
    datei = formular.get("aufnahme")
    if not isinstance(datei, UploadFile):
        raise AufnahmeFehler(400)
    dauer = formular.get("dauer_sekunden", "")
    text = formular.get("text", "")
    if not isinstance(dauer, str) or not isinstance(text, str):
        raise AufnahmeFehler(400)
    return datei, aufnahmen.lies_dauer(dauer), text


def _verzeichnis(request: Request) -> Path:
    return request.app.state.einstellungen.aufnahmen_verzeichnis


def _ausliefern(request: Request, zeile: sqlite3.Row | None) -> FileResponse:
    """Fremd, unbekannt, ungueltiger Name oder fehlende Datei sind nicht unterscheidbar."""
    if zeile is None:
        raise HTTPException(404)
    pfad = aufnahme_pfad(_verzeichnis(request), zeile["dateiname"])
    if pfad is None or not pfad.is_file():
        raise HTTPException(404)
    return FileResponse(
        pfad,
        media_type=zeile["mime_typ"],
        filename=f"aufnahme-{zeile['id']}{pfad.suffix}",
        content_disposition_type="inline",
        headers={"Cross-Origin-Resource-Policy": "same-origin"},
    )


def _seite_tagebuch(
    request: Request,
    db: sqlite3.Connection,
    ansicht: Ansicht,
    meldung: str | None = None,
    status: int = 200,
):
    kontext = {
        "ansicht": ansicht,
        "bereich": "tagebuch",
        "meldung": meldung,
        "hinweis_tagebuch": lies_text(db, "hinweis_tagebuch"),
        "hinweis_aufnahme": lies_text(db, "hinweis_aufnahme"),
        "max_dauer": aufnahmen.MAX_DAUER_SEKUNDEN,
        "max_bytes": aufnahmen.MAX_BYTES,
        "aktion": TAGEBUCH_AKTION,
        "zurueck": "/lehrperson/tagebuch/neu",
        "schreiben": "/lehrperson/tagebuch/neu/frei",
    }
    return templates.TemplateResponse(
        request, "lehrperson/aufnahme_tagebuch.html", kontext, status_code=status
    )


@lehrperson.get("/tagebuch/neu/aufnahme")
def tagebuch_aufnahme_seite(request: Request, db: DB, ansicht: ANSICHT):
    return _seite_tagebuch(request, db, ansicht)


@lehrperson.post(
    "/tagebuch/neu/aufnahme",
    dependencies=[Depends(begrenze_upload), Depends(pruefe_csrf)],
)
async def tagebuch_aufnahme_speichern(request: Request, db: DB, ansicht: ANSICHT):
    verzeichnis = _verzeichnis(request)
    try:
        datei, dauer, text = await _lies_aufnahme(request)
        text = eintraege.lies_tagebuchtext(text, pflicht=False)
        gespeichert = aufnahmen.schreibe_datei(datei.file, verzeichnis)
    except InhaltFehler as fehler:
        return _seite_tagebuch(request, db, ansicht, fehler.meldung, 400)
    except AufnahmeFehler as fehler:
        if fehler.status != 400:
            raise HTTPException(fehler.status) from None
        return _seite_tagebuch(request, db, ansicht, fehler.meldung, 400)
    try:
        eintrag_id = aufnahmen.aufnahme_als_tagebucheintrag(
            db, ansicht.konto_id, gespeichert, dauer, text
        )
    except BaseException:
        aufnahmen.loesche_dateien(verzeichnis, [gespeichert.name])
        raise
    aufnahmen.raeume_waisen(db, verzeichnis)
    return RedirectResponse(f"/lehrperson/tagebuch/{eintrag_id}?erledigt=gespeichert", 303)


@lehrperson.get("/aufnahmen/{aufnahme_id}")
def eigene_abspielen(
    request: Request,
    aufnahme_id: Id,
    db: DB,
    konto: Annotated[Konto, Depends(braucht_lehrperson)],
):
    return _ausliefern(request, eigene_aufnahme(db, konto.id, aufnahme_id))


@verwaltung.get("/aufnahmen/{aufnahme_id}")
def alle_abspielen(request: Request, aufnahme_id: Id, db: DB):
    return _ausliefern(request, aufnahme(db, aufnahme_id))


router.include_router(lehrperson)
router.include_router(verwaltung)
