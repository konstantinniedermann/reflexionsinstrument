import pytest
from fastapi.testclient import TestClient

from app.config import Einstellungen
from app.main import erstelle_app


@pytest.fixture
def einstellungen(tmp_path):
    return Einstellungen(
        daten_verzeichnis=tmp_path / "daten",
        geheimer_schluessel="test-schluessel",
        produktion=False,
    )


@pytest.fixture
def client(einstellungen):
    with TestClient(erstelle_app(einstellungen)) as c:
        yield c


@pytest.fixture(autouse=True)
def schnelles_bcrypt(monkeypatch):
    monkeypatch.setattr("app.konten.BCRYPT_RUNDEN", 4)
