from pathlib import Path

import pytest

from app.config import lade_einstellungen


def test_standardwerte_ohne_umgebung():
    with pytest.warns(UserWarning):
        e = lade_einstellungen({})
    assert e.daten_verzeichnis == Path(".daten")
    assert e.produktion is False
    assert e.geheimer_schluessel == "nur-fuer-entwicklung"


def test_pfade_abgeleitet():
    with pytest.warns(UserWarning):
        e = lade_einstellungen({})
    assert e.db_pfad.name == "reflexion.db"
    assert e.aufnahmen_verzeichnis.name == "aufnahmen"
    assert e.db_pfad.parent == e.daten_verzeichnis
    assert e.aufnahmen_verzeichnis.parent == e.daten_verzeichnis


def test_produktion_ohne_schluessel_schlaegt_fehl():
    with pytest.raises(RuntimeError):
        lade_einstellungen({"PRODUKTION": "1"})


def test_produktion_mit_leerem_schluessel_schlaegt_fehl():
    with pytest.raises(RuntimeError):
        lade_einstellungen({"PRODUKTION": "1", "GEHEIMER_SCHLUESSEL": ""})


def test_produktion_mit_schluessel():
    e = lade_einstellungen(
        {"PRODUKTION": "1", "GEHEIMER_SCHLUESSEL": "x", "DATEN_VERZEICHNIS": "/data"}
    )
    assert e.produktion is True
    assert e.daten_verzeichnis == Path("/data")


def test_produktion_nur_bei_eins():
    e = lade_einstellungen({"PRODUKTION": "true", "GEHEIMER_SCHLUESSEL": "x"})
    assert e.produktion is False
