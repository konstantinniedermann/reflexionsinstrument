# Reflexionsinstrument für Lehrpersonen

Eine einfache Anwendung, mit der Lehrpersonen zu mehreren Zeitpunkten ein Reflexionsinstrument ausfüllen und ein Tagebuch führen. Jede Lehrperson sieht nur ihre eigenen Einträge. Die Auswertung erfolgt pseudonymisiert durch die Projektverantwortliche.

## Stand

Die Anforderungen werden noch geklärt. Es gibt einen **klickbaren Wegwerf-Prototyp**, um Feedback zu holen. Er ist nicht die spätere Pilot-Version. Aufbau und Entscheidungen: [docs/prototyp.md](docs/prototyp.md).

- Online: https://konstantinniedermann.github.io/reflexionsinstrument/
- Lokal: `prototyp/index.html` im Browser öffnen (Doppelklick genügt)

Alle Texte im Prototyp sind Platzhalter. Eingaben bleiben im jeweiligen Browser.

## Prüfen

| Befehl | Prüft |
|---|---|
| `node --test tests/*.test.js` | Logik: Freischaltung der Runden, Trennung der Einträge, CSV-Export |
| `node tests/e2e-prototyp.mjs` | Durchklicken im Headless-Chrome in Handy-Breite, beide Rollen, Screenshots in `tests/.e2e/bilder/` |

Beides braucht nur Node (ab Version 22) und keine Dependencies. Die E2E-Prüfung braucht zusätzlich Google Chrome unter macOS und läuft nur lokal, nicht in der CI.

## Leitplanken

- Einfachheit vor Funktionsumfang, auf dem Handy bedienbar
- Datenschutz: minimal personenbezogene Daten, Pseudonyme, Hosting bevorzugt in der Schweiz oder der EU
