"""Vorschau fuer die Auftraggeberin: die Seiten der Lehrpersonen an einem gewaehlten Tag."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from app.ansicht import Ansicht, fuer_vorschau
from app.inhalte import lies_projektstart, runden
from app.routen.ohne_speichern import DB_LESEND, MELDUNG_VORSCHAU, registriere_seiten
from app.sitzung import braucht_auftraggeberin
from app.texte import REGISTER, lies_textstand
from app.vorlagen import templates
from app.zeit import datum_kurz, hole_heute, ist_plausibel, lies_datum, woche

router = APIRouter(prefix="/verwaltung/vorschau", dependencies=[Depends(braucht_auftraggeberin)])

AUSGANG = ("Vorschau beenden", "/verwaltung/vorschau")
ZIELE = {"info": "/info"}


@dataclass(frozen=True)
class VorschauTag:
    datum: date
    ist_heute: bool
    woche: int | None
    titel: list[str]


def standardtag(heute: date, projektstart: date | None) -> date:
    return heute if projektstart is None else max(heute, projektstart)


def vorschau_tage(
    runden: Sequence[Mapping[str, Any]], heute: date, projektstart: date | None
) -> list[VorschauTag]:
    """Eine Karte pro Datum: heute immer, dazu jedes Freischaltdatum einer Runde."""
    titel: dict[date, list[str]] = {heute: []}
    for r in runden:
        tag = lies_datum(r["freischaltdatum"])
        if tag is not None:
            titel.setdefault(tag, []).append(r["titel"])
    return [
        VorschauTag(
            tag, tag == heute, None if projektstart is None else woche(tag, projektstart), t
        )
        for tag, t in sorted(titel.items())
    ]


def band_vorschau(stichtag: date, projektstart: date | None, offen: list[str]) -> str:
    nummer = None if projektstart is None else woche(stichtag, projektstart)
    zusatz = "" if nummer is None else f" (Woche {nummer})"
    text = f"Vorschau: So sieht es eine Lehrperson am {datum_kurz(stichtag)}{zusatz}."
    text += " Es wird nichts gespeichert."
    if offen:
        text += "\nNoch Vorschläge statt deiner Texte: " + ", ".join(offen) + "."
    return text


def hole_ansicht_vorschau(am: str, db: DB_LESEND) -> Ansicht:
    stichtag = lies_datum(am)
    if stichtag is None or not ist_plausibel(stichtag):
        raise HTTPException(404)
    offen = [v.bezeichnung for k, v in REGISTER.items() if not lies_textstand(db, k).bestaetigt]
    band = band_vorschau(stichtag, lies_projektstart(db), offen)
    return fuer_vorschau(stichtag, band, AUSGANG)


seiten = APIRouter(prefix="/{am}")
registriere_seiten(seiten, hole_ansicht_vorschau, MELDUNG_VORSCHAU)
router.include_router(seiten)


@router.get("")
def auswahl(
    request: Request,
    db: DB_LESEND,
    heute: Annotated[date, Depends(hole_heute)],
    am: str = "",
    ziel: str = "",
):
    tag = lies_datum(am)
    if tag is not None and not ist_plausibel(tag):
        tag = None
    if ziel not in ZIELE:
        ziel = ""
    projektstart = lies_projektstart(db)
    if tag is None and ziel:
        tag = standardtag(heute, projektstart)
    if tag is not None:
        return RedirectResponse(
            f"/verwaltung/vorschau/{tag.isoformat()}{ZIELE.get(ziel, '')}", status_code=303
        )
    return templates.TemplateResponse(
        request,
        "verwaltung/vorschau.html",
        {"tage": vorschau_tage(runden(db), heute, projektstart)},
    )
