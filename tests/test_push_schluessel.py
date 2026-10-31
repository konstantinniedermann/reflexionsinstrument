"""VAPID-Schlüssel für Benachrichtigungen (#37)."""

import base64

import pytest

from app.kommandos import main
from app.push import erzeuge_vapid_schluessel, lade_vapid, oeffentlicher_schluessel


def _b64(wert: str) -> bytes:
    return base64.urlsafe_b64decode(wert + "=" * (-len(wert) % 4))


def test_schluessel_rundreise():
    wert = erzeuge_vapid_schluessel()
    assert "\n" not in wert
    punkt = _b64(oeffentlicher_schluessel(lade_vapid(wert)))
    assert len(punkt) == 65
    assert punkt[0] == 4


def test_oeffentlicher_schluessel_ohne_auffuellung():
    assert "=" not in oeffentlicher_schluessel(lade_vapid(erzeuge_vapid_schluessel()))


def test_kaputter_schluessel():
    with pytest.raises(ValueError):
        lade_vapid("abc")


def test_kommando_vapid(capsys):
    assert main(["vapid-schluessel"]) == 0
    ausgabe = capsys.readouterr().out
    assert "fly secrets set VAPID_SCHLUESSEL=" in ausgabe
    wert = ausgabe.split("VAPID_SCHLUESSEL=", 1)[1].split()[0]
    lade_vapid(wert)
