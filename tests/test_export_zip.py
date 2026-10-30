import builtins
import re
import stat
import zipfile
from datetime import date, datetime
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest
from auswertung_daten import zeile

from app.export import exportzeilen
from app.export_zip import (
    STUECK,
    TABELLE_IM_ZIP,
    ZipDatei,
    name_im_zip,
    person_ascii,
    zip_dateien,
    zip_strom,
)

START = date(2026, 11, 23)
ZUERICH = ZoneInfo("Europe/Zurich")


def _eine(projektstart=START, **abweichungen):
    return exportzeilen([zeile(**abweichungen)], projektstart)[0]


def test_person_ascii():
    assert person_ascii("Zoë Müller", 1) == "zoe-mueller"
    assert person_ascii("ÄRGER Straße", 1) == "aerger-strasse"
    assert person_ascii("../../x", 1) == "x"
    assert person_ascii("***", 7) == "lehrperson-7"
    assert len(person_ascii("a" * 60, 1)) == 30


def test_name_im_zip():
    e = _eine(erstellt="2026-11-30T17:40:00Z", aufnahme_id=17)
    assert name_im_zip(e, ".webm") == "aufnahmen/anna-beispiel_W02_2026-11-30_1840_runde_17.webm"
    e = _eine(projektstart=None, erstellt="2026-11-30T17:40:00Z", aufnahme_id=17)
    assert name_im_zip(e, ".webm") == "aufnahmen/anna-beispiel_2026-11-30_1840_runde_17.webm"


@pytest.mark.parametrize("name", ["../../x", "=HYPERLINK(1)", "<script>", "a/b\\c", "x" * 60])
def test_name_im_zip_feindlich(name):
    e = _eine(anzeigename=name, aufnahme_id=3)
    ergebnis = name_im_zip(e, ".webm")
    assert re.fullmatch(r"aufnahmen/[A-Za-z0-9_.-]+", ergebnis)
    assert ergebnis.count("/") == 1
    assert ".." not in ergebnis


def test_zip_dateien(tmp_path):
    ohne = zeile(id=1)
    mit = zeile(
        id=2,
        aufnahme_id=5,
        aufnahme_dateiname="0" * 32 + ".m4a",
        erstellt="2026-11-30T17:40:00Z",
    )
    dateien = zip_dateien(exportzeilen([ohne, mit], START), tmp_path)
    assert len(dateien) == 1
    assert dateien[0].aufnahme_id == 5
    assert dateien[0].quelle == tmp_path / ("0" * 32 + ".m4a")
    assert dateien[0].name.endswith(".m4a")
    assert dateien[0].zeitpunkt == datetime(2026, 11, 30, 18, 40, tzinfo=ZUERICH)


def test_zip_dateien_name_ohne_muster(tmp_path):
    z = zeile(aufnahme_id=5, aufnahme_dateiname="../x.webm")
    assert zip_dateien(exportzeilen([z], START), tmp_path) == []


def _datei(tmp_path, aufnahme_id, inhalt, name, anlegen=True):
    quelle = tmp_path / f"{aufnahme_id:032x}.webm"
    if anlegen:
        quelle.write_bytes(inhalt)
    zeitpunkt = datetime(2026, 11, 30, 18, 40, tzinfo=ZUERICH)
    return ZipDatei(aufnahme_id, quelle, name, zeitpunkt)


class _Tabelle:
    def __init__(self):
        self.argument = None

    def __call__(self, namen):
        self.argument = namen
        return b"kopf\r\n"


def test_zip_strom(tmp_path):
    gross = bytes(range(256)) * 12288  # 3 MB
    klein = b"0123456789"
    dateien = [
        _datei(tmp_path, 1, gross, "aufnahmen/a.webm"),
        _datei(tmp_path, 2, klein, "aufnahmen/b.webm"),
        _datei(tmp_path, 3, b"", "aufnahmen/c.webm", anlegen=False),
    ]
    tabelle = _Tabelle()
    zf = zipfile.ZipFile(BytesIO(b"".join(zip_strom(dateien, tabelle))))
    assert zf.testzip() is None
    assert zf.namelist() == ["aufnahmen/a.webm", "aufnahmen/b.webm", TABELLE_IM_ZIP]
    assert zf.read("aufnahmen/a.webm") == gross
    assert zf.read("aufnahmen/b.webm") == klein
    assert zf.read(TABELLE_IM_ZIP) == b"kopf\r\n"
    assert tabelle.argument == {1: "aufnahmen/a.webm", 2: "aufnahmen/b.webm"}


def test_zip_strom_fehlende_datei(tmp_path):
    dateien = [_datei(tmp_path, 1, b"", "aufnahmen/a.webm", anlegen=False)]
    tabelle = _Tabelle()
    zf = zipfile.ZipFile(BytesIO(b"".join(zip_strom(dateien, tabelle))))
    assert zf.testzip() is None
    assert zf.namelist() == [TABELLE_IM_ZIP]
    assert tabelle.argument == {}


def test_zip_strom_stueckgroesse(tmp_path):
    dateien = [_datei(tmp_path, 1, bytes(3 * 1024 * 1024), "aufnahmen/a.webm")]
    stuecke = list(zip_strom(dateien, _Tabelle()))
    assert max(len(s) for s in stuecke) <= STUECK + 1024
    assert len(stuecke) > 10


def test_zip_strom_metadaten(tmp_path):
    dateien = [_datei(tmp_path, 1, b"abc", "aufnahmen/a.webm")]
    zf = zipfile.ZipFile(BytesIO(b"".join(zip_strom(dateien, _Tabelle()))))
    aufnahme = zf.getinfo("aufnahmen/a.webm")
    assert aufnahme.compress_type == zipfile.ZIP_STORED
    assert aufnahme.date_time == (2026, 11, 30, 18, 40, 0)
    assert aufnahme.external_attr >> 16 == stat.S_IFREG | 0o644
    assert zf.getinfo(TABELLE_IM_ZIP).compress_type == zipfile.ZIP_DEFLATED


def test_zip_strom_lesefehler(tmp_path, monkeypatch, caplog):
    datei = _datei(tmp_path, 1, b"abc", "aufnahmen/a.webm")
    echtes_open = builtins.open

    def open_mit_fehler(pfad, *args, **kwargs):
        if str(pfad) == str(datei.quelle):
            raise PermissionError(str(pfad))
        return echtes_open(pfad, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", open_mit_fehler)
    with caplog.at_level("WARNING"), pytest.raises(PermissionError):
        b"".join(zip_strom([datei], _Tabelle()))
    assert "Gesamtexport abgebrochen" in caplog.text
    assert datei.quelle.name not in caplog.text
