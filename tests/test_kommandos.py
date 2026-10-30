import io
import json
from datetime import date
from pathlib import Path

import pytest
from testdaten import lege_antwort_an

from app.db import migriere, verbinde
from app.inhalte import zaehle_inhalte
from app.kommandos import PLATZHALTER_DATEI, main
from app.konten import finde_hash, lege_konto_an, passwort_stimmt


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


# ---------- platzhalter-laden ----------


WURZEL = Path(__file__).resolve().parent.parent


def _datei():
    return json.loads(PLATZHALTER_DATEI.read_text(encoding="utf-8"))


def _erwartet():
    d = _datei()
    return {
        "info_abschnitte": len(d["info"]),
        "runden": len(d["runden"]),
        "fragen": sum(len(r["fragen"]) for r in d["runden"]),
        "runden_ohne_fragen": 0,
        "leitfragen": len(d["leitfragen"]),
        "impulse": len(d["impulse"]),
    }


def _laden(*zusatz):
    return main(["platzhalter-laden", *zusatz])


def test_platzhalter_laden(daten, capsys):
    assert _laden("--projektstart", "2026-11-23") == 0
    e = _erwartet()
    assert (
        capsys.readouterr().out.strip()
        == f"Platzhalter geladen: {e['info_abschnitte']} Abschnitte, {e['runden']} Runden, "
        f"{e['fragen']} Fragen, {e['leitfragen']} Leitfragen, {e['impulse']} Impulse."
    )
    db = _db(daten)
    assert zaehle_inhalte(db) == e
    daten_runden = db.execute("SELECT * FROM runden ORDER BY freischaltdatum").fetchall()
    assert daten_runden[0]["freischaltdatum"] == "2026-11-23"
    assert daten_runden[3]["freischaltdatum"] == "2026-12-14"
    assert daten_runden[3]["fallbeispiel"] is None
    start = db.execute("SELECT wert FROM einstellungen WHERE schluessel = 'projektstart'")
    assert start.fetchone()["wert"] == "2026-11-23"
    schluessel = [r["schluessel"] for r in db.execute("SELECT schluessel FROM texte")]
    assert schluessel == ["begruessung"]


def test_platzhalter_standard_heute(daten, monkeypatch):
    monkeypatch.setattr("app.zeit.heute", lambda: date(2026, 12, 1))
    assert _laden() == 0
    start = _db(daten).execute("SELECT wert FROM einstellungen WHERE schluessel = 'projektstart'")
    assert start.fetchone()["wert"] == "2026-12-01"


def test_platzhalter_verweigert_in_produktion(daten, monkeypatch, capsys):
    monkeypatch.setenv("PRODUKTION", "1")
    assert _laden() == 1
    assert "in Produktion nicht erlaubt" in capsys.readouterr().err
    assert not (daten / "reflexion.db").exists()


def test_platzhalter_verweigert_bei_vorhandenen_inhalten(daten, capsys):
    assert _laden("--projektstart", "2026-11-23") == 0
    capsys.readouterr()
    assert _laden("--projektstart", "2026-11-23") == 1
    assert "--ersetzen" in capsys.readouterr().err
    assert zaehle_inhalte(_db(daten)) == _erwartet()


def test_platzhalter_ersetzen(daten):
    assert _laden("--projektstart", "2026-11-23") == 0
    db = _db(daten)
    db.execute("INSERT INTO info_abschnitte (titel, inhalt, reihenfolge) VALUES ('X', 'Y', 99)")
    assert zaehle_inhalte(db)["info_abschnitte"] == _erwartet()["info_abschnitte"] + 1
    db.close()
    assert _laden("--projektstart", "2026-11-23", "--ersetzen") == 0
    assert zaehle_inhalte(_db(daten)) == _erwartet()


def test_platzhalter_ersetzen_mit_antworten_scheitert(daten, capsys):
    assert _laden("--projektstart", "2026-11-23") == 0
    db = _db(daten)
    frage_id = db.execute("SELECT id FROM fragen LIMIT 1").fetchone()["id"]
    konto = lege_konto_an(db, "Lehrperson", "lp.test", "geheim-pass-1")
    lege_antwort_an(db, frage_id, konto.id)
    db.close()
    capsys.readouterr()
    assert _laden("--projektstart", "2026-11-23", "--ersetzen") == 1
    assert "Antworten von Lehrpersonen" in capsys.readouterr().err
    assert zaehle_inhalte(_db(daten)) == _erwartet()


class _KeineEingabe:
    def readline(self):
        raise AssertionError("Passwort gelesen")


def test_platzhalter_liest_kein_passwort(daten):
    assert main(["platzhalter-laden", "--projektstart", "2026-11-23"], _KeineEingabe()) == 0


def test_platzhalter_ungueltiges_datum(daten, capsys):
    assert _laden("--projektstart", "23.11.2026") == 1
    assert "JJJJ-MM-TT" in capsys.readouterr().err


def test_platzhalter_datei_zeigt_formatierung():
    d = _datei()
    assert any("\n- " in a["inhalt"] and "**" in a["inhalt"] for a in d["info"])
    assert any(r["fallbeispiel"] is None for r in d["runden"])
    arten = {f["typ"] for r in d["runden"] for f in r["fragen"]}
    assert arten == {"freitext", "skala"}


def test_dockerignore_laesst_tests_draussen():
    zeilen = (WURZEL / ".dockerignore").read_text().splitlines()
    assert "*" in zeilen and "!app/" in zeilen
    assert not any(z.startswith("!tests") for z in zeilen)
