import sqlite3

import pytest
from fastapi.routing import APIRoute, iter_route_contexts

from app.db import verbinde
from app.main import erstelle_app
from app.routen.ohne_speichern import hole_db_lesend


def test_hole_db_lesend_verbietet_schreiben(einstellungen, client):
    conn = verbinde(einstellungen.db_pfad)
    try:
        assert hole_db_lesend(conn) is conn
        assert conn.execute("SELECT COUNT(*) FROM runden").fetchone()[0] == 0
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO einstellungen (schluessel, wert) VALUES ('x', 'y')")
    finally:
        conn.close()
    neu = verbinde(einstellungen.db_pfad)
    try:
        assert neu.execute("SELECT 1 FROM einstellungen WHERE schluessel = 'x'").fetchone() is None
    finally:
        neu.close()


def _ruft(dependant, ziel) -> bool:
    if dependant.call is ziel:
        return True
    return any(_ruft(d, ziel) for d in dependant.dependencies)


def test_seiten_nutzen_lesende_verbindung(einstellungen):
    app = erstelle_app(einstellungen)
    routen = [
        r
        for r in iter_route_contexts(app.routes)
        if isinstance(r.original_route, APIRoute)
        and r.path.startswith(("/gast", "/verwaltung/vorschau"))
    ]
    assert routen
    for r in routen:
        assert _ruft(r.original_route.dependant, hole_db_lesend), r.path
