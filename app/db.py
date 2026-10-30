"""SQLite-Anbindung: Verbindung, Migrationen und FastAPI-Dependency."""

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager, suppress
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
    # Geloeschte Eintraege werden in der Datei ueberschrieben, nicht nur als frei markiert
    # (docs/loeschkonzept.md).
    conn.execute("PRAGMA secure_delete = ON")
    return conn


def _version(conn: sqlite3.Connection) -> int:
    return conn.execute("PRAGMA user_version").fetchone()[0]


def migriere(conn: sqlite3.Connection, verzeichnis: Path = MIGRATIONEN) -> int:
    """Fuehrt alle NNN_*.sql mit NNN > user_version aufsteigend aus."""
    dateien = sorted((int(p.name.split("_", 1)[0]), p) for p in verzeichnis.glob("[0-9]*_*.sql"))
    # Fremdschluessel waehrend der Migrationen aus, sonst loest der Neuaufbau einer Tabelle
    # (neue Tabelle, kopieren, DROP, umbenennen) ON DELETE CASCADE aus und loescht Eintraege.
    # Das PRAGMA wirkt nur ausserhalb einer Transaktion.
    conn.execute("PRAGMA foreign_keys = OFF")
    try:
        for nummer, pfad in dateien:
            # Neu lesen: ein zweiter Prozess koennte schon migriert haben.
            if nummer <= _version(conn):
                continue
            _fuehre_migration_aus(conn, nummer, pfad)
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
    return _version(conn)


def _fuehre_migration_aus(conn: sqlite3.Connection, nummer: int, pfad: Path) -> None:
    sql = pfad.read_text(encoding="utf-8")
    try:
        # executescript laesst die Transaktion offen; COMMIT erst nach der Pruefung.
        conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {nummer};")
        verletzungen = conn.execute("PRAGMA foreign_key_check").fetchall()
        if verletzungen:
            tabellen = sorted({v[0] for v in verletzungen})
            raise sqlite3.IntegrityError(
                f"Migration {pfad.name} hinterlaesst ungueltige Fremdschluessel in: "
                + ", ".join(tabellen)
            )
        conn.execute("COMMIT")
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise


def hole_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = verbinde(request.app.state.einstellungen.db_pfad)
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaktion(db: sqlite3.Connection) -> Iterator[None]:
    """Alles oder nichts. Laeuft schon eine Transaktion, entscheidet die aeussere."""
    if db.in_transaction:
        yield
        return
    db.execute("BEGIN IMMEDIATE")
    try:
        yield
        db.execute("COMMIT")
    except BaseException:
        # Auch nach gescheitertem COMMIT (z. B. SQLITE_BUSY) ist die Transaktion noch offen.
        # Scheitert das ROLLBACK, bleibt die urspruengliche Ausnahme sichtbar.
        if db.in_transaction:
            with suppress(sqlite3.Error):
                db.execute("ROLLBACK")
        raise
