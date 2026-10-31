"""Benachrichtigungs-Abos: Prüfung der Adresse und Speichern pro Konto (#37)."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

from app.konten import loesche_konto
from app.push_abos import (
    Abo,
    alle_abos,
    anzahl_abos,
    entferne_abo,
    loesche_abo,
    pruefe_abo,
    speichere_abo,
)

_PUNKT = (
    ec.generate_private_key(ec.SECP256R1())
    .public_key()
    .public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
)
P256DH = base64.urlsafe_b64encode(_PUNKT).rstrip(b"=").decode()
AUTH = base64.urlsafe_b64encode(b"\x02" * 16).rstrip(b"=").decode()


def abo(endpunkt="https://fcm.googleapis.com/fcm/send/abc") -> Abo:
    return pruefe_abo(endpunkt, P256DH, AUTH)


@pytest.mark.parametrize(
    "endpunkt",
    [
        "https://web.push.apple.com/QGhp-abc",
        "https://fcm.googleapis.com/fcm/send/abc:def",
        "https://updates.push.services.mozilla.com/wpush/v2/abc",
        "https://wns2-par02p.notify.windows.com/w/?token=abc",
    ],
)
def test_erlaubte_dienste(endpunkt):
    assert pruefe_abo(endpunkt, P256DH, AUTH).endpunkt == endpunkt


@pytest.mark.parametrize(
    "endpunkt",
    [
        "http://fcm.googleapis.com/fcm/send/abc",
        "https://127.0.0.1/push",
        "https://evil.example/push.apple.com",
        "https://x.push.apple.com.evil.example/abc",
        "https://evilpush.apple.com/abc",
        "https://fcm.googleapis.com:8443/fcm/send/abc",
        "https://nutzer:pw@fcm.googleapis.com/fcm/send/abc",
        "https://fcm.googleapis.com/" + "a" * 1000,
        "",
        "kein-url",
        "https://fcm.googleapis.com/fcm/send/a b",
        "https://fcm.googleapis.com/fcm/send/a\tb",
        "https://fcm.googleapis.com/fcm/send/a\x7f",
        "https://fcm.googleapis.com/fcm/send/ä",
    ],
)
def test_abgelehnte_adressen(endpunkt):
    with pytest.raises(ValueError):
        pruefe_abo(endpunkt, P256DH, AUTH)


@pytest.mark.parametrize(
    "p256dh,auth",
    [
        (base64.urlsafe_b64encode(_PUNKT[:64]).decode(), AUTH),
        (base64.urlsafe_b64encode(b"\x04" + b"\x01" * 64).decode(), AUTH),
        (P256DH, base64.urlsafe_b64encode(b"\x02" * 15).decode()),
        (P256DH, "!!kein base64!!"),
        ("", AUTH),
    ],
)
def test_abgelehnte_schluessel(p256dh, auth):
    with pytest.raises(ValueError):
        pruefe_abo("https://fcm.googleapis.com/fcm/send/abc", p256dh, auth)


def test_speichern_und_lesen(db, lehrperson):
    speichere_abo(db, lehrperson["id"], abo())
    zeilen = alle_abos(db)
    assert [z["endpunkt"] for z in zeilen] == ["https://fcm.googleapis.com/fcm/send/abc"]
    assert zeilen[0]["p256dh"] == P256DH and zeilen[0]["auth"] == AUTH
    assert anzahl_abos(db) == 1


def test_gleiches_geraet_neues_konto(db, lehrperson, zweite_lehrperson):
    speichere_abo(db, lehrperson["id"], abo())
    speichere_abo(db, zweite_lehrperson["id"], abo())
    assert anzahl_abos(db) == 1
    assert not loesche_abo(db, lehrperson["id"], abo().endpunkt)
    assert loesche_abo(db, zweite_lehrperson["id"], abo().endpunkt)
    assert anzahl_abos(db) == 0


def test_fremdes_abo_nicht_loeschbar(db, lehrperson, zweite_lehrperson):
    speichere_abo(db, lehrperson["id"], abo())
    assert loesche_abo(db, zweite_lehrperson["id"], abo().endpunkt) is False
    assert anzahl_abos(db) == 1


def test_obergrenze_zehn(db, lehrperson):
    for i in range(11):
        speichere_abo(db, lehrperson["id"], abo(f"https://fcm.googleapis.com/fcm/send/{i}"))
    endpunkte = {z["endpunkt"] for z in alle_abos(db)}
    assert len(endpunkte) == 10
    assert "https://fcm.googleapis.com/fcm/send/0" not in endpunkte


def test_entferne_abo(db, lehrperson):
    speichere_abo(db, lehrperson["id"], abo())
    entferne_abo(db, alle_abos(db)[0]["id"])
    assert anzahl_abos(db) == 0


def test_kaskade_beim_konto_loeschen(db, lehrperson, einstellungen):
    speichere_abo(db, lehrperson["id"], abo())
    loesche_konto(db, lehrperson["id"], einstellungen.aufnahmen_verzeichnis)
    assert anzahl_abos(db) == 0
