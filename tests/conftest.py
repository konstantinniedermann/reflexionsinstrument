import pytest

from app.config import Einstellungen


@pytest.fixture
def einstellungen(tmp_path):
    return Einstellungen(
        daten_verzeichnis=tmp_path / "daten",
        geheimer_schluessel="test-schluessel",
        produktion=False,
    )
