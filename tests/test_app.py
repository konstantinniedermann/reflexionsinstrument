import sqlite3
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.db import hole_db
from app.main import erstelle_app


def test_start_legt_datenverzeichnis_an(einstellungen):
    assert not einstellungen.daten_verzeichnis.exists()
    with TestClient(erstelle_app(einstellungen)):
        pass
    assert einstellungen.daten_verzeichnis.is_dir()
    assert einstellungen.aufnahmen_verzeichnis.is_dir()
    conn = sqlite3.connect(einstellungen.db_pfad)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 1
    conn.close()


def test_healthz(client):
    antwort = client.get("/healthz")
    assert antwort.status_code == 200
    assert antwort.json() == {"status": "ok"}


def test_healthz_unter_paralleler_last(client):
    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(lambda _: client.get("/healthz").status_code, range(40)))
    assert codes == [200] * 40


def test_healthz_fehler_gibt_503(einstellungen):
    class KaputteDb:
        def execute(self, *_):
            raise sqlite3.OperationalError("kaputt")

    app = erstelle_app(einstellungen)
    app.dependency_overrides[hole_db] = lambda: KaputteDb()
    with TestClient(app) as c:
        antwort = c.get("/healthz")
    assert antwort.status_code == 503
    assert antwort.json() == {"status": "fehler"}


def test_login_seite_rendert(client):
    antwort = client.get("/")
    assert antwort.status_code == 200
    assert "text/html" in antwort.headers["content-type"]
    assert "Reflexionsinstrument" in antwort.text
    assert 'lang="de"' in antwort.text
    assert "/static/css/style.css" in antwort.text


def test_login_seite_ohne_externe_quellen(client):
    text = client.get("/").text
    for verboten in ("http://", "https://", "<script", " style="):
        assert verboten not in text


def test_css_wird_ausgeliefert(client):
    antwort = client.get("/static/css/style.css")
    assert antwort.status_code == 200
    assert "text/css" in antwort.headers["content-type"]
    assert "--papier" in antwort.text


def test_keine_api_doku(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/openapi.json").status_code == 404
