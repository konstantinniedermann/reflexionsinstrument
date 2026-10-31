"""Sitzung: signiertes Cookie, Widerruf ueber die Sitzungsversion, Rollenpruefung."""

import sqlite3
import time
from typing import Annotated

from fastapi import Depends
from itsdangerous import BadData, URLSafeTimedSerializer
from starlette.requests import Request

from app.cookies import CSRF_MAX_AGE, loesche_cookie, setze_cookie
from app.csrf import erneuere_csrf
from app.db import hole_db
from app.konten import Konto, finde_konto
from app.zugriff import KeinZugriff, NichtAngemeldet

DAUER_LANG = 30 * 24 * 3600
DAUER_KURZ = 12 * 3600
VERLAENGERN_AB = 24 * 3600

STARTSEITE = {"lehrperson": "/lehrperson", "auftraggeberin": "/verwaltung/inhalte"}

COOKIE = "sitzung"


def _serializer(request: Request) -> URLSafeTimedSerializer:
    schluessel = request.app.state.einstellungen.geheimer_schluessel
    return URLSafeTimedSerializer(schluessel, salt="sitzung")


def _setze_sitzungscookie(request: Request, konto: Konto, dauerhaft: bool) -> None:
    inhalt = {"k": konto.id, "v": konto.sitzungsversion, "d": dauerhaft}
    wert = _serializer(request).dumps(inhalt)
    setze_cookie(request, COOKIE, wert, DAUER_LANG if dauerhaft else None)


def anmelden(request: Request, konto: Konto, dauerhaft: bool) -> None:
    _setze_sitzungscookie(request, konto, dauerhaft)
    request.state.konto = konto
    erneuere_csrf(request)


def abmelden(request: Request) -> None:
    loesche_cookie(request, COOKIE)
    request.state.konto = None
    erneuere_csrf(request)


def _lese_inhalt(request: Request, wert: str) -> tuple[int, int, bool, float] | None:
    """Gibt (konto_id, version, dauerhaft, alter) zurueck oder None bei jedem Mangel."""
    try:
        inhalt, zeitpunkt = _serializer(request).loads(wert, return_timestamp=True)
        konto_id, version, dauerhaft = inhalt["k"], inhalt["v"], inhalt["d"]
        zeitpunkt_sekunden = zeitpunkt.timestamp()
    except (BadData, KeyError, TypeError, ValueError, AttributeError):
        return None
    if type(konto_id) is not int or type(version) is not int or type(dauerhaft) is not bool:
        return None
    alter = time.time() - zeitpunkt_sekunden
    if alter > (DAUER_LANG if dauerhaft else DAUER_KURZ):
        return None
    return konto_id, version, dauerhaft, alter


def aktuelles_konto(
    request: Request, db: Annotated[sqlite3.Connection, Depends(hole_db)]
) -> Konto | None:
    if hasattr(request.state, "konto"):
        return request.state.konto
    konto = None
    wert = request.cookies.get(COOKIE)
    if wert is not None:
        gelesen = _lese_inhalt(request, wert)
        if gelesen is not None:
            konto_id, version, dauerhaft, alter = gelesen
            kandidat = finde_konto(db, konto_id)
            if kandidat is not None and kandidat.sitzungsversion == version:
                konto = kandidat
                if dauerhaft and alter > VERLAENGERN_AB:
                    _setze_sitzungscookie(request, konto, True)
                    # csrf-Cookie mitverlaengern (gleicher Wert), sonst scheitert ein Formular,
                    # das am Ende der Laufzeit geladen wurde.
                    setze_cookie(request, "csrf", request.state.csrf_wert, CSRF_MAX_AGE)
        if konto is None:
            loesche_cookie(request, COOKIE)
    request.state.konto = konto
    return konto


def braucht_konto(konto: Annotated[Konto | None, Depends(aktuelles_konto)]) -> Konto:
    if konto is None:
        raise NichtAngemeldet
    return konto


def _braucht(rolle: str, konto: Konto | None) -> Konto:
    if konto is None:
        raise NichtAngemeldet
    if konto.rolle != rolle:
        raise KeinZugriff
    return konto


def braucht_lehrperson(konto: Annotated[Konto | None, Depends(aktuelles_konto)]) -> Konto:
    return _braucht("lehrperson", konto)


def braucht_auftraggeberin(konto: Annotated[Konto | None, Depends(aktuelles_konto)]) -> Konto:
    return _braucht("auftraggeberin", konto)
