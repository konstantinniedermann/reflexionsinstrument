from datetime import date

import pytest

from app.ansicht import Ansicht, fuer_gast, fuer_lehrperson, fuer_vorschau
from app.konten import Konto

TAG = date(2026, 11, 30)


def test_konto_nur_bei_lehrperson():
    for args in [
        ("gast", TAG, "/gast", 1),
        ("vorschau", TAG, "/x", 2),
        ("lehrperson", TAG, "/lehrperson", None),
    ]:
        with pytest.raises(ValueError):
            Ansicht(*args)


def test_fuer_lehrperson():
    konto = Konto(id=7, anzeigename="A", benutzername="a", rolle="lehrperson", sitzungsversion=1)
    ansicht = fuer_lehrperson(konto, TAG)
    assert ansicht.speichert and ansicht.zeigt_eintraege
    assert ansicht.url("/runden/3") == "/lehrperson/runden/3"
    assert ansicht.konto_id == 7
    assert ansicht.stichtag == TAG
    assert ansicht.ausgang is None


def test_fuer_gast():
    ansicht = fuer_gast(TAG, "Band", ("Anmelden", "/"))
    assert ansicht.basis == "/gast"
    assert ansicht.konto_id is None
    assert not ansicht.speichert
    assert ansicht.band == "Band"
    assert ansicht.ausgang == ("Anmelden", "/")


def test_fuer_vorschau():
    ansicht = fuer_vorschau(date(2026, 12, 7), "B", ("Vorschau beenden", "/verwaltung/vorschau"))
    assert ansicht.url("/info") == "/verwaltung/vorschau/2026-12-07/info"
    assert not ansicht.zeigt_eintraege
