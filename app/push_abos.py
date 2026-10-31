"""Benachrichtigungs-Abos: Prüfung und Speicherung (#37).

Der Server schickt später eine Anfrage an die gespeicherte Adresse. Deshalb sind nur
Adressen bekannter Push-Dienste erlaubt (Schutz gegen Anfragen an beliebige Server).
"""

import base64
import binascii
import re
import sqlite3
from dataclasses import dataclass
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec

ERLAUBTE_DIENSTE = (
    "push.apple.com",
    "fcm.googleapis.com",
    "push.services.mozilla.com",
    "notify.windows.com",
)
MAX_LAENGE_ENDPUNKT = 1000
MAX_ABOS_PRO_KONTO = 10


@dataclass(frozen=True)
class Abo:
    endpunkt: str
    p256dh: str
    auth: str


def _bytes(wert: str) -> bytes:
    try:
        return base64.urlsafe_b64decode(wert + "=" * (-len(wert) % 4))
    except (binascii.Error, ValueError) as fehler:
        raise ValueError("kein base64url") from fehler


def _erlaubter_host(host: str) -> bool:
    return any(host == d or host.endswith("." + d) for d in ERLAUBTE_DIENSTE)


def pruefe_abo(endpunkt: str, p256dh: str, auth: str) -> Abo:
    if not endpunkt or len(endpunkt) > MAX_LAENGE_ENDPUNKT:
        raise ValueError("Adresse fehlt oder ist zu lang")
    # Nur sichtbares ASCII: Leer- und Steuerzeichen liessen den Versand später scheitern.
    if not re.fullmatch(r"[!-~]+", endpunkt):
        raise ValueError("Adresse nicht erlaubt")
    teile = urlsplit(endpunkt)
    if teile.scheme != "https" or teile.username or teile.password:
        raise ValueError("Adresse nicht erlaubt")
    if teile.port not in (None, 443) or not _erlaubter_host(teile.hostname or ""):
        raise ValueError("Adresse nicht erlaubt")
    punkt = _bytes(p256dh)
    if len(punkt) != 65 or punkt[0] != 4:
        raise ValueError("Schlüssel des Geräts ungültig")
    ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(), punkt)
    if len(_bytes(auth)) != 16:
        raise ValueError("Schlüssel des Geräts ungültig")
    return Abo(endpunkt, p256dh, auth)


def speichere_abo(db: sqlite3.Connection, konto_id: int, abo: Abo) -> None:
    """Speichert das Abo; ein schon bekanntes Gerät gehört danach diesem Konto."""
    db.execute("BEGIN IMMEDIATE")
    try:
        db.execute(
            "INSERT INTO push_abos (konto_id, endpunkt, p256dh, auth) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(endpunkt) DO UPDATE SET konto_id = excluded.konto_id, "
            "p256dh = excluded.p256dh, auth = excluded.auth",
            (konto_id, abo.endpunkt, abo.p256dh, abo.auth),
        )
        db.execute(
            "DELETE FROM push_abos WHERE konto_id = ? AND id NOT IN "
            "(SELECT id FROM push_abos WHERE konto_id = ? ORDER BY id DESC LIMIT ?)",
            (konto_id, konto_id, MAX_ABOS_PRO_KONTO),
        )
        db.execute("COMMIT")
    except Exception:
        if db.in_transaction:
            db.execute("ROLLBACK")
        raise


def loesche_abo(db: sqlite3.Connection, konto_id: int, endpunkt: str) -> bool:
    zeiger = db.execute(
        "DELETE FROM push_abos WHERE konto_id = ? AND endpunkt = ?", (konto_id, endpunkt)
    )
    return zeiger.rowcount > 0


def alle_abos(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT id, endpunkt, p256dh, auth FROM push_abos ORDER BY id").fetchall()


def entferne_abo(db: sqlite3.Connection, abo_id: int) -> None:
    db.execute("DELETE FROM push_abos WHERE id = ?", (abo_id,))


def anzahl_abos(db: sqlite3.Connection) -> int:
    return db.execute("SELECT COUNT(*) FROM push_abos").fetchone()[0]
