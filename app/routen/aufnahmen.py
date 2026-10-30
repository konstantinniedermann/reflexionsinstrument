"""Sprachaufnahmen: Speichern (Tagebuch) und Anhoeren (Lehrperson: eigene, Auftraggeberin: alle)."""

import re
import sqlite3
from collections.abc import Callable
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from starlette.datastructures import UploadFile

from app import aufnahmen, eintraege, groesse, inhalte
from app.ansicht import Ansicht, hole_ansicht_lehrperson
from app.aufnahmen import AufnahmeFehler, aufnahme, aufnahme_pfad, eigene_aufnahme
from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import InhaltFehler
from app.groesse import ZuGross
from app.konten import Konto
from app.sichtbar import sichtbare_runde
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


async def _speichere_upload(
    request: Request,
    mit_text: bool,
    uebernehmen: Callable[[aufnahmen.Datei, int | None, str | None], RedirectResponse],
    fehlerseite: Callable[[str, int], Response],
) -> Response:
    """Liest und speichert die Datei; `uebernehmen` legt die Zeilen an und gibt die Weiterleitung."""
    verzeichnis = _verzeichnis(request)
    try:
        datei, dauer, text = await _lies_aufnahme(request)
        text = eintraege.lies_tagebuchtext(text, pflicht=False) if mit_text else None
        gespeichert = aufnahmen.schreibe_datei(datei.file, verzeichnis)
    except InhaltFehler as fehler:
        return fehlerseite(fehler.meldung, 400)
    except AufnahmeFehler as fehler:
        if fehler.status != 400:
            raise HTTPException(fehler.status) from None
        return fehlerseite(fehler.meldung, 400)
    try:
        antwort = uebernehmen(gespeichert, dauer, text)
    except BaseException:
        aufnahmen.loesche_dateien(verzeichnis, [gespeichert.name])
        raise
    return antwort


@lehrperson.post(
    "/tagebuch/neu/aufnahme",
    dependencies=[Depends(begrenze_upload), Depends(pruefe_csrf)],
)
async def tagebuch_aufnahme_speichern(request: Request, db: DB, ansicht: ANSICHT):
    def uebernehmen(gespeichert: aufnahmen.Datei, dauer: int | None, text: str | None):
        eintrag_id = aufnahmen.aufnahme_als_tagebucheintrag(
            db, ansicht.konto_id, gespeichert, dauer, text
        )
        return RedirectResponse(f"/lehrperson/tagebuch/{eintrag_id}?erledigt=gespeichert", 303)

    antwort = await _speichere_upload(
        request,
        True,
        uebernehmen,
        lambda meldung, status: _seite_tagebuch(request, db, ansicht, meldung, status),
    )
    aufnahmen.raeume_waisen(db, _verzeichnis(request))
    return antwort


def _freitext_frage(
    db: sqlite3.Connection, ansicht: Ansicht, runde_id: int, frage_id: int
) -> tuple[sqlite3.Row, sqlite3.Row]:
    """Runde (sichtbar) und Freitext-Frage dieser Runde; sonst 404."""
    runde = sichtbare_runde(db, runde_id, ansicht.stichtag)
    if runde is None:
        raise HTTPException(404)
    for frage in inhalte.fragen(db, runde_id):
        if frage["id"] == frage_id and frage["typ"] == "freitext":
            return runde, frage
    raise HTTPException(404)


def _antwort_pfad(runde_id: int, frage_id: int) -> str:
    return f"/lehrperson/runden/{runde_id}/fragen/{frage_id}/aufnahme"


def _seite_antwort(
    request: Request,
    db: sqlite3.Connection,
    ansicht: Ansicht,
    runde: sqlite3.Row,
    frage: sqlite3.Row,
    meldung: str | None = None,
    status: int = 200,
):
    ziel = f"/lehrperson/runden/{runde['id']}#frage-{frage['id']}"
    kontext = {
        "ansicht": ansicht,
        "bereich": "runden",
        "meldung": meldung,
        "frage": frage,
        "bisherige": aufnahmen.aufnahme_der_antwort(db, ansicht.konto_id, frage["id"]),
        "hinweis_tagebuch": lies_text(db, "hinweis_tagebuch"),
        "hinweis_aufnahme": lies_text(db, "hinweis_aufnahme"),
        "max_dauer": aufnahmen.MAX_DAUER_SEKUNDEN,
        "max_bytes": aufnahmen.MAX_BYTES,
        "aktion": _antwort_pfad(runde["id"], frage["id"]),
        "zurueck": ziel,
        "schreiben": ziel,
    }
    return templates.TemplateResponse(
        request, "lehrperson/aufnahme_antwort.html", kontext, status_code=status
    )


@lehrperson.get("/runden/{runde_id}/fragen/{frage_id}/aufnahme")
def antwort_aufnahme_seite(request: Request, runde_id: Id, frage_id: Id, db: DB, ansicht: ANSICHT):
    runde, frage = _freitext_frage(db, ansicht, runde_id, frage_id)
    return _seite_antwort(request, db, ansicht, runde, frage)


@lehrperson.post(
    "/runden/{runde_id}/fragen/{frage_id}/aufnahme",
    dependencies=[Depends(begrenze_upload), Depends(pruefe_csrf)],
)
async def antwort_aufnahme_speichern(
    request: Request, runde_id: Id, frage_id: Id, db: DB, ansicht: ANSICHT
):
    runde, frage = _freitext_frage(db, ansicht, runde_id, frage_id)
    verzeichnis = _verzeichnis(request)

    def uebernehmen(gespeichert: aufnahmen.Datei, dauer: int | None, _text: str | None):
        aufnahmen.haenge_an_antwort(db, ansicht.konto_id, frage_id, gespeichert, dauer, verzeichnis)
        return RedirectResponse(
            f"/lehrperson/runden/{runde_id}?erledigt=gespeichert#frage-{frage_id}", 303
        )

    antwort = await _speichere_upload(
        request,
        False,
        uebernehmen,
        lambda meldung, status: _seite_antwort(request, db, ansicht, runde, frage, meldung, status),
    )
    aufnahmen.raeume_waisen(db, verzeichnis)
    return antwort


def _seite_loeschen(request: Request, ansicht: Ansicht, runde_id: int, frage_id: int):
    kontext = {
        "ansicht": ansicht,
        "bereich": "runden",
        "frage_text": "Die Aufnahme zu dieser Frage löschen? Deine geschriebene Antwort bleibt.",
        "aktion": f"{_antwort_pfad(runde_id, frage_id)}/loeschen",
        "zurueck": f"/lehrperson/runden/{runde_id}#frage-{frage_id}",
    }
    return templates.TemplateResponse(request, "lehrperson/loeschen.html", kontext)


@lehrperson.get("/runden/{runde_id}/fragen/{frage_id}/aufnahme/loeschen")
def antwort_aufnahme_loeschen_seite(
    request: Request, runde_id: Id, frage_id: Id, db: DB, ansicht: ANSICHT
):
    _freitext_frage(db, ansicht, runde_id, frage_id)
    if aufnahmen.aufnahme_der_antwort(db, ansicht.konto_id, frage_id) is None:
        raise HTTPException(404)
    return _seite_loeschen(request, ansicht, runde_id, frage_id)


@lehrperson.post(
    "/runden/{runde_id}/fragen/{frage_id}/aufnahme/loeschen", dependencies=[Depends(pruefe_csrf)]
)
def antwort_aufnahme_loeschen(
    request: Request, runde_id: Id, frage_id: Id, db: DB, ansicht: ANSICHT
):
    _freitext_frage(db, ansicht, runde_id, frage_id)
    if not aufnahmen.loesche_aufnahme_der_antwort(
        db, ansicht.konto_id, frage_id, _verzeichnis(request)
    ):
        raise HTTPException(404)
    return RedirectResponse(
        f"/lehrperson/runden/{runde_id}?erledigt=aufnahme_geloescht#frage-{frage_id}", 303
    )


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
