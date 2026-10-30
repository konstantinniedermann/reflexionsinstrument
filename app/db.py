"""SQLite-Anbindung: Verbindung, Migrationen und FastAPI-Dependency."""

import sqlite3
from collections.abc import Iterator
from pathlib import Path

from fastapi import Request

MIGRATIONEN = Path(__file__).parent / "migrationen"


def verbinde(db_pfad: Path) -> sqlite3.Connection:
    # isolation_level=None: Transaktionen steuert der Code selbst.
    # check_same_thread=False: FastAPI fuehrt Dependency-Aufbau, Route und Abbau in
    # verschiedenen Threads aus. Sicher, weil jede Anfrage ihre eigene Verbindung hat
    # und diese nie gleichzeitig von mehreren Threads genutzt wird.
    conn = sqlite3.connect(db_pfad, isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    return conn


def _version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migriere(conn: sqlite3.Connection, verzeichnis: Path = MIGRATIONEN) -> int:
    """Fuehrt alle NNN_*.sql mit NNN > user_version aufsteigend aus."""
    dateien = sorted((int(p.name.split("_", 1)[0]), p) for p in verzeichnis.glob("[0-9]*_*.sql"))
    for nummer, pfad in dateien:
        # Neu lesen: ein zweiter Prozess koennte schon migriert haben.
        if nummer <= _version(conn):
            continue
        sql = pfad.read_text(encoding="utf-8")
        try:
            # executescript committet selbst, darum die Transaktion im Skript.
            conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {nummer};\nCOMMIT;")
        except Exception:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
    return _version(conn)


def hole_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = verbinde(request.app.state.einstellungen.db_pfad)
    try:
        yield conn
    finally:
        conn.close()
