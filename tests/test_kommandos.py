import io

import pytest

from app.db import migriere, verbinde
from app.kommandos import main
from app.konten import finde_hash, passwort_stimmt


@pytest.fixture
def daten(tmp_path, monkeypatch):
    verzeichnis = tmp_path / "daten"
    monkeypatch.setenv("DATEN_VERZEICHNIS", str(verzeichnis))
    return verzeichnis


def _db(daten):
    conn = verbinde(daten / "reflexion.db")
    migriere(conn)
    return conn


def _anlegen(benutzername="projektleitung", passwort="geheim123\n"):
    return main(
        ["auftraggeberin-anlegen", "--benutzername", benutzername, "--anzeigename", "Leitung"],
        io.StringIO(passwort),
    )


def test_auftraggeberin_anlegen(daten, capsys):
    assert _anlegen() == 0
    assert "projektleitung" in capsys.readouterr().out
    konto, passwort_hash = finde_hash(_db(daten), "projektleitung")
    assert konto.rolle == "auftraggeberin"
    assert passwort_stimmt("geheim123", passwort_hash)


def test_doppelter_benutzername_exit_1(daten, capsys):
    assert _anlegen() == 0
    assert _anlegen() == 1
    assert "gibt es schon" in capsys.readouterr().err


def test_passwort_setzen_erhoeht_version(daten):
    _anlegen()
    vorher, _ = finde_hash(_db(daten), "projektleitung")
    code = main(
        ["passwort-setzen", "--benutzername", "projektleitung"], io.StringIO("neu-geheim1\n")
    )
    assert code == 0
    nachher, passwort_hash = finde_hash(_db(daten), "projektleitung")
    assert nachher.sitzungsversion == vorher.sitzungsversion + 1
    assert passwort_stimmt("neu-geheim1", passwort_hash)


def test_passwort_setzen_unbekannt_exit_1(daten, capsys):
    code = main(["passwort-setzen", "--benutzername", "niemand"], io.StringIO("geheim123\n"))
    assert code == 1
    assert capsys.readouterr().err


def test_leeres_passwort_exit_1(daten, capsys):
    assert _anlegen(passwort="\n") == 1
    assert capsys.readouterr().err
    assert finde_hash(_db(daten), "projektleitung") is None
