"""Fachlogik der Eingabemaske: Grundlagen (Titel, erster Tag, Begruessung) und Zaehler."""

import sqlite3
from datetime import date, timedelta

from app.db import transaktion
from app.eingaben import (
    LAENGE_BESCHRIFTUNG,
    LAENGE_KURZ,
    LAENGE_TITEL,
    LAENGE_TITEL_INSTRUMENT,
    Gesperrt,
    InhaltFehler,
    datum_feld,
    kurzer_text,
    langer_text,
)
from app.texte import speichere_text
from app.zeit import lies_datum

STANDARD_TITEL = "Reflexionsinstrument"

SKALA_MIN = 1
SKALA_MAX = 5
TYPEN = ("freitext", "skala")

# art -> (Tabelle, Spalte der Gruppe oder None). Namen stehen fest im Code, nie aus Eingaben.
GEORDNET = {
    "info": ("info_abschnitte", None),
    "frage": ("fragen", "runde_id"),
    "leitfrage": ("leitfragen", None),
}


def _lies_einstellung(db: sqlite3.Connection, schluessel: str) -> str | None:
    zeile = db.execute(
        "SELECT wert FROM einstellungen WHERE schluessel = ?", (schluessel,)
    ).fetchone()
    return None if zeile is None else zeile["wert"]


def lies_titel(db: sqlite3.Connection) -> str:
    return _lies_einstellung(db, "titel") or STANDARD_TITEL


def lies_projektstart(db: sqlite3.Connection) -> date | None:
    wert = _lies_einstellung(db, "projektstart")
    return None if wert is None else lies_datum(wert)


def _setze_einstellung(db: sqlite3.Connection, schluessel: str, wert: str | None) -> None:
    if wert is None:
        db.execute("DELETE FROM einstellungen WHERE schluessel = ?", (schluessel,))
    else:
        db.execute(
            "INSERT INTO einstellungen (schluessel, wert) VALUES (?, ?) "
            "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
            (schluessel, wert),
        )


def speichere_allgemein(
    db: sqlite3.Connection, titel: str, begruessung: str, projektstart: str
) -> None:
    with transaktion(db):
        sauberer_titel = kurzer_text(
            titel, "titel", LAENGE_TITEL_INSTRUMENT, "Bitte einen Titel eingeben."
        )
        try:
            speichere_text(db, "begruessung", begruessung)
        except InhaltFehler as fehler:
            raise InhaltFehler("begruessung", fehler.meldung) from fehler
        start = datum_feld(projektstart, "projektstart", pflicht=False)
        _setze_einstellung(db, "titel", sauberer_titel)
        _setze_einstellung(db, "projektstart", start)


def zaehle_inhalte(db: sqlite3.Connection) -> dict[str, int]:
    def anzahl(sql: str) -> int:
        return db.execute(sql).fetchone()[0]

    return {
        "info_abschnitte": anzahl("SELECT COUNT(*) FROM info_abschnitte"),
        "runden": anzahl("SELECT COUNT(*) FROM runden"),
        "fragen": anzahl("SELECT COUNT(*) FROM fragen"),
        "runden_ohne_fragen": anzahl(
            "SELECT COUNT(*) FROM runden r "
            "WHERE NOT EXISTS (SELECT 1 FROM fragen f WHERE f.runde_id = r.id)"
        ),
        "leitfragen": anzahl("SELECT COUNT(*) FROM leitfragen"),
        "impulse": anzahl("SELECT COUNT(*) FROM impulse"),
    }


# ---------- Runden ----------

_RUNDEN_SQL = (
    "SELECT r.id, r.titel, r.fallbeispiel, r.freischaltdatum, "
    "(SELECT COUNT(*) FROM fragen f WHERE f.runde_id = r.id) AS anzahl_fragen FROM runden r"
)


def runden(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(f"{_RUNDEN_SQL} ORDER BY r.freischaltdatum, r.id").fetchall()


def runde(db: sqlite3.Connection, runde_id: int) -> sqlite3.Row | None:
    return db.execute(f"{_RUNDEN_SQL} WHERE r.id = ?", (runde_id,)).fetchone()


def datum_vorschlag_runde(db: sqlite3.Connection) -> date | None:
    """Eine Woche nach der letzten Runde, ohne Runden der erste Tag, sonst nichts."""
    letzte = db.execute("SELECT MAX(freischaltdatum) FROM runden").fetchone()[0]
    if letzte is not None:
        return date.fromisoformat(letzte) + timedelta(days=7)
    return lies_projektstart(db)


def _pruefe_runde(titel: str, fallbeispiel: str, freischaltdatum: str):
    sauberer_titel = kurzer_text(titel, "titel", LAENGE_TITEL, "Bitte einen Titel eingeben.")
    text = langer_text(fallbeispiel, "fallbeispiel", None)
    datum = datum_feld(freischaltdatum, "freischaltdatum", pflicht=True)
    return sauberer_titel, text, datum


def lege_runde_an(
    db: sqlite3.Connection, titel: str, fallbeispiel: str, freischaltdatum: str
) -> int:
    werte = _pruefe_runde(titel, fallbeispiel, freischaltdatum)
    return db.execute(
        "INSERT INTO runden (titel, fallbeispiel, freischaltdatum) VALUES (?, ?, ?)", werte
    ).lastrowid


def aendere_runde(
    db: sqlite3.Connection, runde_id: int, titel: str, fallbeispiel: str, freischaltdatum: str
) -> None:
    werte = _pruefe_runde(titel, fallbeispiel, freischaltdatum)
    aenderungen = db.execute(
        "UPDATE runden SET titel = ?, fallbeispiel = ?, freischaltdatum = ? WHERE id = ?",
        (*werte, runde_id),
    ).rowcount
    if aenderungen == 0:
        raise LookupError(runde_id)


def _antworten_runde(db: sqlite3.Connection, runde_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM antworten a JOIN fragen f ON f.id = a.frage_id WHERE f.runde_id = ?",
        (runde_id,),
    ).fetchone()[0]


def _antworten_frage(db: sqlite3.Connection, frage_id: int) -> int:
    return db.execute("SELECT COUNT(*) FROM antworten WHERE frage_id = ?", (frage_id,)).fetchone()[
        0
    ]


def zaehle_antworten_runde(db: sqlite3.Connection, runde_id: int) -> int:
    return _antworten_runde(db, runde_id)


def zaehle_antworten_frage(db: sqlite3.Connection, frage_id: int) -> int:
    return _antworten_frage(db, frage_id)


def loesche_runde(db: sqlite3.Connection, runde_id: int) -> int:
    """Loescht die Runde samt Fragen; gibt die Zahl der Fragen zurueck. Mit Antworten: Gesperrt."""
    with transaktion(db):
        if runde(db, runde_id) is None:
            raise LookupError(runde_id)
        anzahl = zaehle_antworten_runde(db, runde_id)
        if anzahl:
            raise Gesperrt(anzahl)
        fragen_anzahl = len(fragen(db, runde_id))
        try:
            db.execute("DELETE FROM runden WHERE id = ?", (runde_id,))
        except sqlite3.IntegrityError as fehler:
            # Sicherheitsnetz: die Datenbank verweigert, was die Pruefung uebersehen hat.
            raise Gesperrt(max(_antworten_runde(db, runde_id), 1)) from fehler
        return fragen_anzahl


# ---------- Fragen ----------

_FRAGEN_SQL = (
    "SELECT f.*, (SELECT COUNT(*) FROM antworten a WHERE a.frage_id = f.id) AS anzahl_antworten "
    "FROM fragen f"
)


def fragen(db: sqlite3.Connection, runde_id: int) -> list[sqlite3.Row]:
    return db.execute(
        f"{_FRAGEN_SQL} WHERE f.runde_id = ? ORDER BY f.reihenfolge, f.id", (runde_id,)
    ).fetchall()


def frage(db: sqlite3.Connection, frage_id: int) -> sqlite3.Row | None:
    return db.execute(f"{_FRAGEN_SQL} WHERE f.id = ?", (frage_id,)).fetchone()


def _pruefe_frage(typ: str, text: str, skala_min_text: str, skala_max_text: str):
    if typ not in TYPEN:
        raise InhaltFehler("typ", "Bitte die Art der Antwort wählen.")
    sauberer_text = kurzer_text(text, "text", LAENGE_KURZ, "Bitte eine Frage eingeben.")
    if typ != "skala":
        return typ, sauberer_text, None, None
    meldung = "Für die Skala braucht es beide Beschriftungen."
    kleinste = kurzer_text(skala_min_text, "skala_min_text", LAENGE_BESCHRIFTUNG, meldung)
    groesste = kurzer_text(skala_max_text, "skala_max_text", LAENGE_BESCHRIFTUNG, meldung)
    return typ, sauberer_text, kleinste, groesste


def lege_frage_an(
    db: sqlite3.Connection,
    runde_id: int,
    typ: str,
    text: str,
    skala_min_text: str,
    skala_max_text: str,
) -> int:
    werte = _pruefe_frage(typ, text, skala_min_text, skala_max_text)
    try:
        # Eine Anweisung: die naechste Nummer wird im selben Schritt gelesen und geschrieben.
        return db.execute(
            "INSERT INTO fragen (runde_id, typ, text, skala_min_text, skala_max_text, reihenfolge) "
            "SELECT ?, ?, ?, ?, ?, coalesce(max(reihenfolge), 0) + 1 FROM fragen "
            "WHERE runde_id = ?",
            (runde_id, *werte, runde_id),
        ).lastrowid
    except sqlite3.IntegrityError as fehler:
        raise LookupError(runde_id) from fehler


def aendere_frage(
    db: sqlite3.Connection,
    frage_id: int,
    typ: str,
    text: str,
    skala_min_text: str,
    skala_max_text: str,
) -> None:
    werte = _pruefe_frage(typ, text, skala_min_text, skala_max_text)
    with transaktion(db):
        bisher = frage(db, frage_id)
        if bisher is None:
            raise LookupError(frage_id)
        if bisher["typ"] != typ and bisher["anzahl_antworten"]:
            raise InhaltFehler(
                "typ",
                "Die Art lässt sich nicht mehr ändern, weil die Frage schon beantwortet wurde. "
                "Lege bei Bedarf eine neue Frage an.",
            )
        db.execute(
            "UPDATE fragen SET typ = ?, text = ?, skala_min_text = ?, skala_max_text = ? "
            "WHERE id = ?",
            (*werte, frage_id),
        )


def loesche_frage(db: sqlite3.Connection, frage_id: int) -> None:
    """Loescht eine unbeantwortete Frage und nummeriert die Runde neu; sonst Gesperrt."""
    with transaktion(db):
        bisher = frage(db, frage_id)
        if bisher is None:
            raise LookupError(frage_id)
        anzahl = zaehle_antworten_frage(db, frage_id)
        if anzahl:
            raise Gesperrt(anzahl)
        try:
            db.execute("DELETE FROM fragen WHERE id = ?", (frage_id,))
        except sqlite3.IntegrityError as fehler:
            # Sicherheitsnetz: die Datenbank verweigert, was die Pruefung uebersehen hat.
            raise Gesperrt(max(_antworten_frage(db, frage_id), 1)) from fehler
        _nummeriere(db, "frage", bisher["runde_id"])


# ---------- Reihenfolge ----------


def _gruppe_ids(db: sqlite3.Connection, art: str, gruppe: int | None) -> list[int]:
    tabelle, spalte = GEORDNET[art]
    if spalte is None:
        sql = f"SELECT id FROM {tabelle} ORDER BY reihenfolge, id"
        zeilen = db.execute(sql).fetchall()
    else:
        sql = f"SELECT id FROM {tabelle} WHERE {spalte} = ? ORDER BY reihenfolge, id"
        zeilen = db.execute(sql, (gruppe,)).fetchall()
    return [z["id"] for z in zeilen]


def _schreibe_reihenfolge(db: sqlite3.Connection, art: str, ids: list[int]) -> None:
    tabelle = GEORDNET[art][0]
    for nummer, eintrag_id in enumerate(ids, start=1):
        db.execute(f"UPDATE {tabelle} SET reihenfolge = ? WHERE id = ?", (nummer, eintrag_id))


def _nummeriere(db: sqlite3.Connection, art: str, gruppe: int | None) -> None:
    _schreibe_reihenfolge(db, art, _gruppe_ids(db, art, gruppe))


def verschiebe(db: sqlite3.Connection, art: str, eintrag_id: int, richtung: str) -> None:
    """Tauscht den Eintrag mit seinem Nachbarn; am Rand ohne Wirkung. Schreibt 1 bis n neu."""
    if richtung not in ("hoch", "runter") or art not in GEORDNET:
        raise ValueError(f"{art!r} / {richtung!r}")
    tabelle, spalte = GEORDNET[art]
    with transaktion(db):
        gruppe = None
        if spalte is not None:
            zeile = db.execute(f"SELECT {spalte} FROM {tabelle} WHERE id = ?", (eintrag_id,))
            zeile = zeile.fetchone()
            if zeile is None:
                return
            gruppe = zeile[0]
        ids = _gruppe_ids(db, art, gruppe)
        if eintrag_id in ids:
            stelle = ids.index(eintrag_id)
            nachbar = stelle - 1 if richtung == "hoch" else stelle + 1
            if 0 <= nachbar < len(ids):
                ids[stelle], ids[nachbar] = ids[nachbar], ids[stelle]
        _schreibe_reihenfolge(db, art, ids)
