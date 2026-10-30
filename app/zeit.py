"""Datum in Zuerich. Einziges Modul, das die Uhr kennt."""

import re
from datetime import UTC, date, datetime
from typing import NamedTuple
from zoneinfo import ZoneInfo

from starlette.requests import Request

ZEITZONE = ZoneInfo("Europe/Zurich")
WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")

JAHR_VON = 2020
JAHR_BIS = 2099

_DATUM = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def heute(jetzt: datetime | None = None) -> date:
    """Heutiges Datum in Zuerich; `jetzt` muss zeitzonenbewusst sein."""
    if jetzt is None:
        jetzt = datetime.now(ZEITZONE)
    return jetzt.astimezone(ZEITZONE).date()


def hole_heute(request: Request) -> date:
    return request.app.state.heute()


def zeitstempel(jetzt: datetime | None = None) -> str:
    """UTC-Text fuer die Datenbank, z. B. '2026-11-23T17:40:00Z'. Einzige Stelle mit der Uhr."""
    if jetzt is None:
        jetzt = datetime.now(UTC)
    return jetzt.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def lokal(zeitstempel: str) -> datetime:
    """UTC-Text aus der Datenbank als zeitzonenbewusste Zeit in Europe/Zurich."""
    utc = datetime.strptime(zeitstempel, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
    return utc.astimezone(ZEITZONE)


def lies_datum(text: str) -> date | None:
    if not _DATUM.match(text):
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def ist_plausibel(datum: date) -> bool:
    return JAHR_VON <= datum.year <= JAHR_BIS


def ist_erreicht(datum: date, heute: date) -> bool:
    return datum <= heute


def woche(datum: date, projektstart: date) -> int | None:
    tage = (datum - projektstart).days
    if tage < 0:
        return None
    return tage // 7 + 1


def datum_kurz(datum: date, mit_jahr: bool = True) -> str:
    text = f"{WOCHENTAGE[datum.weekday()]} {datum.day:02d}.{datum.month:02d}."
    return f"{text}{datum.year}" if mit_jahr else text


def zeitpunkt_kurz(zeitstempel: str) -> str:
    """'Mo 23.11.2026, 18:40'."""
    zeit = lokal(zeitstempel)
    return f"{datum_kurz(zeit.date())}, {zeit:%H:%M}"


class Zeitplan(NamedTuple):
    datum: date
    woche: int | None
    sichtbar: bool


def zeitplan(datum_text: str, projektstart: date | None, heute: date) -> Zeitplan:
    """`datum_text` stammt aus der Datenbank und ist gueltig."""
    datum = date.fromisoformat(datum_text)
    return Zeitplan(
        datum,
        None if projektstart is None else woche(datum, projektstart),
        ist_erreicht(datum, heute),
    )
