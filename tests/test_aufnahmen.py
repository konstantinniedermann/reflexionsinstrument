import logging
import os
import shutil
import stat
from collections import namedtuple
from io import BytesIO

import pytest

from app import aufnahmen
from app.aufnahmen import (
    DATEINAME,
    RESERVE_BYTES,
    AufnahmeFehler,
    erkenne_format,
    lies_dauer,
    raeume_waisen,
    schreibe_datei,
)

WEBM = b"\x1aE\xdf\xa3" + bytes(60)
MP4 = b"\x00\x00\x00\x18ftypM4A " + bytes(52)
OGG = b"OggS" + bytes(60)


@pytest.mark.parametrize(
    ("anfang", "erwartet"),
    [
        (WEBM, ("audio/webm", ".webm")),
        (MP4, ("audio/mp4", ".m4a")),
        (OGG, ("audio/ogg", ".ogg")),
        (b"", None),
        (b"\x1aE\xdf", None),
        (b"<html><script>", None),
        (b"ID3\x04\x00", None),
        (b"RIFF\x00\x00\x00\x00WAVE", None),
        (b"\x89PNG\r\n\x1a\n", None),
    ],
)
def test_erkenne_format(anfang, erwartet):
    assert erkenne_format(anfang) == erwartet


def test_lies_dauer():
    assert lies_dauer("") is None
    assert lies_dauer("0") == 0
    assert lies_dauer("42") == 42
    assert lies_dauer("610") == 610
    for wert in ("abc", "-1", "611", "99999999999999999999", " 5", "5.0", "٣"):
        with pytest.raises(AufnahmeFehler) as fehler:
            lies_dauer(wert)
        assert fehler.value.status == 400


def test_schreibe_datei(tmp_path):
    d = schreibe_datei(BytesIO(MP4), tmp_path)
    assert DATEINAME.fullmatch(d.name)
    assert d.name.endswith(".m4a")
    assert d.mime_typ == "audio/mp4"
    assert d.groesse == len(MP4)
    pfad = tmp_path / d.name
    assert pfad.read_bytes() == MP4
    assert stat.S_IMODE(pfad.stat().st_mode) == 0o600
    assert list(tmp_path.iterdir()) == [pfad]
    zweite = schreibe_datei(BytesIO(MP4), tmp_path)
    assert zweite.name != d.name


def test_schreibe_datei_abgewiesen(tmp_path, monkeypatch):
    with pytest.raises(AufnahmeFehler) as fehler:
        schreibe_datei(BytesIO(b""), tmp_path)
    assert fehler.value.status == 400
    with pytest.raises(AufnahmeFehler) as fehler:
        schreibe_datei(BytesIO(b"<html>" + bytes(60)), tmp_path)
    assert fehler.value.status == 400
    monkeypatch.setattr(aufnahmen, "MAX_BYTES", 100)
    with pytest.raises(AufnahmeFehler) as fehler:
        schreibe_datei(BytesIO(WEBM + bytes(100)), tmp_path)
    assert fehler.value.status == 413
    assert list(tmp_path.iterdir()) == []


def test_speicher_knapp(tmp_path, monkeypatch, caplog):
    Nutzung = namedtuple("Nutzung", "total used free")
    monkeypatch.setattr(
        shutil, "disk_usage", lambda _p: Nutzung(0, 0, RESERVE_BYTES + len(WEBM) - 1)
    )
    with caplog.at_level(logging.INFO), pytest.raises(AufnahmeFehler) as fehler:
        schreibe_datei(BytesIO(WEBM), tmp_path)
    assert fehler.value.status == 503
    assert list(tmp_path.iterdir()) == []
    assert [r.getMessage() for r in caplog.records] == ["Aufnahme abgelehnt: Speicherplatz knapp"]


def test_fehler_beim_umbenennen(tmp_path, monkeypatch):
    def kaputt(*_args, **_kwargs):
        raise OSError("kaputt")

    monkeypatch.setattr(os, "replace", kaputt)
    with pytest.raises(OSError, match="kaputt"):
        schreibe_datei(BytesIO(WEBM), tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_raeume_waisen(db, lehrperson, tmp_path):
    ordner = tmp_path / "ordner"
    ordner.mkdir()
    ausserhalb = tmp_path / "ausserhalb.webm"
    ausserhalb.write_bytes(b"x")
    vor_zwei_stunden = 1_000_000.0
    jetzt = vor_zwei_stunden + 7200

    def anlegen(name: str, alt: bool = True):
        pfad = ordner / name
        pfad.write_bytes(b"x")
        if alt:
            os.utime(pfad, (vor_zwei_stunden, vor_zwei_stunden))
        return pfad

    verknuepft = anlegen("a" * 32 + ".webm")
    waise = anlegen("b" * 32 + ".m4a")
    teil = anlegen("c" * 32 + ".ogg.teil")
    notiz = anlegen("notiz.txt")
    datenbank = anlegen("reflexion.db")
    jung = anlegen("d" * 32 + ".webm", alt=False)
    os.utime(jung, (jetzt, jetzt))
    unterordner = ordner / ("e" * 32 + ".webm")
    unterordner.mkdir()
    link = ordner / ("f" * 32 + ".webm")
    link.symlink_to(ausserhalb)
    db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes)"
        " VALUES (?, ?, 'audio/webm', 1)",
        (lehrperson["id"], verknuepft.name),
    )
    db.commit()

    assert raeume_waisen(db, ordner, jetzt=jetzt) == 2
    assert sorted(p.name for p in ordner.iterdir()) == sorted(
        p.name for p in (verknuepft, notiz, datenbank, jung, unterordner, link)
    )
    assert not waise.exists()
    assert not teil.exists()
    assert ausserhalb.exists()
