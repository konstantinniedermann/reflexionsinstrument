from datetime import UTC, date, datetime
from pathlib import Path

from app import zeit
from app.zeit import (
    ZEITZONE,
    Zeitplan,
    datum_kurz,
    heute,
    ist_erreicht,
    lies_datum,
    woche,
    zeitplan,
)


def test_heute_winterzeit():
    assert heute(datetime(2026, 11, 22, 23, 30, tzinfo=UTC)) == date(2026, 11, 23)


def test_heute_sommerzeit():
    assert heute(datetime(2026, 10, 24, 22, 30, tzinfo=UTC)) == date(2026, 10, 25)


def test_lies_datum():
    assert lies_datum("2026-11-23") == date(2026, 11, 23)
    for text in ["20261123", "2026-11-31", "23.11.2026", "", " 2026-11-23", "2026-1-5"]:
        assert lies_datum(text) is None


def test_woche():
    start = date(2026, 11, 23)
    assert woche(start, start) == 1
    assert woche(date(2026, 11, 29), start) == 1
    assert woche(date(2026, 11, 30), start) == 2
    assert woche(date(2026, 12, 14), start) == 4
    assert woche(date(2026, 11, 22), start) is None


def test_ist_erreicht():
    assert ist_erreicht(date(2026, 11, 23), date(2026, 11, 23))
    assert not ist_erreicht(date(2026, 11, 24), date(2026, 11, 23))


def test_datum_kurz():
    assert datum_kurz(date(2026, 11, 30)) == "Mo 30.11.2026"
    assert datum_kurz(date(2026, 11, 30), mit_jahr=False) == "Mo 30.11."
    assert datum_kurz(date(2026, 11, 29)) == "So 29.11.2026"


def test_zeitplan():
    start = date(2026, 11, 23)
    assert zeitplan("2026-11-30", start, date(2026, 11, 29)) == Zeitplan(
        date(2026, 11, 30), 2, False
    )
    assert zeitplan("2026-11-30", start, date(2026, 11, 30)).sichtbar
    assert zeitplan("2026-11-30", None, date(2026, 11, 29)).woche is None


def test_zeitzone_laedt():
    assert ZEITZONE.key == "Europe/Zurich"
    assert isinstance(heute(), date)


def test_app_nutzt_heute_aus_state(client):
    assert client.app.state.heute is zeit.heute


def test_festes_heute(client, festes_heute):
    assert client.app.state.heute() == festes_heute == date(2026, 11, 30)


def test_nur_zeit_kennt_die_uhr():
    app_dir = Path(zeit.__file__).parent
    for datei in app_dir.rglob("*.py"):
        if datei.name == "zeit.py":
            continue
        text = datei.read_text(encoding="utf-8")
        assert "date.today(" not in text, datei
        assert "datetime.now(" not in text, datei


def test_hole_heute(client):
    class R:
        app = client.app

    assert zeit.hole_heute(R()) == client.app.state.heute()
