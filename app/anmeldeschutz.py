"""Schutz gegen Durchprobieren: begrenzt Fehlversuche pro Benutzername und Adresse.

Der Zustand liegt nur im Arbeitsspeicher und geht beim Neustart verloren.
"""

import threading
import time
from collections import deque
from collections.abc import Callable

from app.konten import normalisiere_benutzername


class Anmeldeschutz:
    def __init__(
        self,
        uhr: Callable[[], float] = time.monotonic,
        fenster: float = 900,
        max_pro_name: int = 5,
        max_pro_adresse: int = 20,
        max_schluessel: int = 10_000,
    ) -> None:
        self._uhr = uhr
        self._fenster = fenster
        self._max_pro_name = max_pro_name
        self._max_pro_adresse = max_pro_adresse
        self._max_schluessel = max_schluessel
        self._eintraege: dict[str, deque[float]] = {}
        self._sperre = threading.Lock()

    def _schluessel(self, benutzername: str, adresse: str) -> tuple[str, str]:
        return (
            "n:" + normalisiere_benutzername(benutzername),
            "a:" + adresse,
        )

    def _anzahl(self, schluessel: str, jetzt: float) -> int:
        """Entfernt veraltete Zeitpunkte und gibt die Anzahl im Fenster zurueck."""
        zeiten = self._eintraege.get(schluessel)
        if zeiten is None:
            return 0
        while zeiten and zeiten[0] <= jetzt - self._fenster:
            zeiten.popleft()
        if not zeiten:
            del self._eintraege[schluessel]
            return 0
        return len(zeiten)

    def gesperrt(self, benutzername: str, adresse: str) -> bool:
        name, adr = self._schluessel(benutzername, adresse)
        with self._sperre:
            jetzt = self._uhr()
            return (
                self._anzahl(name, jetzt) >= self._max_pro_name
                or self._anzahl(adr, jetzt) >= self._max_pro_adresse
            )

    def fehlversuch(self, benutzername: str, adresse: str) -> None:
        with self._sperre:
            jetzt = self._uhr()
            for schluessel in self._schluessel(benutzername, adresse):
                self._anzahl(schluessel, jetzt)
                self._eintraege.setdefault(schluessel, deque()).append(jetzt)
            while len(self._eintraege) > self._max_schluessel:
                aeltester = min(self._eintraege, key=lambda s: self._eintraege[s][-1])
                del self._eintraege[aeltester]

    def erfolg(self, benutzername: str) -> None:
        with self._sperre:
            self._eintraege.pop("n:" + normalisiere_benutzername(benutzername), None)
