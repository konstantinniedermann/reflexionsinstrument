"""Benachrichtigungen per Web Push: Schlüssel (VAPID) und Versand (#37)."""

import base64
import json
import logging
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from urllib.parse import urlsplit

import http_ece
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02

from app.push_abos import alle_abos, entferne_abo

_log = logging.getLogger(__name__)

ABSENDER = "https://reflexionsinstrument.fly.dev"
GUELTIGKEIT_SIGNATUR = 12 * 3600
LEBENSDAUER_NACHRICHT = 86400  # so lange hält der Push-Dienst sie für ein ausgeschaltetes Gerät
ZEITLIMIT = 10
# Abo abgelaufen oder gekündigt. 401/403 nicht: Das kann auch ein Fehler unserer Signatur sein,
# dann würden beim ersten Versand alle Abos gelöscht. Einen neuen Schlüssel erkennt das Seiten-Skript.
UNGUELTIG = {404, 410}


class _OhneWeiterleitung(urllib.request.HTTPRedirectHandler):
    """Keiner Weiterleitung folgen: Die Signatur gehört nur dem Push-Dienst der Abo-Adresse."""

    def redirect_request(self, *args, **kwargs):
        return None


_OHNE_WEITERLEITUNG = urllib.request.build_opener(_OhneWeiterleitung)


@dataclass(frozen=True)
class Ergebnis:
    gesendet: int
    entfernt: int
    nicht_erreicht: int


def _b64(daten: bytes) -> str:
    return base64.urlsafe_b64encode(daten).rstrip(b"=").decode("ascii")


def erzeuge_vapid_schluessel() -> str:
    """Neuer privater Schlüssel als base64url der rohen 32 Byte, eine Zeile."""
    zahl = ec.generate_private_key(ec.SECP256R1()).private_numbers().private_value
    return _b64(zahl.to_bytes(32, "big"))


def lade_vapid(wert: str) -> Vapid02:
    try:
        roh = base64.urlsafe_b64decode(wert.strip() + "=" * (-len(wert.strip()) % 4))
        if len(roh) != 32:
            raise ValueError("falsche Länge")
        vapid = Vapid02.from_raw(wert.strip().encode("ascii"))
    except Exception as fehler:
        raise ValueError("VAPID_SCHLUESSEL ist kein gültiger Schlüssel.") from fehler
    return vapid


def oeffentlicher_schluessel(vapid: Vapid02) -> str:
    punkt = vapid.public_key.public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint
    )
    return _b64(punkt)


def _unb64(wert: str) -> bytes:
    return base64.urlsafe_b64decode(wert + "=" * (-len(wert) % 4))


def sende(vapid: Vapid02, abo: sqlite3.Row, nutzlast: bytes, oeffne=_OHNE_WEITERLEITUNG.open):
    """Schickt eine Nachricht an ein Gerät. Gibt den HTTP-Status zurück, None bei Netzfehler."""
    teile = urlsplit(abo["endpunkt"])
    koerper = http_ece.encrypt(
        nutzlast,
        private_key=ec.generate_private_key(ec.SECP256R1()),
        dh=_unb64(abo["p256dh"]),
        auth_secret=_unb64(abo["auth"]),
        version="aes128gcm",
    )
    anspruch = {
        "aud": f"{teile.scheme}://{teile.netloc}",
        "sub": ABSENDER,
        "exp": int(time.time()) + GUELTIGKEIT_SIGNATUR,
    }
    anfrage = urllib.request.Request(
        abo["endpunkt"],
        data=koerper,
        method="POST",
        headers={
            **vapid.sign(anspruch),
            "TTL": str(LEBENSDAUER_NACHRICHT),
            "Urgency": "normal",
            "Content-Encoding": "aes128gcm",
            "Content-Type": "application/octet-stream",
        },
    )
    try:
        with oeffne(anfrage, timeout=ZEITLIMIT) as antwort:
            status = antwort.status
    except urllib.error.HTTPError as fehler:
        status = fehler.code
    except (urllib.error.URLError, OSError):
        status = None
    except Exception as fehler:  # noqa: BLE001 - ein Gerät darf den Versand an die anderen nicht stoppen
        # Nur der Typ: der Text kann die Abo-Adresse enthalten.
        _log.warning("Benachrichtigung an %s: %s", teile.hostname, type(fehler).__name__)
        status = None
    # Nur Dienst und Status: Pfad und Schlüssel identifizieren das Gerät, der Text ist Inhalt.
    _log.info("Benachrichtigung an %s: %s", teile.hostname, status or "nicht erreicht")
    return status


def verschicke_an_alle(
    db: sqlite3.Connection, vapid: Vapid02, titel: str, text: str, oeffne=_OHNE_WEITERLEITUNG.open
) -> Ergebnis:
    nutzlast = json.dumps({"titel": titel, "text": text}, ensure_ascii=False).encode("utf-8")
    gesendet = entfernt = nicht_erreicht = 0
    for abo in alle_abos(db):
        status = sende(vapid, abo, nutzlast, oeffne)
        if status in (200, 201, 202):
            gesendet += 1
        elif status in UNGUELTIG:
            entferne_abo(db, abo["id"])
            entfernt += 1
        else:
            nicht_erreicht += 1
    return Ergebnis(gesendet, entfernt, nicht_erreicht)
