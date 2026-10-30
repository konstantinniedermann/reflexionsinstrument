"""Abbruch-Ausnahmen fuer Anmelde- und Rollenpruefung (eigenes Modul gegen Zirkelimporte)."""


class NichtAngemeldet(Exception):
    pass


class KeinZugriff(Exception):
    def __init__(
        self,
        text: str = "Diese Seite ist für deinen Zugang nicht freigegeben.",
        titel: str = "Kein Zugriff",
    ):
        super().__init__(text)
        self.text = text
        self.titel = titel
