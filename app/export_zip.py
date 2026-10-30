"""Gesamtexport als ZIP, Stueck fuer Stueck gestreamt. Fachlogik ohne FastAPI."""

import logging
import os
import re
import stat
import unicodedata
import zipfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from app.aufnahmen import aufnahme_pfad
from app.export import Exportzeile

STUECK = 64 * 1024
TABELLE_IM_ZIP = "eintraege.csv"
DATEI_FEHLT = "Datei fehlt"

_UMLAUTE = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)
_NICHT_ERLAUBT = re.compile(r"[^a-z0-9]+")

_log = logging.getLogger(__name__)


def person_ascii(anzeigename: str, konto_id: int) -> str:
    """Namensteil fuer Dateinamen im ZIP: nur `[a-z0-9-]`, hoechstens 30 Zeichen."""
    text = unicodedata.normalize(
        "NFKD", unicodedata.normalize("NFC", anzeigename).translate(_UMLAUTE)
    )
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    text = _NICHT_ERLAUBT.sub("-", text).strip("-")[:30].strip("-")
    return text or f"lehrperson-{konto_id}"


def name_im_zip(e: Exportzeile, endung: str) -> str:
    teile = [person_ascii(e.zeile.anzeigename, e.zeile.konto_id)]
    if e.woche is not None:
        teile.append(f"W{e.woche:02d}")
    teile += [f"{e.erstellt:%Y-%m-%d}", f"{e.erstellt:%H%M}", e.zeile.art, str(e.zeile.aufnahme_id)]
    return "aufnahmen/" + "_".join(teile) + endung


@dataclass(frozen=True)
class ZipDatei:
    aufnahme_id: int
    quelle: Path
    name: str
    zeitpunkt: datetime  # Zuerich


def zip_dateien(exportzeilen: list[Exportzeile], verzeichnis: Path) -> list[ZipDatei]:
    """Aufnahmen fuers ZIP; ohne Dateizugriff. Namen ohne Muster werden ausgelassen."""
    ergebnis = []
    for e in exportzeilen:
        z = e.zeile
        if z.aufnahme_id is None:
            continue
        quelle = aufnahme_pfad(verzeichnis, z.aufnahme_dateiname or "")
        if quelle is None:
            continue
        ergebnis.append(ZipDatei(z.aufnahme_id, quelle, name_im_zip(e, quelle.suffix), e.erstellt))
    return ergebnis


class _Sammler:
    """Nur schreibbar (kein `seek`/`tell`): das ZIP laeuft so im Datenstrom-Modus."""

    def __init__(self) -> None:
        self._teile = bytearray()

    def write(self, daten: bytes) -> int:
        self._teile += daten
        return len(daten)

    def flush(self) -> None:
        pass

    def entnehmen(self) -> bytes:
        daten = bytes(self._teile)
        self._teile.clear()
        return daten


def _stuecke(quelle: BinaryIO) -> Iterator[bytes]:
    while stueck := quelle.read(STUECK):
        yield stueck


def zip_strom(
    dateien: list[ZipDatei], tabelle: Callable[[dict[int, str]], bytes]
) -> Iterator[bytes]:
    """ZIP als Folge von Bytes; nichts davon liegt als Ganzes im Speicher oder auf der Platte."""
    sammler = _Sammler()
    try:
        with zipfile.ZipFile(sammler, "w") as zf:
            vorhanden: dict[int, str] = {}
            for d in dateien:
                try:
                    datei = open(d.quelle, "rb")  # noqa: SIM115 - im with-Block darunter
                except FileNotFoundError:
                    continue  # verschwunden: die Tabelle nennt sie nicht
                with datei:
                    info = zipfile.ZipInfo(d.name, d.zeitpunkt.timetuple()[:6])
                    info.compress_type = zipfile.ZIP_STORED  # Audio ist schon komprimiert
                    info.file_size = os.fstat(datei.fileno()).st_size
                    info.external_attr = (stat.S_IFREG | 0o644) << 16
                    with zf.open(info, "w") as ziel:
                        for stueck in _stuecke(datei):
                            ziel.write(stueck)
                            yield sammler.entnehmen()
                vorhanden[d.aufnahme_id] = d.name
                if rest := sammler.entnehmen():  # Ende der Datei (Datenbeschreibung)
                    yield rest
            info = zipfile.ZipInfo(TABELLE_IM_ZIP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            daten = tabelle(vorhanden)
            with zf.open(info, "w") as ziel:
                for anfang in range(0, len(daten), STUECK):
                    ziel.write(daten[anfang : anfang + STUECK])
                    yield sammler.entnehmen()
        yield sammler.entnehmen()  # zentrales Verzeichnis
    except OSError:
        # Ohne Namen und Pfade: sie sind personenbezogen verknuepfbar.
        _log.warning("Gesamtexport abgebrochen")
        # Ohne Ursache: sonst traegt die Fehlermeldung des Servers den Dateipfad.
        raise RuntimeError("Gesamtexport abgebrochen") from None
