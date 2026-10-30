"""Kommandozeile fuer den Betreiber: erstes Konto anlegen, Passwort setzen."""

import argparse
import getpass
import os
import sys
from pathlib import Path
from typing import TextIO

from app.db import migriere, verbinde
from app.konten import EingabeFehler, finde_hash, lege_konto_an, setze_passwort


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
    return parser


def main(argv: list[str] | None = None, eingabe: TextIO | None = None) -> int:
    argumente = _parser().parse_args(argv)
    daten_verzeichnis = Path(os.environ.get("DATEN_VERZEICHNIS", ".daten"))
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
