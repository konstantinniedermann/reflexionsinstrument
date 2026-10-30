"""Bereinigung und Pruefung von Eingaben der Eingabemaske."""

import re

from app.zeit import ist_plausibel, lies_datum

LAENGE_TITEL_INSTRUMENT = 60
LAENGE_TITEL = 100
LAENGE_KURZ = 500
LAENGE_BESCHRIFTUNG = 60
LAENGE_LANG = 20_000

_ZEILENENDE = re.compile(r"\r\n|\r|\n")


class InhaltFehler(ValueError):
    """Eingabe ungueltig; `feld` nennt das Formularfeld, die Meldung ist fuer Menschen."""

    def __init__(self, feld: str, meldung: str):
        super().__init__(meldung)
        self.feld = feld
        self.meldung = meldung


class Gesperrt(Exception):
    """Aenderung nicht moeglich, weil schon `anzahl` Antworten daran haengen."""

    def __init__(self, anzahl: int):
        super().__init__(anzahl)
        self.anzahl = anzahl


def zu_lang(hoechstens: int) -> str:
    # Geschuetztes Leerzeichen als Tausendertrennzeichen: 20 000, aber 500.
    zahl = f"{hoechstens:,}".replace(",", " ")
    return f"Der Text ist zu lang (höchstens {zahl} Zeichen)."


def _pruefe(text: str, feld: str, hoechstens: int, leer_meldung: str | None) -> str | None:
    if not text:
        if leer_meldung is None:
            return None
        raise InhaltFehler(feld, leer_meldung)
    if len(text) > hoechstens:
        raise InhaltFehler(feld, zu_lang(hoechstens))
    return text


def kurzer_text(wert: str, feld: str, hoechstens: int, leer_meldung: str | None) -> str | None:
    return _pruefe(_ZEILENENDE.sub(" ", wert).strip(), feld, hoechstens, leer_meldung)


def langer_text(wert: str, feld: str, leer_meldung: str | None) -> str | None:
    text = wert.replace("\r\n", "\n").replace("\r", "\n").strip()
    return _pruefe(text, feld, LAENGE_LANG, leer_meldung)


def datum_feld(wert: str, feld: str, pflicht: bool) -> str | None:
    wert = wert.strip()
    datum = lies_datum(wert)
    if datum is not None:
        if not ist_plausibel(datum):
            raise InhaltFehler(feld, "Bitte ein Datum zwischen 2020 und 2099 wählen.")
        return datum.isoformat()
    if not wert and not pflicht:
        return None
    raise InhaltFehler(feld, "Bitte ein Datum wählen.")
