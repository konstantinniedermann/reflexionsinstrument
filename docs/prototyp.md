# Klickbarer Prototyp (#1)

Ein Wegwerf-Prototyp, um Feedback von der Auftraggeberin zu holen. Er ist **nicht** die Pilot-Version. Die Technik der Pilot-Version wird in #5 entschieden.

## Ziel
Die Auftraggeberin klickt auf ihrem Handy durch, wie sich das Instrument für eine Lehrperson und für sie selbst anfühlt, und sagt, was gut ist, was weg kann und was fehlt.

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Technik | Statisches HTML, CSS und JavaScript ohne Framework und ohne Build | Keine Dependencies, öffnet sich per Doppelklick oder per Link, wird nach dem Feedback weggeworfen |
| Speicherung | Nur im Browser (`localStorage`), mit Rücksetzknopf | Kein Server nötig, keine echten Daten |
| Bereitstellung | GitHub Pages | Kostenlos, per Link auf dem Handy aufrufbar |
| Inhalte | Selbst geschriebene Platzhalter in `prototyp/js/inhalte.js`, getrennt vom Code | Echte Inhalte fehlen noch und gehören nicht ins öffentliche Repo |
| Anmeldung | Simuliert: Auswahl «Lehrperson 1–4» oder «Projektleiterin» (= Auftraggeberin) | Zeigt, dass jede Lehrperson nur ihre Einträge sieht, ohne echtes Login zu bauen |
| Zeitverlauf | Demo-Schalter «Woche 1–4» schaltet die Runden frei (Runde 1 ab Woche 1, Runde 2 ab Woche 2, Runde 3 ab Woche 4) | Die drei angeleiteten Runden lassen sich im Gespräch durchspielen |
| Gestaltung | Ruhig, «Reflexionsheft»-Anmutung, Karten, mobile-first, helles und dunkles Farbschema | Wunsch: professionell, kein ChatGPT-Look |

## Funktionen

**Lehrperson**
- **Startseite:** Stand der drei Runden, aktueller Impuls, Knopf «Neue Notiz»
- **Infoblock:** Einführung ins Thema, jederzeit erreichbar
- **Fallbeispiel-Runden:** Runde 1 mit Wahl aus drei Fällen, Runde 2 mit einem Fall für alle, Runde 3 als Rückblick auf die eigenen Antworten aus Runde 1. Freitext und eine Einschätzungsskala
- **Notizbüchlein:** freie Notiz mit optionalen Leitfragen, Hinweis «keine Namen»
- **Impuls:** kurze Frage, aus der direkt eine Notiz entsteht
- **Meine Einträge:** alle eigenen Einträge chronologisch zum Nachlesen

**Auftraggeberin**
- Übersicht pro Lehrperson (Pseudonym, Runden erledigt, Anzahl Notizen)
- Alle Einträge lesen, nach Lehrperson filtern
- Export als CSV, das sich in Excel direkt öffnen lässt
- Liste der geplanten Impulse

## Bewusst weggelassen
Echtes Login, Server, Datenbank, Versand von Erinnerungen, Bearbeiten der Fragen in der Oberfläche. Das wird erst nach dem Feedback und den Anforderungen (#4) entschieden.

## Zum Besprechen
Gestrichelte Kästen «Zum Besprechen» stellen auf jeder Seite die offenen Fragen fürs Treffen (#2). Sie lassen sich in der Prototyp-Steuerung ausblenden.

## Prüfung
- `node --test tests/*.test.js`: reine Logik (Freischaltung der Runden, Trennung der Einträge pro Lehrperson, CSV-Export inkl. Schutz vor Formel-Injection)
- `node tests/e2e-prototyp.mjs`: Durchklicken in Headless-Chrome in Handy-Breite (390 px), beide Rollen, Datenschutz-Grenzen (fremde Einträge, Zugriff auf die Übersicht), HTML-Einschleusung, kein horizontales Scrollen, helles und dunkles Farbschema, Desktop-Breite
