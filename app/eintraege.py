"""Antworten und Tagebuch einer Lehrperson. Fachlogik ohne FastAPI."""

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from app import zeit
from app.aufnahmen import loesche_dateien
from app.db import transaktion
from app.eingaben import InhaltFehler, langer_text
from app.inhalte import SKALA_MAX, SKALA_MIN

Eingabe = tuple[str | None, int | None]  # (text, skalawert)


def antworten_der_runde(
    db: sqlite3.Connection, konto_id: int, runde_id: int
) -> dict[int, sqlite3.Row]:
    """Antworten des Kontos zu den Fragen der Runde, nach `frage_id`."""
    zeilen = db.execute(
        "SELECT a.*, au.dauer_sekunden AS aufnahme_dauer_sekunden FROM antworten a "
        "JOIN fragen f ON f.id = a.frage_id "
        "LEFT JOIN aufnahmen au ON au.id = a.aufnahme_id AND au.konto_id = a.konto_id "
        "WHERE a.konto_id = ? AND f.runde_id = ?",
        (konto_id, runde_id),
    ).fetchall()
    return {z["frage_id"]: z for z in zeilen}


SKALA_MELDUNG = f"Bitte einen Wert von {SKALA_MIN} bis {SKALA_MAX} wählen."
GEAENDERT_MELDUNG = "Die Frage wurde inzwischen geändert. Bitte prüfe deine Antwort."


def _lies_skala(wert: str, feld: str) -> int | None:
    if wert == "":
        return None
    # Nur die genauen Ziffernfolgen: kein int() auf beliebig langen Eingaben, kein "03".
    if wert in {str(i) for i in range(SKALA_MIN, SKALA_MAX + 1)}:
        return int(wert)
    raise InhaltFehler(feld, SKALA_MELDUNG)


def lies_runden_eingaben(
    fragen: list[sqlite3.Row], formular: Mapping[str, str]
) -> dict[int, Eingabe]:
    """Prueft die Felder `antwort_{id}` der Fragen; fehlende Felder bleiben weg."""
    ergebnis: dict[int, Eingabe] = {}
    for frage in fragen:
        feld = f"antwort_{frage['id']}"
        if feld not in formular:
            continue
        wert = formular[feld]
        if frage["typ"] == "skala":
            ergebnis[frage["id"]] = (None, _lies_skala(wert, feld))
        else:
            ergebnis[frage["id"]] = (langer_text(wert, feld, None), None)
    return ergebnis


def _pruefe_art(db: sqlite3.Connection, frage_id: int, text: str | None, skalawert: int | None):
    """Skalawert nur bei `skala`, Text nur bei `freitext` (sonst war das Formular veraltet)."""
    zeile = db.execute("SELECT typ FROM fragen WHERE id = ?", (frage_id,)).fetchone()
    typ = zeile["typ"] if zeile else None
    if (skalawert is not None and typ != "skala") or (text is not None and typ != "freitext"):
        meldung = SKALA_MELDUNG if typ == "skala" else GEAENDERT_MELDUNG
        raise InhaltFehler(f"antwort_{frage_id}", meldung)


def speichere_antworten(
    db: sqlite3.Connection,
    konto_id: int,
    eingaben: dict[int, Eingabe],
    jetzt: str | None = None,
) -> int:
    """Speichert nur Geaendertes; gibt die Anzahl geaenderter Zeilen zurueck.

    Passt eine Eingabe nicht zum aktuellen `fragen.typ`, wirft das `InhaltFehler` und es wird
    nichts gespeichert.
    """
    jetzt = jetzt or zeit.zeitstempel()
    geaendert = 0
    with transaktion(db):
        for frage_id, (text, skalawert) in eingaben.items():
            _pruefe_art(db, frage_id, text, skalawert)
            alt = db.execute(
                "SELECT id, text, skalawert, aufnahme_id FROM antworten "
                "WHERE frage_id = ? AND konto_id = ?",
                (frage_id, konto_id),
            ).fetchone()
            leer = text is None and skalawert is None
            if alt is None:
                if leer:
                    continue
                db.execute(
                    "INSERT INTO antworten (frage_id, konto_id, text, skalawert, erstellt, "
                    "geaendert) VALUES (?, ?, ?, ?, ?, ?)",
                    (frage_id, konto_id, text, skalawert, jetzt, jetzt),
                )
            elif leer and alt["aufnahme_id"] is None:
                db.execute("DELETE FROM antworten WHERE id = ?", (alt["id"],))
            elif (alt["text"], alt["skalawert"]) == (text, skalawert):
                continue
            else:
                db.execute(
                    "UPDATE antworten SET text = ?, skalawert = ?, geaendert = ? WHERE id = ?",
                    (text, skalawert, jetzt, alt["id"]),
                )
            geaendert += 1
    return geaendert


def entferne_aufnahmen(db: sqlite3.Connection, konto_id: int, aufnahme_ids: list[int]) -> list[str]:
    """Loescht die Zeilen des Kontos in `aufnahmen` und gibt die Dateinamen zurueck.

    Innerhalb der Transaktion aufrufen; die Dateien loescht der Aufrufer erst nach dem COMMIT
    mit `aufnahmen.loesche_dateien`. Fremde Aufnahmen bleiben unberuehrt.
    """
    if not aufnahme_ids:
        return []
    platzhalter = ", ".join("?" * len(aufnahme_ids))
    parameter = [konto_id, *aufnahme_ids]
    zeilen = db.execute(
        f"SELECT dateiname FROM aufnahmen WHERE konto_id = ? AND id IN ({platzhalter})",
        parameter,
    ).fetchall()
    db.execute(f"DELETE FROM aufnahmen WHERE konto_id = ? AND id IN ({platzhalter})", parameter)
    return [zeile["dateiname"] for zeile in zeilen]


def loesche_antworten_der_runde(
    db: sqlite3.Connection, konto_id: int, runde_id: int, aufnahmen_verzeichnis: Path
) -> int:
    """Loescht alle Antworten des Kontos zur Runde samt Aufnahmen; gibt die Anzahl zurueck."""
    if db.in_transaction:
        raise RuntimeError(
            "Dateien werden erst nach dem COMMIT geloescht; keine laufende Transaktion"
        )
    with transaktion(db):
        zeilen = antworten_der_runde(db, konto_id, runde_id).values()
        aufnahme_ids = [z["aufnahme_id"] for z in zeilen if z["aufnahme_id"] is not None]
        for zeile in zeilen:
            db.execute("DELETE FROM antworten WHERE id = ?", (zeile["id"],))
        dateinamen = entferne_aufnahmen(db, konto_id, aufnahme_ids)
    loesche_dateien(aufnahmen_verzeichnis, dateinamen)
    return len(zeilen)


@dataclass(frozen=True)
class Stand:
    beantwortet: int
    fragen: int


def rundenstand(db: sqlite3.Connection, konto_id: int) -> dict[int, Stand]:
    """Fuer jede Runde: wie viele ihrer Fragen das Konto beantwortet hat."""
    zeilen = db.execute(
        "SELECT r.id AS runde_id, COUNT(f.id) AS fragen, COUNT(a.id) AS beantwortet "
        "FROM runden r LEFT JOIN fragen f ON f.runde_id = r.id "
        "LEFT JOIN antworten a ON a.frage_id = f.id AND a.konto_id = ? "
        "GROUP BY r.id",
        (konto_id,),
    ).fetchall()
    return {z["runde_id"]: Stand(z["beantwortet"], z["fragen"]) for z in zeilen}


# --- Tagebuch ---

TAGEBUCH_ARTEN = ("frei", "leitfragen", "impuls", "aufnahme")


def lies_tagebuchtext(text: str | None, pflicht: bool = True) -> str | None:
    """Normalisiert den Text eines Eintrags; leer ist nur ohne `pflicht` erlaubt (dann `None`)."""
    return langer_text(text or "", "text", "Der Eintrag ist noch leer." if pflicht else None)


def anzahl_tagebucheintraege(db: sqlite3.Connection, konto_id: int) -> int:
    return db.execute(
        "SELECT COUNT(*) FROM tagebucheintraege WHERE konto_id = ?", (konto_id,)
    ).fetchone()[0]


def lege_tagebucheintrag_an(
    db: sqlite3.Connection,
    konto_id: int,
    art: str,
    text: str | None,
    *,
    impuls: sqlite3.Row | None = None,
    leitfrage: sqlite3.Row | None = None,
    aufnahme_id: int | None = None,
    jetzt: str | None = None,
) -> int:
    """Legt einen Eintrag an; der Bezugstext wird kopiert. Gibt die neue `id` zurueck.

    Eine Kombination, die nicht zur Art passt, ist ein Programmierfehler (`ValueError`);
    ein ungueltiger Text wirft `InhaltFehler`.
    """
    if art not in TAGEBUCH_ARTEN:
        raise ValueError(f"Unbekannte Art: {art!r}")
    erwartet = (art == "impuls", art == "leitfragen", art == "aufnahme")
    gegeben = (impuls is not None, leitfrage is not None, aufnahme_id is not None)
    if erwartet != gegeben:
        raise ValueError(f"Bezug passt nicht zur Art {art!r}")
    text = lies_tagebuchtext(text, pflicht=art != "aufnahme")
    jetzt = jetzt or zeit.zeitstempel()
    with transaktion(db):
        return db.execute(
            "INSERT INTO tagebucheintraege (konto_id, art, text, impuls_id, impuls_text, "
            "leitfrage_id, leitfrage_text, aufnahme_id, erstellt, geaendert) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                konto_id,
                art,
                text,
                impuls["id"] if impuls else None,
                impuls["text"] if impuls else None,
                leitfrage["id"] if leitfrage else None,
                leitfrage["text"] if leitfrage else None,
                aufnahme_id,
                jetzt,
                jetzt,
            ),
        ).lastrowid


def hole_tagebucheintrag(
    db: sqlite3.Connection, konto_id: int, eintrag_id: int
) -> sqlite3.Row | None:
    return db.execute(
        "SELECT * FROM tagebucheintraege WHERE id = ? AND konto_id = ?", (eintrag_id, konto_id)
    ).fetchone()


def aendere_tagebucheintrag(
    db: sqlite3.Connection, konto_id: int, eintrag_id: int, text: str | None
) -> bool:
    """Aendert den Text; `geaendert` nur bei geaendertem Text. Fremd oder unbekannt: `False`."""
    with transaktion(db):
        alt = hole_tagebucheintrag(db, konto_id, eintrag_id)
        if alt is None:
            return False
        neu = lies_tagebuchtext(text, pflicht=alt["art"] != "aufnahme")
        if neu != alt["text"]:
            db.execute(
                "UPDATE tagebucheintraege SET text = ?, geaendert = ? "
                "WHERE id = ? AND konto_id = ?",
                (neu, zeit.zeitstempel(), eintrag_id, konto_id),
            )
    return True


def loesche_tagebucheintrag(
    db: sqlite3.Connection, konto_id: int, eintrag_id: int, aufnahmen_verzeichnis: Path
) -> bool:
    """Loescht den Eintrag samt Aufnahme; fremd oder unbekannt: `False`, nichts geaendert."""
    if db.in_transaction:
        raise RuntimeError(
            "Dateien werden erst nach dem COMMIT geloescht; keine laufende Transaktion"
        )
    with transaktion(db):
        eintrag = hole_tagebucheintrag(db, konto_id, eintrag_id)
        if eintrag is None:
            return False
        db.execute(
            "DELETE FROM tagebucheintraege WHERE id = ? AND konto_id = ?", (eintrag_id, konto_id)
        )
        aufnahme_ids = [] if eintrag["aufnahme_id"] is None else [eintrag["aufnahme_id"]]
        dateinamen = entferne_aufnahmen(db, konto_id, aufnahme_ids)
    loesche_dateien(aufnahmen_verzeichnis, dateinamen)
    return True


# --- Zeilen und Gruppierung ---


@dataclass(frozen=True)
class Zeile:
    """Eine Antwort oder ein Tagebucheintrag, flach (Grundlage fuer Liste und Export)."""

    quelle: str  # "antwort" | "tagebuch"
    id: int
    konto_id: int
    anzeigename: str
    art: str  # "runde" | "tagebuch" | "impuls"
    tagebuch_art: str | None  # frei | leitfragen | impuls | aufnahme
    angeleitet: bool  # True genau bei art == "runde"
    runde_id: int | None
    runde_titel: str | None
    runde_freischaltdatum: str | None
    frage_id: int | None
    frage: str | None  # aktueller Fragetext; bei Tagebuch der kopierte Bezugstext
    frage_typ: str | None
    frage_reihenfolge: int | None
    text: str | None
    skalawert: int | None
    aufnahme_id: int | None
    aufnahme_dateiname: str | None
    aufnahme_mime_typ: str | None
    aufnahme_dauer_sekunden: int | None
    erstellt: str  # UTC-Text
    geaendert: str  # gleich erstellt, solange nie geaendert


_ZEILEN_SQL = """
SELECT * FROM (
    SELECT 'antwort' AS quelle, a.id AS id, a.konto_id AS konto_id,
           k.anzeigename AS anzeigename, 'runde' AS art, NULL AS tagebuch_art,
           r.id AS runde_id, r.titel AS runde_titel,
           r.freischaltdatum AS runde_freischaltdatum,
           f.id AS frage_id, f.text AS frage, f.typ AS frage_typ,
           f.reihenfolge AS frage_reihenfolge, a.text AS text, a.skalawert AS skalawert,
           a.aufnahme_id AS aufnahme_id, au.dateiname AS aufnahme_dateiname,
           au.mime_typ AS aufnahme_mime_typ, au.dauer_sekunden AS aufnahme_dauer_sekunden,
           a.erstellt AS erstellt, a.geaendert AS geaendert
    FROM antworten a
    JOIN fragen f ON f.id = a.frage_id
    JOIN runden r ON r.id = f.runde_id
    JOIN konten k ON k.id = a.konto_id
    LEFT JOIN aufnahmen au ON au.id = a.aufnahme_id
    UNION ALL
    SELECT 'tagebuch', t.id, t.konto_id, k.anzeigename,
           CASE t.art WHEN 'impuls' THEN 'impuls' ELSE 'tagebuch' END, t.art,
           NULL, NULL, NULL, NULL, COALESCE(t.leitfrage_text, t.impuls_text), NULL, NULL,
           t.text, NULL, t.aufnahme_id, au.dateiname, au.mime_typ, au.dauer_sekunden,
           t.erstellt, t.geaendert
    FROM tagebucheintraege t
    JOIN konten k ON k.id = t.konto_id
    LEFT JOIN aufnahmen au ON au.id = t.aufnahme_id
)
"""


def _zeile(row: sqlite3.Row) -> Zeile:
    werte = dict(row)
    return Zeile(angeleitet=werte["art"] == "runde", **werte)


def zeilen_von(db: sqlite3.Connection, konto_id: int) -> list[Zeile]:
    """Alle Antworten und Eintraege des Kontos, ungefiltert nach Freischaltung."""
    zeilen = db.execute(
        _ZEILEN_SQL + " WHERE konto_id = ? ORDER BY erstellt, quelle, id", (konto_id,)
    ).fetchall()
    return [_zeile(z) for z in zeilen]


def alle_zeilen(db: sqlite3.Connection) -> list[Zeile]:
    """Alle Zeilen aller Konten; nur fuer die Auftraggeberin (#18)."""
    zeilen = db.execute(_ZEILEN_SQL + " ORDER BY erstellt, quelle, id").fetchall()
    return [_zeile(z) for z in zeilen]


@dataclass(frozen=True)
class Eintrag:
    """Was in einer Liste als eine Karte erscheint."""

    art: str  # "runde" | "tagebuch" | "impuls"
    konto_id: int
    anzeigename: str
    runde_id: int | None  # bei Runde
    eintrag_id: int | None  # bei Tagebuch
    erstellt: str  # Runde: fruehste Antwort
    geaendert: str  # Runde: spaeteste Antwort
    zeilen: list[Zeile]  # Runde: Antworten nach Fragenreihenfolge; Tagebuch: eine Zeile


def gruppiere(zeilen: list[Zeile]) -> list[Eintrag]:
    """Antworten einer Runde je Konto zu einer Karte, Tagebuch je Eintrag; neueste zuerst."""
    runden: dict[tuple[int, int], list[Zeile]] = {}
    karten: list[Eintrag] = []
    for z in zeilen:
        if z.quelle == "antwort":
            runden.setdefault((z.konto_id, z.runde_id), []).append(z)
        else:
            karten.append(
                Eintrag(z.art, z.konto_id, z.anzeigename, None, z.id, z.erstellt, z.geaendert, [z])
            )
    for (konto_id, runde_id), gruppe in runden.items():
        gruppe.sort(key=lambda z: (z.frage_reihenfolge, z.frage_id))
        karten.append(
            Eintrag(
                "runde",
                konto_id,
                gruppe[0].anzeigename,
                runde_id,
                None,
                min(z.erstellt for z in gruppe),
                max(z.geaendert for z in gruppe),
                gruppe,
            )
        )
    karten.sort(
        key=lambda k: (k.erstellt, k.art != "runde", k.runde_id or k.eintrag_id), reverse=True
    )
    return karten
