"""Benachrichtigungen per Web Push: Schlüssel (VAPID) und Versand (#37)."""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec
from py_vapid import Vapid02


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
