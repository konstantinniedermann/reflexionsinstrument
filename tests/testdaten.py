"""Hilfen fuer Testdaten. Keine Fixtures; die Daten gehen ohne Pruefung direkt per SQL hinein.

Tests importieren das Modul (`import testdaten`), damit es keinen Namenskonflikt mit
gleichnamigen Funktionen in `app/` gibt.
"""

import secrets
from pathlib import Path

WEBM_ANFANG = b"\x1aE\xdf\xa3"


def lege_runde_an(
    db,
    titel: str = "Runde",
    freischaltdatum: str = "2026-11-23",
    fragen: tuple[tuple[str, str], ...] = (("freitext", "Frage A"), ("skala", "Frage B")),
    fallbeispiel: str | None = None,
) -> tuple[int, list[int]]:
    """Legt eine Runde mit Fragen an; Skala-Fragen bekommen die Beschriftungen wenig/viel."""
    rid = db.execute(
        "INSERT INTO runden (titel, fallbeispiel, freischaltdatum) VALUES (?, ?, ?)",
        (titel, fallbeispiel, freischaltdatum),
    ).lastrowid
    ids = []
    for nummer, (typ, text) in enumerate(fragen, start=1):
        wenig, viel = ("wenig", "viel") if typ == "skala" else (None, None)
        ids.append(
            db.execute(
                "INSERT INTO fragen (runde_id, typ, text, skala_min_text, skala_max_text, "
                "reihenfolge) VALUES (?, ?, ?, ?, ?, ?)",
                (rid, typ, text, wenig, viel, nummer),
            ).lastrowid
        )
    return rid, ids


def lege_impuls_an(db, text: str = "Impuls", sichtbar_ab: str = "2026-11-23") -> int:
    return db.execute(
        "INSERT INTO impulse (text, sichtbar_ab) VALUES (?, ?)", (text, sichtbar_ab)
    ).lastrowid


def lege_leitfrage_an(db, text: str = "Leitfrage") -> int:
    return db.execute("INSERT INTO leitfragen (text) VALUES (?)", (text,)).lastrowid


def lege_antwort_an(
    db,
    frage_id: int,
    konto_id: int,
    text: str | None = "Antwort",
    skalawert: int | None = None,
    aufnahme_id: int | None = None,
) -> int:
    return db.execute(
        "INSERT INTO antworten (frage_id, konto_id, text, skalawert, aufnahme_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (frage_id, konto_id, text, skalawert, aufnahme_id),
    ).lastrowid


def lege_eintrag_an(
    db,
    konto_id: int,
    art: str = "frei",
    text: str | None = "Text",
    impuls_id: int | None = None,
    leitfrage_id: int | None = None,
    aufnahme_id: int | None = None,
) -> int:
    """Legt einen Tagebucheintrag an; Impuls- und Leitfragetext werden aus der Quelle kopiert."""
    impuls_text = leitfrage_text = None
    if impuls_id is not None:
        impuls_text = db.execute("SELECT text FROM impulse WHERE id = ?", (impuls_id,)).fetchone()[
            0
        ]
    if leitfrage_id is not None:
        leitfrage_text = db.execute(
            "SELECT text FROM leitfragen WHERE id = ?", (leitfrage_id,)
        ).fetchone()[0]
    return db.execute(
        "INSERT INTO tagebucheintraege (konto_id, art, text, impuls_id, impuls_text, "
        "leitfrage_id, leitfrage_text, aufnahme_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (konto_id, art, text, impuls_id, impuls_text, leitfrage_id, leitfrage_text, aufnahme_id),
    ).lastrowid


def lege_aufnahme_an(db, konto_id: int, verzeichnis: Path, dauer_sekunden: int = 5) -> int:
    """Schreibt eine kleine Datei mit echtem WebM-Anfang und legt die Zeile dazu an."""
    name = secrets.token_hex(16) + ".webm"
    inhalt = WEBM_ANFANG + bytes(60)
    verzeichnis.mkdir(parents=True, exist_ok=True)
    (verzeichnis / name).write_bytes(inhalt)
    return db.execute(
        "INSERT INTO aufnahmen (konto_id, dateiname, mime_typ, groesse_bytes, dauer_sekunden) "
        "VALUES (?, ?, 'audio/webm', ?, ?)",
        (konto_id, name, len(inhalt), dauer_sekunden),
    ).lastrowid


def abzug(db) -> dict[str, list[tuple]]:
    """Alle Tabellen mit sortierten Zeilen, fuer Vergleiche wie 'Datenbank unveraendert'."""
    namen = [
        z[0]
        for z in db.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' "
            "ORDER BY name"
        )
    ]
    return {n: sorted(tuple(z) for z in db.execute(f'SELECT * FROM "{n}"')) for n in namen}
