"""Kommandozeile fuer den Betreiber: erstes Konto anlegen, Passwort setzen."""

import argparse
import getpass
import json
import os
import sqlite3
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import TextIO

from app import zeit
from app.db import migriere, transaktion, verbinde
from app.eingaben import Gesperrt, InhaltFehler
from app.inhalte import (
    inhalte_vorhanden,
    lege_frage_an,
    lege_impuls_an,
    lege_info_an,
    lege_leitfrage_an,
    lege_runde_an,
    loesche_alle_inhalte,
    speichere_allgemein,
    zaehle_inhalte,
)
from app.konten import EingabeFehler, finde_hash, lege_konto_an, setze_passwort

PLATZHALTER_DATEI = (
    Path(__file__).resolve().parent.parent / "tests" / "platzhalter" / "inhalte.json"
)


def _lies_passwort(eingabe: TextIO | None) -> str:
    quelle = eingabe if eingabe is not None else sys.stdin
    if eingabe is None and sys.stdin.isatty():
        erstes = getpass.getpass("Passwort: ")
        if getpass.getpass("Passwort wiederholen: ") != erstes:
            raise EingabeFehler("passwort", "Die beiden Passwörter sind nicht gleich.")
        return erstes
    return quelle.readline().rstrip("\r\n")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.kommandos")
    unterbefehle = parser.add_subparsers(dest="befehl", required=True)
    anlegen = unterbefehle.add_parser("auftraggeberin-anlegen")
    anlegen.add_argument("--benutzername", required=True)
    anlegen.add_argument("--anzeigename", required=True)
    setzen = unterbefehle.add_parser("passwort-setzen")
    setzen.add_argument("--benutzername", required=True)
    platzhalter = unterbefehle.add_parser("platzhalter-laden")
    platzhalter.add_argument("--projektstart", default=None)
    platzhalter.add_argument("--ersetzen", action="store_true")
    return parser


def lade_platzhalter(db: sqlite3.Connection, daten: dict, projektstart: date) -> dict[str, int]:
    """Legt die Platzhalter ueber die Fachfunktionen an, ganz oder gar nicht."""

    def tag(abstand: int) -> str:
        return (projektstart + timedelta(days=abstand)).isoformat()

    with transaktion(db):
        speichere_allgemein(db, daten["titel"], daten["begruessung"], projektstart.isoformat())
        for abschnitt in daten["info"]:
            lege_info_an(db, abschnitt["titel"], abschnitt["inhalt"])
        for eintrag in daten["runden"]:
            runde_id = lege_runde_an(
                db, eintrag["titel"], eintrag["fallbeispiel"] or "", tag(eintrag["tag"])
            )
            for frage in eintrag["fragen"]:
                lege_frage_an(
                    db,
                    runde_id,
                    frage["typ"],
                    frage["text"],
                    frage.get("skala_min_text", ""),
                    frage.get("skala_max_text", ""),
                )
        for text in daten["leitfragen"]:
            lege_leitfrage_an(db, text)
        for impuls in daten["impulse"]:
            lege_impuls_an(db, impuls["text"], tag(impuls["tag"]))
        return zaehle_inhalte(db)


def _platzhalter_laden(daten_verzeichnis: Path, argumente: argparse.Namespace) -> int:
    if os.environ.get("PRODUKTION") == "1":
        print("Platzhalter-Inhalte sind in Produktion nicht erlaubt.", file=sys.stderr)
        return 1
    if argumente.projektstart is None:
        projektstart = zeit.heute()
    else:
        projektstart = zeit.lies_datum(argumente.projektstart)
        if projektstart is None:
            print("Bitte das Datum als JJJJ-MM-TT angeben.", file=sys.stderr)
            return 1
    try:
        daten = json.loads(PLATZHALTER_DATEI.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        print(
            f"Die Datei mit den Platzhaltern fehlt oder ist unlesbar: {PLATZHALTER_DATEI}",
            file=sys.stderr,
        )
        return 1
    daten_verzeichnis.mkdir(parents=True, exist_ok=True)
    db = verbinde(daten_verzeichnis / "reflexion.db")
    try:
        migriere(db)
        if inhalte_vorhanden(db) and not argumente.ersetzen:
            print(
                "Es gibt schon Inhalte. Mit --ersetzen werden sie vorher gelöscht.",
                file=sys.stderr,
            )
            return 1
        with transaktion(db):
            if argumente.ersetzen:
                loesche_alle_inhalte(db)
            zahlen = lade_platzhalter(db, daten, projektstart)
    except Gesperrt:
        print(
            "Es gibt schon Antworten von Lehrpersonen. Die Inhalte werden nicht ersetzt.",
            file=sys.stderr,
        )
        return 1
    except InhaltFehler as fehler:
        print(fehler.meldung, file=sys.stderr)
        return 1
    finally:
        db.close()
    print(
        f"Platzhalter geladen: {zahlen['info_abschnitte']} Abschnitte, {zahlen['runden']} Runden, "
        f"{zahlen['fragen']} Fragen, {zahlen['leitfragen']} Leitfragen, {zahlen['impulse']} Impulse."
    )
    return 0


def main(argv: list[str] | None = None, eingabe: TextIO | None = None) -> int:
    argumente = _parser().parse_args(argv)
    daten_verzeichnis = Path(os.environ.get("DATEN_VERZEICHNIS", ".daten"))
    if argumente.befehl == "platzhalter-laden":
        return _platzhalter_laden(daten_verzeichnis, argumente)
    daten_verzeichnis.mkdir(parents=True, exist_ok=True)
    db = verbinde(daten_verzeichnis / "reflexion.db")
    try:
        migriere(db)
        passwort = _lies_passwort(eingabe)
        if argumente.befehl == "auftraggeberin-anlegen":
            konto = lege_konto_an(
                db,
                argumente.anzeigename,
                argumente.benutzername,
                passwort,
                rolle="auftraggeberin",
            )
            print(f"Zugang '{konto.benutzername}' für die Auftraggeberin ist angelegt.")
        else:
            gefunden = finde_hash(db, argumente.benutzername)
            if gefunden is None:
                print("Diesen Benutzernamen gibt es nicht.", file=sys.stderr)
                return 1
            setze_passwort(db, gefunden[0].id, passwort)
            print(f"Das Passwort für '{gefunden[0].benutzername}' ist neu gesetzt.")
    except EingabeFehler as fehler:
        print(str(fehler), file=sys.stderr)
        return 1
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
