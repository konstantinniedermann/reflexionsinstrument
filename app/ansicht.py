"""Gemeinsame Darstellung fuer Lehrperson, Gast und Vorschau."""

from dataclasses import dataclass
from datetime import date
from typing import Annotated, Literal

from fastapi import Depends

from app.konten import Konto
from app.sitzung import braucht_lehrperson
from app.zeit import hole_heute

Modus = Literal["lehrperson", "gast", "vorschau"]


@dataclass(frozen=True)
class Ansicht:
    modus: Modus
    stichtag: date  # bis zu diesem Tag sind Runden und Impulse sichtbar
    basis: str  # "/lehrperson", "/gast", "/verwaltung/vorschau/2026-11-30"
    konto_id: int | None  # nur bei "lehrperson"; sonst None
    band: str | None = None  # Text des Bands oben (Gast, Vorschau)
    ausgang: tuple[str, str] | None = None  # (Text, Adresse): Link oben rechts im Kopf

    def __post_init__(self) -> None:
        if (self.modus == "lehrperson") != (self.konto_id is not None):
            raise ValueError("konto_id ist genau im Modus 'lehrperson' gesetzt")

    @property
    def speichert(self) -> bool:
        return self.modus == "lehrperson"

    @property
    def zeigt_eintraege(self) -> bool:
        return self.modus == "lehrperson"

    def url(self, pfad: str = "") -> str:
        return self.basis + pfad


def fuer_lehrperson(konto: Konto, heute: date) -> Ansicht:
    return Ansicht("lehrperson", heute, "/lehrperson", konto.id)


def fuer_gast(heute: date, band: str, ausgang: tuple[str, str]) -> Ansicht:
    return Ansicht("gast", heute, "/gast", None, band, ausgang)


def fuer_vorschau(stichtag: date, band: str, ausgang: tuple[str, str]) -> Ansicht:
    basis = f"/verwaltung/vorschau/{stichtag.isoformat()}"
    return Ansicht("vorschau", stichtag, basis, None, band, ausgang)


def hole_ansicht_lehrperson(
    konto: Annotated[Konto, Depends(braucht_lehrperson)],
    heute: Annotated[date, Depends(hole_heute)],
) -> Ansicht:
    return fuer_lehrperson(konto, heute)
