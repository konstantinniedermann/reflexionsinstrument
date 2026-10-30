import logging
from pathlib import Path

from app.aufnahmen import aufnahme_pfad, loesche_dateien

GUELTIG = "0" * 32 + ".webm"


def test_aufnahme_pfad_muster(tmp_path):
    for name in ("../x.webm", "a.webm", "0" * 32 + ".mp3", "A" * 32 + ".webm", GUELTIG + "/.."):
        assert aufnahme_pfad(tmp_path, name) is None
    name = "0" * 32 + ".m4a"
    assert aufnahme_pfad(tmp_path, name) == tmp_path / name


def test_loesche_dateien(tmp_path):
    (tmp_path / "a.webm").write_bytes(b"x")
    (tmp_path / GUELTIG).write_bytes(b"x")
    loesche_dateien(tmp_path, ["a.webm", GUELTIG, "f" * 32 + ".ogg"])
    assert (tmp_path / "a.webm").exists()
    assert not (tmp_path / GUELTIG).exists()


def test_loesche_dateien_fehler_geloggt(tmp_path, monkeypatch, caplog):
    (tmp_path / GUELTIG).write_bytes(b"x")

    def verweigert(self, *args, **kwargs):
        raise PermissionError("nein")

    monkeypatch.setattr(Path, "unlink", verweigert)
    with caplog.at_level(logging.WARNING):
        loesche_dateien(tmp_path, [GUELTIG])
    assert len(caplog.records) == 1
    assert GUELTIG not in caplog.text
    assert "0" * 32 not in caplog.text
