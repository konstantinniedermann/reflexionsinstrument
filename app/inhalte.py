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
from app.zeit import ist_plausibel, lies_datum

STANDARD_TITEL = "Reflexionsinstrument"


class NichtGefunden(LookupError):
    """Der Eintrag existiert nicht (mehr), z. B. weil er zwischen Anzeige und Absenden gelöscht wurde."""


SKALA_MIN = 1
SKALA_MAX = 5
TYPEN = ("freitext", "skala")

# art -> (Tabelle, Spalte der Gruppe oder None). Namen stehen fest im Code, nie aus Eingaben.
# Fragen und Zusatzinfos teilen sich die Reihenfolge ihrer Runde (siehe «Ablauf»).
GEORDNET = {
    "info": ("info_abschnitte", None),
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


def inhalte_vorhanden(db: sqlite3.Connection) -> bool:
    zahlen = zaehle_inhalte(db)
    return any(zahlen[k] for k in ("info_abschnitte", "runden", "leitfragen", "impulse"))


def loesche_alle_inhalte(db: sqlite3.Connection) -> None:
    """Leert Infoblock, Runden (samt Fragen), Leitfragen und Impulse. Mit Antworten: Gesperrt."""
    with transaktion(db):
        try:
            for tabelle in ("info_abschnitte", "runden", "leitfragen", "impulse"):
                db.execute(f"DELETE FROM {tabelle}")
        except sqlite3.IntegrityError as fehler:
            antworten = db.execute("SELECT COUNT(*) FROM antworten").fetchone()[0]
            raise Gesperrt(max(antworten, 1)) from fehler


# ---------- Runden ----------

_RUNDEN_SQL = (
    "SELECT r.id, r.titel, r.fallbeispiel, r.freischaltdatum, "
    "(SELECT COUNT(*) FROM fragen f WHERE f.runde_id = r.id) AS anzahl_fragen, "
    "(SELECT COUNT(*) FROM zusatzinfos z WHERE z.runde_id = r.id) AS anzahl_zusatzinfos "
    "FROM runden r"
)


def runden(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(f"{_RUNDEN_SQL} ORDER BY r.freischaltdatum, r.id").fetchall()


def runde(db: sqlite3.Connection, runde_id: int) -> sqlite3.Row | None:
    return db.execute(f"{_RUNDEN_SQL} WHERE r.id = ?", (runde_id,)).fetchone()


def _eine_woche_spaeter(text: str) -> date | None:
    """Ein Altwert in der Datenbank darf den Vorschlag leeren, nie die Seite zum Absturz bringen."""
    try:
        vorschlag = date.fromisoformat(text) + timedelta(days=7)
    except (ValueError, OverflowError):
        return None
    return vorschlag if ist_plausibel(vorschlag) else None


def datum_vorschlag_runde(db: sqlite3.Connection) -> date | None:
    """Eine Woche nach der letzten Runde, ohne Runden der erste Tag, sonst nichts.

    Ein unplausibler Altwert ergibt keinen Vorschlag.
    """
    letzte = db.execute("SELECT MAX(freischaltdatum) FROM runden").fetchone()[0]
    if letzte is not None:
        return _eine_woche_spaeter(letzte)
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
        raise NichtGefunden(runde_id)


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
            raise NichtGefunden(runde_id)
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


# Naechste Nummer im Ablauf einer Runde, ueber Fragen und Zusatzinfos hinweg. Erwartet die
# Runden-Id zweimal. Als Teilabfrage im INSERT wird sie im selben Schritt gelesen und geschrieben.
_NAECHSTE_NUMMER = (
    "(SELECT coalesce(max(reihenfolge), 0) + 1 FROM ("
    "SELECT reihenfolge FROM fragen WHERE runde_id = ? "
    "UNION ALL SELECT reihenfolge FROM zusatzinfos WHERE runde_id = ?))"
)


def lege_frage_an(
    db: sqlite3.Connection,
    runde_id: int,
    typ: str,
    text: str,
    skala_min_text: str,
    skala_max_text: str,
) -> int:
    """Neue Frage am Ende des Ablaufs der Runde."""
    werte = _pruefe_frage(typ, text, skala_min_text, skala_max_text)
    try:
        return db.execute(
            "INSERT INTO fragen (runde_id, typ, text, skala_min_text, skala_max_text, "
            f"reihenfolge) VALUES (?, ?, ?, ?, ?, {_NAECHSTE_NUMMER})",
            (runde_id, *werte, runde_id, runde_id),
        ).lastrowid
    except sqlite3.IntegrityError as fehler:
        if runde(db, runde_id) is None:
            raise NichtGefunden(runde_id) from fehler
        raise


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
            raise NichtGefunden(frage_id)
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
            raise NichtGefunden(frage_id)
        anzahl = zaehle_antworten_frage(db, frage_id)
        if anzahl:
            raise Gesperrt(anzahl)
        try:
            db.execute("DELETE FROM fragen WHERE id = ?", (frage_id,))
        except sqlite3.IntegrityError as fehler:
            # Sicherheitsnetz: die Datenbank verweigert, was die Pruefung uebersehen hat.
            raise Gesperrt(max(_antworten_frage(db, frage_id), 1)) from fehler
        _nummeriere_ablauf(db, bisher["runde_id"])


# ---------- Zusatzinfos ----------


def zusatzinfos(db: sqlite3.Connection, runde_id: int) -> list[sqlite3.Row]:
    return db.execute(
        "SELECT * FROM zusatzinfos WHERE runde_id = ? ORDER BY reihenfolge, id", (runde_id,)
    ).fetchall()


def zusatzinfo(db: sqlite3.Connection, info_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM zusatzinfos WHERE id = ?", (info_id,)).fetchone()


def _pruefe_zusatzinfo(inhalt: str) -> str:
    return langer_text(inhalt, "inhalt", "Bitte einen Text eingeben.")


def lege_zusatzinfo_an(db: sqlite3.Connection, runde_id: int, inhalt: str) -> int:
    """Neue Zusatzinfo am Ende des Ablaufs der Runde."""
    text = _pruefe_zusatzinfo(inhalt)
    try:
        return db.execute(
            f"INSERT INTO zusatzinfos (runde_id, inhalt, reihenfolge) VALUES (?, ?, {_NAECHSTE_NUMMER})",
            (runde_id, text, runde_id, runde_id),
        ).lastrowid
    except sqlite3.IntegrityError as fehler:
        if runde(db, runde_id) is None:
            raise NichtGefunden(runde_id) from fehler
        raise


def aendere_zusatzinfo(db: sqlite3.Connection, info_id: int, inhalt: str) -> None:
    text = _pruefe_zusatzinfo(inhalt)
    if db.execute("UPDATE zusatzinfos SET inhalt = ? WHERE id = ?", (text, info_id)).rowcount == 0:
        raise NichtGefunden(info_id)


def loesche_zusatzinfo(db: sqlite3.Connection, info_id: int) -> None:
    """An einer Zusatzinfo haengen keine Antworten; sie laesst sich immer loeschen."""
    with transaktion(db):
        bisher = zusatzinfo(db, info_id)
        if bisher is None:
            raise NichtGefunden(info_id)
        db.execute("DELETE FROM zusatzinfos WHERE id = ?", (info_id,))
        _nummeriere_ablauf(db, bisher["runde_id"])


# ---------- Ablauf einer Runde ----------

# art -> Tabelle; die Namen stehen fest im Code, nie aus Eingaben.
ABLAUF = {"frage": "fragen", "zusatzinfo": "zusatzinfos"}


def ablauf(db: sqlite3.Connection, runde_id: int) -> list[dict]:
    """Fragen und Zusatzinfos der Runde in ihrer gemeinsamen Reihenfolge.

    Jeder Baustein ist `{"art": "frage", "frage": Row}` oder
    `{"art": "zusatzinfo", "zusatzinfo": Row}`. Bei gleicher Nummer (nur in Altdaten
    denkbar) steht die Frage vor der Zusatzinfo.
    """
    bausteine = [
        (f["reihenfolge"], 0, f["id"], {"art": "frage", "frage": f}) for f in fragen(db, runde_id)
    ]
    bausteine += [
        (z["reihenfolge"], 1, z["id"], {"art": "zusatzinfo", "zusatzinfo": z})
        for z in zusatzinfos(db, runde_id)
    ]
    return [b[3] for b in sorted(bausteine, key=lambda b: b[:3])]


def _ablauf_schluessel(db: sqlite3.Connection, runde_id: int) -> list[tuple[str, int]]:
    return [(b["art"], b[b["art"]]["id"]) for b in ablauf(db, runde_id)]


def _schreibe_ablauf(db: sqlite3.Connection, schluessel: list[tuple[str, int]]) -> None:
    for nummer, (art, eintrag_id) in enumerate(schluessel, start=1):
        db.execute(f"UPDATE {ABLAUF[art]} SET reihenfolge = ? WHERE id = ?", (nummer, eintrag_id))


def _nummeriere_ablauf(db: sqlite3.Connection, runde_id: int) -> None:
    _schreibe_ablauf(db, _ablauf_schluessel(db, runde_id))


def verschiebe_im_ablauf(db: sqlite3.Connection, art: str, eintrag_id: int, richtung: str) -> None:
    """Tauscht Frage oder Zusatzinfo mit ihrem Nachbarn im Ablauf, egal welcher Art.

    Am Rand ohne Wirkung; schreibt die Runde 1 bis n neu.
    """
    if richtung not in ("hoch", "runter") or art not in ABLAUF:
        raise ValueError(f"{art!r} / {richtung!r}")
    with transaktion(db):
        zeile = db.execute(f"SELECT runde_id FROM {ABLAUF[art]} WHERE id = ?", (eintrag_id,))
        zeile = zeile.fetchone()
        if zeile is None:
            return
        schluessel = _ablauf_schluessel(db, zeile[0])
        stelle = schluessel.index((art, eintrag_id))
        nachbar = stelle - 1 if richtung == "hoch" else stelle + 1
        if 0 <= nachbar < len(schluessel):
            schluessel[stelle], schluessel[nachbar] = schluessel[nachbar], schluessel[stelle]
        _schreibe_ablauf(db, schluessel)


# ---------- Infoblock ----------


def info_abschnitte(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute("SELECT * FROM info_abschnitte ORDER BY reihenfolge, id").fetchall()


def info_abschnitt(db: sqlite3.Connection, abschnitt_id: int) -> sqlite3.Row | None:
    return db.execute("SELECT * FROM info_abschnitte WHERE id = ?", (abschnitt_id,)).fetchone()


def _pruefe_info(titel: str, inhalt: str):
    sauberer_titel = kurzer_text(titel, "titel", LAENGE_TITEL, "Bitte einen Titel eingeben.")
    text = langer_text(inhalt, "inhalt", "Bitte einen Text eingeben.")
    return sauberer_titel, text


def lege_info_an(db: sqlite3.Connection, titel: str, inhalt: str) -> int:
    werte = _pruefe_info(titel, inhalt)
    # Eine Anweisung: die naechste Nummer wird im selben Schritt gelesen und geschrieben.
    return db.execute(
        "INSERT INTO info_abschnitte (titel, inhalt, reihenfolge) "
        "SELECT ?, ?, coalesce(max(reihenfolge), 0) + 1 FROM info_abschnitte",
        werte,
    ).lastrowid


def aendere_info(db: sqlite3.Connection, abschnitt_id: int, titel: str, inhalt: str) -> None:
    werte = _pruefe_info(titel, inhalt)
    aenderungen = db.execute(
        "UPDATE info_abschnitte SET titel = ?, inhalt = ? WHERE id = ?", (*werte, abschnitt_id)
    ).rowcount
    if aenderungen == 0:
        raise NichtGefunden(abschnitt_id)


def loesche_info(db: sqlite3.Connection, abschnitt_id: int) -> None:
    with transaktion(db):
        geloescht = db.execute("DELETE FROM info_abschnitte WHERE id = ?", (abschnitt_id,)).rowcount
        if geloescht == 0:
            raise NichtGefunden(abschnitt_id)
        _nummeriere(db, "info", None)


# ---------- Leitfragen ----------

_LEITFRAGEN_SQL = (
    "SELECT l.*, "
    "(SELECT COUNT(*) FROM tagebucheintraege t WHERE t.leitfrage_id = l.id) AS anzahl_eintraege "
    "FROM leitfragen l"
)


def leitfragen(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(f"{_LEITFRAGEN_SQL} ORDER BY l.reihenfolge, l.id").fetchall()


def leitfrage(db: sqlite3.Connection, leitfrage_id: int) -> sqlite3.Row | None:
    return db.execute(f"{_LEITFRAGEN_SQL} WHERE l.id = ?", (leitfrage_id,)).fetchone()


def _pruefe_leitfrage(text: str) -> str:
    return kurzer_text(text, "text", LAENGE_KURZ, "Bitte eine Frage eingeben.")


def lege_leitfrage_an(db: sqlite3.Connection, text: str) -> int:
    sauberer_text = _pruefe_leitfrage(text)
    return db.execute(
        "INSERT INTO leitfragen (text, reihenfolge) "
        "SELECT ?, coalesce(max(reihenfolge), 0) + 1 FROM leitfragen",
        (sauberer_text,),
    ).lastrowid


def aendere_leitfrage(db: sqlite3.Connection, leitfrage_id: int, text: str) -> None:
    sauberer_text = _pruefe_leitfrage(text)
    aenderungen = db.execute(
        "UPDATE leitfragen SET text = ? WHERE id = ?", (sauberer_text, leitfrage_id)
    ).rowcount
    if aenderungen == 0:
        raise NichtGefunden(leitfrage_id)


def loesche_leitfrage(db: sqlite3.Connection, leitfrage_id: int) -> None:
    """Eintraege behalten ihren Text; ihr Verweis wird von der Datenbank geleert."""
    with transaktion(db):
        geloescht = db.execute("DELETE FROM leitfragen WHERE id = ?", (leitfrage_id,)).rowcount
        if geloescht == 0:
            raise NichtGefunden(leitfrage_id)
        _nummeriere(db, "leitfrage", None)


# ---------- Impulse ----------

_IMPULSE_SQL = (
    "SELECT i.*, "
    "(SELECT COUNT(*) FROM tagebucheintraege t WHERE t.impuls_id = i.id) AS anzahl_eintraege "
    "FROM impulse i"
)


def impulse(db: sqlite3.Connection) -> list[sqlite3.Row]:
    return db.execute(f"{_IMPULSE_SQL} ORDER BY i.sichtbar_ab, i.id").fetchall()


def impuls(db: sqlite3.Connection, impuls_id: int) -> sqlite3.Row | None:
    return db.execute(f"{_IMPULSE_SQL} WHERE i.id = ?", (impuls_id,)).fetchone()


def datum_vorschlag_impuls(db: sqlite3.Connection) -> date | None:
    """Eine Woche nach dem letzten Impuls, ohne Impulse der erste Tag, sonst nichts."""
    letzter = db.execute("SELECT MAX(sichtbar_ab) FROM impulse").fetchone()[0]
    if letzter is not None:
        return _eine_woche_spaeter(letzter)
    return lies_projektstart(db)


def _pruefe_impuls(text: str, sichtbar_ab: str):
    sauberer_text = kurzer_text(text, "text", LAENGE_KURZ, "Bitte einen Impuls eingeben.")
    return sauberer_text, datum_feld(sichtbar_ab, "sichtbar_ab", pflicht=True)


def lege_impuls_an(db: sqlite3.Connection, text: str, sichtbar_ab: str) -> int:
    werte = _pruefe_impuls(text, sichtbar_ab)
    return db.execute("INSERT INTO impulse (text, sichtbar_ab) VALUES (?, ?)", werte).lastrowid


def aendere_impuls(db: sqlite3.Connection, impuls_id: int, text: str, sichtbar_ab: str) -> None:
    werte = _pruefe_impuls(text, sichtbar_ab)
    aenderungen = db.execute(
        "UPDATE impulse SET text = ?, sichtbar_ab = ? WHERE id = ?", (*werte, impuls_id)
    ).rowcount
    if aenderungen == 0:
        raise NichtGefunden(impuls_id)


def loesche_impuls(db: sqlite3.Connection, impuls_id: int) -> None:
    """Eintraege behalten ihren Text; ihr Verweis wird von der Datenbank geleert."""
    geloescht = db.execute("DELETE FROM impulse WHERE id = ?", (impuls_id,)).rowcount
    if geloescht == 0:
        raise NichtGefunden(impuls_id)


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
