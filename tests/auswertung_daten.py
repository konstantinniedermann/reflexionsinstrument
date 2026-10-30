"""Gemeinsame Testhilfen fuer die Ansicht der Auftraggeberin und den Export (#18)."""

import dataclasses

from app.eintraege import Zeile

_ZEIT = "2026-11-24T08:00:00Z"

_STANDARD = Zeile(
    quelle="antwort",
    id=1,
    konto_id=1,
    anzeigename="Anna Beispiel",
    art="runde",
    tagebuch_art=None,
    angeleitet=True,
    runde_id=1,
    runde_titel="Runde Eins",
    runde_freischaltdatum="2026-11-23",
    frage_id=1,
    frage="Frage A",
    frage_typ="freitext",
    frage_reihenfolge=1,
    text="Antwort",
    skalawert=None,
    aufnahme_id=None,
    aufnahme_dateiname=None,
    aufnahme_mime_typ=None,
    aufnahme_dauer_sekunden=None,
    erstellt=_ZEIT,
    geaendert=_ZEIT,
)


def zeile(**abweichungen) -> Zeile:
    """Eine Antwort von Anna Beispiel; `abweichungen` ueberschreiben einzelne Felder."""
    return dataclasses.replace(_STANDARD, **abweichungen)


def setze_zeit(db, tabelle: str, zeilen_id: int, erstellt: str, geaendert: str | None = None):
    """Setzt `erstellt` und `geaendert` (Standard: gleich), damit Tests nicht von der Uhr abhaengen."""
    db.execute(
        f"UPDATE {tabelle} SET erstellt = ?, geaendert = ? WHERE id = ?",
        (erstellt, geaendert or erstellt, zeilen_id),
    )


def setze_projektstart(db, tag: str):
    db.execute(
        "INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', ?) "
        "ON CONFLICT(schluessel) DO UPDATE SET wert = excluded.wert",
        (tag,),
    )
