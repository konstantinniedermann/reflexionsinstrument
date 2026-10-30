"""Register der festen Texte: Vorschlaege im Code, bestaetigte Fassungen in der Tabelle `texte`."""

import sqlite3
from dataclasses import dataclass

from app.eingaben import langer_text


@dataclass(frozen=True)
class Textvorlage:
    schluessel: str  # Schluessel in der Tabelle texte
    bezeichnung: str  # Ueberschrift in der Maske
    ort: str  # wo er erscheint, in einfacher Sprache
    bereich: str  # "allgemein" (Begruessung) oder "hinweise"
    vorschlag: str  # gilt, solange die Auftraggeberin nichts gespeichert hat


@dataclass(frozen=True)
class Textstand:
    vorlage: Textvorlage
    inhalt: str
    bestaetigt: bool
    geaendert: str | None


_VORLAGEN = [
    Textvorlage(
        "begruessung",
        "Begrüssung",
        "Auf der Startseite, ganz oben.",
        "allgemein",
        "Willkommen im Reflexionsinstrument. Hier hältst du Gedanken zu deinem Unterricht "
        "fest und beantwortest Fragen, die nach und nach freigeschaltet werden.",
    ),
    Textvorlage(
        "hinweis_tagebuch",
        "Hinweis im Tagebuch",
        "Im Tagebuch, über dem Eingabefeld und dem Aufnahmeknopf.",
        "hinweise",
        "Bitte keine Namen, Orte oder Klassenbezeichnungen notieren und nichts, was "
        "Rückschlüsse auf Kinder, Eltern oder Kolleginnen und Kollegen erlaubt. Situationen "
        "lassen sich allgemein beschreiben, zum Beispiel ‹ein Kind aus der Klasse›.",
    ),
    Textvorlage(
        "hinweis_wer_sieht_was",
        "Wer sieht was",
        "Auf der Startseite, unter der Begrüssung.",
        "hinweise",
        "Die anderen Lehrpersonen sehen die Einträge nicht. Die Projektleiterin liest alle "
        "Einträge mit Namen und hört die Aufnahmen an, schon während der vier Wochen. Sie "
        "dienen ihr als Grundlage für die Gespräche nach dem Projekt.",
    ),
    Textvorlage(
        "hinweis_gast",
        "Hinweis für Gäste",
        "Beim Ansehen ohne Konto, oben auf jeder Seite.",
        "hinweise",
        "Ansicht ohne Speichern. Hier lässt sich das Instrument mit den bereits "
        "freigeschalteten Inhalten ansehen. Eingaben werden nicht gespeichert, und Einträge "
        "von Lehrpersonen sind nicht sichtbar.",
    ),
    Textvorlage(
        "hinweis_datenspeicherung",
        "Datenschutz im Infoblock",
        "Im Infoblock, als letzter Abschnitt «Datenschutz».",
        "hinweise",
        "Die Einträge und Aufnahmen liegen auf einem Server in Frankfurt (EU). Gespeichert "
        "werden nur Name, Benutzername, Passwort (unlesbar gespeichert), Einträge und "
        "Aufnahmen, keine E-Mail-Adressen. Eigene Einträge lassen sich jederzeit ändern und "
        "löschen. Nach Abschluss des Projekts werden alle Daten gelöscht.",
    ),
    Textvorlage(
        "hinweis_aufnahme",
        "Hinweis zu Aufnahmen",
        "Neben dem Aufnahmeknopf, im Tagebuch und bei Fragen.",
        "hinweise",
        "Die Aufnahme wird gespeichert, und die Projektleiterin hört sie an. Bitte auch "
        "beim Sprechen keine Namen nennen.",
    ),
]

REGISTER: dict[str, Textvorlage] = {v.schluessel: v for v in _VORLAGEN}


def _zeile(db: sqlite3.Connection, schluessel: str) -> sqlite3.Row | None:
    return db.execute(
        "SELECT inhalt, geaendert FROM texte WHERE schluessel = ?", (schluessel,)
    ).fetchone()


def lies_textstand(db: sqlite3.Connection, schluessel: str) -> Textstand:
    vorlage = REGISTER[schluessel]
    zeile = _zeile(db, schluessel)
    if zeile is None:
        return Textstand(vorlage, vorlage.vorschlag, False, None)
    return Textstand(vorlage, zeile["inhalt"], True, zeile["geaendert"])


def lies_text(db: sqlite3.Connection, schluessel: str) -> str:
    return lies_textstand(db, schluessel).inhalt


def lies_texte(db: sqlite3.Connection, bereich: str) -> list[Textstand]:
    return [lies_textstand(db, k) for k, v in REGISTER.items() if v.bereich == bereich]


def speichere_text(db: sqlite3.Connection, schluessel: str, inhalt: str) -> None:
    if schluessel not in REGISTER:
        raise KeyError(schluessel)
    text = langer_text(inhalt, "inhalt", "Bitte einen Text eingeben.")
    db.execute(
        "INSERT INTO texte (schluessel, inhalt) VALUES (?, ?) "
        "ON CONFLICT(schluessel) DO UPDATE SET inhalt = excluded.inhalt, "
        "geaendert = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')",
        (schluessel, text),
    )
