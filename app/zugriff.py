"""Abbruch-Ausnahmen fuer Anmelde- und Rollenpruefung (eigenes Modul gegen Zirkelimporte)."""


class NichtAngemeldet(Exception):
    pass


class KeinZugriff(Exception):
    def __init__(self, text: str = "Diese Seite ist für deinen Zugang nicht freigegeben."):
        super().__init__(text)
        self.text = text
