"""Eingabemaske der Auftraggeberin: Uebersicht der Inhalte und Allgemeines."""

import sqlite3
from contextlib import contextmanager
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.csrf import pruefe_csrf
from app.db import hole_db
from app.eingaben import Gesperrt, InhaltFehler
from app.inhalte import (
    aendere_frage,
    aendere_runde,
    datum_vorschlag_runde,
    frage,
    fragen,
    lege_frage_an,
    lege_runde_an,
    lies_projektstart,
    lies_titel,
    loesche_frage,
    loesche_runde,
    runde,
    runden,
    speichere_allgemein,
    verschiebe,
    zaehle_antworten_frage,
    zaehle_antworten_runde,
    zaehle_inhalte,
)
from app.sitzung import braucht_auftraggeberin
from app.texte import lies_texte, lies_textstand
from app.typen import Id
from app.vorlagen import templates, zahl
from app.zeit import hole_heute, zeitplan

router = APIRouter(prefix="/verwaltung/inhalte", dependencies=[Depends(braucht_auftraggeberin)])

DB = Annotated[sqlite3.Connection, Depends(hole_db)]
HEUTE = Annotated[date, Depends(hole_heute)]

# Der Text kommt aus dieser Tabelle, nie aus der Adresse.
ERLEDIGT = {"gespeichert": "Gespeichert.", "angelegt": "Angelegt.", "geloescht": "Gelöscht."}


def _meldung(request: Request) -> str | None:
    return ERLEDIGT.get(request.query_params.get("erledigt", ""))


def _weiter(pfad: str, erledigt: str | None = None, anker: str | None = None):
    ziel = pfad if erledigt is None else f"{pfad}?erledigt={erledigt}"
    if anker:
        ziel = f"{ziel}#{anker}"
    return RedirectResponse(ziel, status_code=303)


def _oder_404(zeile):
    if zeile is None:
        raise HTTPException(404)
    return zeile


@contextmanager
def _vorhanden():
    """Ein Eintrag, der zwischen Anzeige und Absenden verschwunden ist, ergibt 404."""
    try:
        yield
    except LookupError:
        raise HTTPException(404) from None


@router.get("")
def uebersicht(request: Request, db: DB):
    zahlen = zaehle_inhalte(db)
    hinweise = lies_texte(db, "hinweise")
    start = lies_projektstart(db)
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/uebersicht.html",
        {
            "zahlen": zahlen,
            "projektstart": start,
            "begruessung_offen": not lies_textstand(db, "begruessung").bestaetigt,
            "hinweise_bestaetigt": sum(1 for h in hinweise if h.bestaetigt),
            "hinweise_gesamt": len(hinweise),
        },
    )


def _allgemein_seite(request: Request, db: sqlite3.Connection, status=200, werte=None, fehler=None):
    stand = lies_textstand(db, "begruessung")
    start = lies_projektstart(db)
    gespeichert = {
        "titel": lies_titel(db),
        "begruessung": stand.inhalt,
        "projektstart": "" if start is None else start.isoformat(),
    }
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/allgemein.html",
        {
            "stand": stand,
            "werte": werte or gespeichert,
            "fehler": fehler or {},
            "meldung": _meldung(request),
        },
        status_code=status,
    )


@router.get("/allgemein")
def allgemein(request: Request, db: DB):
    return _allgemein_seite(request, db)


@router.post("/allgemein", dependencies=[Depends(pruefe_csrf)])
def allgemein_speichern(
    request: Request,
    db: DB,
    titel: Annotated[str, Form()] = "",
    begruessung: Annotated[str, Form()] = "",
    projektstart: Annotated[str, Form()] = "",
):
    try:
        speichere_allgemein(db, titel, begruessung, projektstart)
    except InhaltFehler as fehler:
        werte = {"titel": titel, "begruessung": begruessung, "projektstart": projektstart}
        return _allgemein_seite(request, db, 400, werte, {fehler.feld: fehler.meldung})
    return _weiter("/verwaltung/inhalte/allgemein", "gespeichert")


# ---------- Runden ----------

INHALTE = "/verwaltung/inhalte"
RUNDEN = f"{INHALTE}/runden"


@router.get("/runden")
def runden_liste(request: Request, db: DB, heute: HEUTE):
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/runden.html",
        {
            "runden": runden(db),
            "projektstart": lies_projektstart(db),
            "heute": heute,
            "meldung": _meldung(request),
        },
    )


def _runde_formular(
    request, ueberschrift, aktion, abbrechen, werte, fehler=None, status=200, **mehr
):
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/formular_runde.html",
        {
            "ueberschrift": ueberschrift,
            "aktion": aktion,
            "abbrechen": abbrechen,
            "werte": werte,
            "fehler": fehler or {},
            "schon_sichtbar": False,
            **mehr,
        },
        status_code=status,
    )


def _neue_runde_seite(
    request: Request, db: sqlite3.Connection, werte=None, fehler=None, status=200
):
    if werte is None:
        vorschlag = datum_vorschlag_runde(db)
        werte = {
            "titel": "",
            "freischaltdatum": "" if vorschlag is None else vorschlag.isoformat(),
            "fallbeispiel": "",
        }
    return _runde_formular(request, "Neue Runde", RUNDEN, RUNDEN, werte, fehler, status)


@router.get("/runden/neu")
def runde_neu(request: Request, db: DB):
    return _neue_runde_seite(request, db)


@router.post("/runden", dependencies=[Depends(pruefe_csrf)])
def runde_anlegen(
    request: Request,
    db: DB,
    titel: Annotated[str, Form()] = "",
    freischaltdatum: Annotated[str, Form()] = "",
    fallbeispiel: Annotated[str, Form()] = "",
):
    try:
        runde_id = lege_runde_an(db, titel, fallbeispiel, freischaltdatum)
    except InhaltFehler as fehler:
        werte = {"titel": titel, "freischaltdatum": freischaltdatum, "fallbeispiel": fallbeispiel}
        return _neue_runde_seite(request, db, werte, {fehler.feld: fehler.meldung}, 400)
    return _weiter(f"{RUNDEN}/{runde_id}", "angelegt")


@router.get("/runden/{runde_id}")
def runde_seite(request: Request, runde_id: Id, db: DB, heute: HEUTE):
    zeile = _oder_404(runde(db, runde_id))
    start = lies_projektstart(db)
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/runde.html",
        {
            "runde": zeile,
            "fragen": fragen(db, runde_id),
            "projektstart": start,
            "zp": zeitplan(zeile["freischaltdatum"], start, heute),
            "meldung": _meldung(request),
        },
    )


def _bearbeiten_seite(
    request: Request,
    db: sqlite3.Connection,
    zeile,
    heute: date,
    werte=None,
    fehler=None,
    status=200,
):
    seite = f"{RUNDEN}/{zeile['id']}"
    if werte is None:
        werte = {
            "titel": zeile["titel"],
            "freischaltdatum": zeile["freischaltdatum"],
            "fallbeispiel": zeile["fallbeispiel"] or "",
        }
    sichtbar = zeitplan(zeile["freischaltdatum"], None, heute).sichtbar
    return _runde_formular(
        request,
        "Angaben der Runde",
        f"{seite}/bearbeiten",
        seite,
        werte,
        fehler,
        status,
        schon_sichtbar=sichtbar,
    )


@router.get("/runden/{runde_id}/bearbeiten")
def runde_bearbeiten(request: Request, runde_id: Id, db: DB, heute: HEUTE):
    return _bearbeiten_seite(request, db, _oder_404(runde(db, runde_id)), heute)


@router.post("/runden/{runde_id}/bearbeiten", dependencies=[Depends(pruefe_csrf)])
def runde_speichern(
    request: Request,
    runde_id: Id,
    db: DB,
    heute: HEUTE,
    titel: Annotated[str, Form()] = "",
    freischaltdatum: Annotated[str, Form()] = "",
    fallbeispiel: Annotated[str, Form()] = "",
):
    zeile = _oder_404(runde(db, runde_id))
    try:
        with _vorhanden():
            aendere_runde(db, runde_id, titel, fallbeispiel, freischaltdatum)
    except InhaltFehler as fehler:
        werte = {"titel": titel, "freischaltdatum": freischaltdatum, "fallbeispiel": fallbeispiel}
        return _bearbeiten_seite(
            request, db, zeile, heute, werte, {fehler.feld: fehler.meldung}, 400
        )
    return _weiter(f"{RUNDEN}/{runde_id}", "gespeichert")


def _loeschen_seite(request: Request, status: int = 200, **kontext):
    kontext.setdefault("folgen", None)
    kontext.setdefault("gesperrt", None)
    return templates.TemplateResponse(
        request, "verwaltung/inhalte/loeschen.html", kontext, status_code=status
    )


def _runde_loeschen_seite(request: Request, zeile, antworten: int, status: int = 200):
    seite = f"{RUNDEN}/{zeile['id']}"
    kontext = {
        "ueberschrift": "Runde löschen",
        "frage_text": f"Runde ‹{zeile['titel']}› löschen?",
        "aktion": f"{seite}/loeschen",
        "zurueck": seite,
    }
    if antworten:
        kontext["gesperrt"] = (
            f"Die Fragen dieser Runde wurden schon {antworten}-mal beantwortet. "
            "Damit keine Antworten verloren gehen, lässt sich die Runde nicht löschen. "
            "Ihre Angaben und die Texte ihrer Fragen kannst du weiterhin ändern."
        )
    else:
        kontext["folgen"] = (
            f"Die Runde und ihre {zahl(zeile['anzahl_fragen'], 'Frage', 'Fragen')} werden gelöscht."
        )
    return _loeschen_seite(request, status, **kontext)


@router.get("/runden/{runde_id}/loeschen")
def runde_loeschen_seite(request: Request, runde_id: Id, db: DB):
    zeile = _oder_404(runde(db, runde_id))
    return _runde_loeschen_seite(request, zeile, zaehle_antworten_runde(db, runde_id))


@router.post("/runden/{runde_id}/loeschen", dependencies=[Depends(pruefe_csrf)])
def runde_loeschen(request: Request, runde_id: Id, db: DB):
    zeile = _oder_404(runde(db, runde_id))
    try:
        with _vorhanden():
            loesche_runde(db, runde_id)
    except Gesperrt as gesperrt:
        return _runde_loeschen_seite(request, zeile, gesperrt.anzahl, 409)
    return _weiter(RUNDEN, "geloescht")


# ---------- Fragen ----------

FRAGEN = f"{INHALTE}/fragen"


def _frage_formular(
    request: Request,
    ueberschrift: str,
    aktion: str,
    abbrechen: str,
    werte: dict,
    fehler: dict | None = None,
    status: int = 200,
    zeile=None,
):
    antworten = 0 if zeile is None else zeile["anzahl_antworten"]
    return templates.TemplateResponse(
        request,
        "verwaltung/inhalte/formular_frage.html",
        {
            "ueberschrift": ueberschrift,
            "aktion": aktion,
            "abbrechen": abbrechen,
            "werte": werte,
            "fehler": fehler or {},
            "anzahl_antworten": antworten,
            # Bei Antworten gilt immer die gespeicherte Art, nie die abgeschickte.
            "bisherige_art": None if zeile is None else zeile["typ"],
        },
        status_code=status,
    )


def _neue_frage_seite(request: Request, zeile_runde, werte=None, fehler=None, status=200):
    werte = werte or {"typ": "freitext", "text": "", "skala_min_text": "", "skala_max_text": ""}
    seite = f"{RUNDEN}/{zeile_runde['id']}"
    return _frage_formular(request, "Neue Frage", f"{seite}/fragen", seite, werte, fehler, status)


@router.get("/runden/{runde_id}/fragen/neu")
def frage_neu(request: Request, runde_id: Id, db: DB):
    return _neue_frage_seite(request, _oder_404(runde(db, runde_id)))


@router.post("/runden/{runde_id}/fragen", dependencies=[Depends(pruefe_csrf)])
def frage_anlegen(
    request: Request,
    runde_id: Id,
    db: DB,
    typ: Annotated[str, Form()] = "",
    text: Annotated[str, Form()] = "",
    skala_min_text: Annotated[str, Form()] = "",
    skala_max_text: Annotated[str, Form()] = "",
):
    zeile = _oder_404(runde(db, runde_id))
    try:
        with _vorhanden():
            frage_id = lege_frage_an(db, runde_id, typ, text, skala_min_text, skala_max_text)
    except InhaltFehler as fehler:
        werte = {
            "typ": typ,
            "text": text,
            "skala_min_text": skala_min_text,
            "skala_max_text": skala_max_text,
        }
        return _neue_frage_seite(request, zeile, werte, {fehler.feld: fehler.meldung}, 400)
    return _weiter(f"{RUNDEN}/{runde_id}", "angelegt", f"frage-{frage_id}")


def _frage_bearbeiten_seite(request: Request, zeile, werte=None, fehler=None, status=200):
    if werte is None:
        werte = {
            "typ": zeile["typ"],
            "text": zeile["text"],
            "skala_min_text": zeile["skala_min_text"] or "",
            "skala_max_text": zeile["skala_max_text"] or "",
        }
    return _frage_formular(
        request,
        "Frage bearbeiten",
        f"{FRAGEN}/{zeile['id']}",
        f"{RUNDEN}/{zeile['runde_id']}#frage-{zeile['id']}",
        werte,
        fehler,
        status,
        zeile,
    )


@router.get("/fragen/{frage_id}")
def frage_bearbeiten(request: Request, frage_id: Id, db: DB):
    return _frage_bearbeiten_seite(request, _oder_404(frage(db, frage_id)))


@router.post("/fragen/{frage_id}", dependencies=[Depends(pruefe_csrf)])
def frage_speichern(
    request: Request,
    frage_id: Id,
    db: DB,
    typ: Annotated[str, Form()] = "",
    text: Annotated[str, Form()] = "",
    skala_min_text: Annotated[str, Form()] = "",
    skala_max_text: Annotated[str, Form()] = "",
):
    zeile = _oder_404(frage(db, frage_id))
    try:
        with _vorhanden():
            aendere_frage(db, frage_id, typ, text, skala_min_text, skala_max_text)
    except InhaltFehler as fehler:
        werte = {
            "typ": typ,
            "text": text,
            "skala_min_text": skala_min_text,
            "skala_max_text": skala_max_text,
        }
        return _frage_bearbeiten_seite(request, zeile, werte, {fehler.feld: fehler.meldung}, 400)
    return _weiter(f"{RUNDEN}/{zeile['runde_id']}", "gespeichert", f"frage-{frage_id}")


@router.post("/fragen/{frage_id}/verschieben", dependencies=[Depends(pruefe_csrf)])
def frage_verschieben(db: DB, frage_id: Id, richtung: Annotated[str, Form()] = ""):
    zeile = _oder_404(frage(db, frage_id))
    try:
        verschiebe(db, "frage", frage_id, richtung)
    except ValueError:
        raise HTTPException(400) from None
    return _weiter(f"{RUNDEN}/{zeile['runde_id']}", anker=f"frage-{frage_id}")


def _frage_loeschen_seite(request: Request, zeile, antworten: int, status: int = 200):
    seite = f"{RUNDEN}/{zeile['runde_id']}#frage-{zeile['id']}"
    kontext = {
        "ueberschrift": "Frage löschen",
        "frage_text": f"Frage ‹{zeile['text']}› löschen?",
        "aktion": f"{FRAGEN}/{zeile['id']}/loeschen",
        "zurueck": seite,
    }
    if antworten:
        kontext["gesperrt"] = (
            f"Diese Frage wurde schon {antworten}-mal beantwortet. "
            "Damit keine Antworten verloren gehen, lässt sie sich nicht löschen. "
            "Den Text kannst du weiterhin ändern."
        )
    return _loeschen_seite(request, status, **kontext)


@router.get("/fragen/{frage_id}/loeschen")
def frage_loeschen_seite(request: Request, frage_id: Id, db: DB):
    zeile = _oder_404(frage(db, frage_id))
    return _frage_loeschen_seite(request, zeile, zaehle_antworten_frage(db, frage_id))


@router.post("/fragen/{frage_id}/loeschen", dependencies=[Depends(pruefe_csrf)])
def frage_loeschen(request: Request, frage_id: Id, db: DB):
    zeile = _oder_404(frage(db, frage_id))
    try:
        with _vorhanden():
            loesche_frage(db, frage_id)
    except Gesperrt as gesperrt:
        return _frage_loeschen_seite(request, zeile, gesperrt.anzahl, 409)
    return _weiter(f"{RUNDEN}/{zeile['runde_id']}", "geloescht")
