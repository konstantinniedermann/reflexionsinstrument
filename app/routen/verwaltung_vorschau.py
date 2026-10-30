"""Vorschau fuer die Auftraggeberin: die Seiten der Lehrpersonen an einem gewaehlten Tag."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException

from app.ansicht import Ansicht, fuer_vorschau
from app.inhalte import lies_projektstart
from app.routen.ohne_speichern import DB_LESEND, MELDUNG_VORSCHAU, registriere_seiten
from app.sitzung import braucht_auftraggeberin
from app.texte import REGISTER, lies_textstand
from app.zeit import datum_kurz, ist_plausibel, lies_datum, woche

router = APIRouter(prefix="/verwaltung/vorschau", dependencies=[Depends(braucht_auftraggeberin)])

AUSGANG = ("Vorschau beenden", "/verwaltung/vorschau")


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
