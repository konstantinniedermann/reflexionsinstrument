import os
import warnings
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ENTWICKLUNGS_SCHLUESSEL = "nur-fuer-entwicklung"
MINDESTLAENGE_SCHLUESSEL = 32


@dataclass(frozen=True)
class Einstellungen:
    daten_verzeichnis: Path
    geheimer_schluessel: str
    produktion: bool

    @property
    def db_pfad(self) -> Path:
        return self.daten_verzeichnis / "reflexion.db"

    @property
    def aufnahmen_verzeichnis(self) -> Path:
        return self.daten_verzeichnis / "aufnahmen"


def lade_einstellungen(umgebung: Mapping[str, str] | None = None) -> Einstellungen:
    if umgebung is None:
        umgebung = os.environ
    produktion = umgebung.get("PRODUKTION") == "1"
    schluessel = umgebung.get("GEHEIMER_SCHLUESSEL", "")
    if not schluessel:
        if produktion:
            raise RuntimeError("GEHEIMER_SCHLUESSEL muss in Produktion gesetzt sein.")
        warnings.warn(
            "GEHEIMER_SCHLUESSEL fehlt, es wird der Entwicklungswert verwendet.",
            UserWarning,
            stacklevel=2,
        )
        schluessel = ENTWICKLUNGS_SCHLUESSEL
    elif produktion and len(schluessel) < MINDESTLAENGE_SCHLUESSEL:
        raise RuntimeError(
            f"GEHEIMER_SCHLUESSEL muss in Produktion mindestens {MINDESTLAENGE_SCHLUESSEL}"
            " Zeichen lang sein."
        )
    return Einstellungen(
        daten_verzeichnis=Path(umgebung.get("DATEN_VERZEICHNIS", ".daten")),
        geheimer_schluessel=schluessel,
        produktion=produktion,
    )
