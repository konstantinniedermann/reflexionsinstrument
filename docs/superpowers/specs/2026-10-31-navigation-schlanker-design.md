# Design: Navigation ohne Übersicht, Abmelden zurückgenommen

Grundlage: Rückmeldung zur Navigation nach [Bereichsfarben](2026-10-31-bereichsfarben-design.md) (#44). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Rückmeldung

1. Die Verwaltung braucht keine «Übersicht»: Über die farbige Navigation oben ist jede Funktion direkt erreichbar. Der Kurzbeschrieb jeder Funktion gehört stattdessen ganz oben auf ihre eigene Seite.
2. «Abmelden» ist zu prominent. Es gibt keinen Grund, sich abzumelden; man soll angemeldet bleiben.

## Entscheidung

### Übersicht entfällt

- Der Navigationspunkt «Übersicht» und die Seite verschwinden. `/verwaltung` leitet auf «Inhalte» weiter, damit alte Lesezeichen und die Anmeldung weiter funktionieren; nach der Anmeldung landet die Auftraggeberin direkt dort.
- «Inhalte» als Ziel, weil es der erste Punkt der Navigation ist und bis zum Start ihre Hauptarbeit. Während des Pilots ist «Einträge» einen Tipp entfernt. Eine Weiche nach Datum wäre unsichtbares Verhalten und wird nicht gebaut.
- Jede Seite der Navigation beginnt unter der Überschrift mit einem Satz, wofür sie da ist (aus den Karten der Übersicht übernommen, wo nötig ergänzt). Der Link «‹ Verwaltung» auf der Vorschau entfällt.

### Abmelden: verstecken, nicht weglassen

Ganz weglassen geht nicht: Meldet sich eine Lehrperson einmal auf einem geteilten Gerät an, zum Beispiel einem Schulcomputer, sähe die nächste Person dort ihre Einträge. Das verletzt die einzige Muss-Anforderung «Lehrpersonen sehen nichts voneinander». Darum bleibt die Funktion, aber unauffällig:

- Der Knopf im Kopf entfällt für alle Rollen. Der Name bleibt im Kopf stehen, damit sichtbar ist, wer angemeldet ist.
- Lehrpersonen: ganz unten auf der Info-Seite, als leiser Knopf mit dem Satz «Nur nötig auf einem geteilten Gerät, zum Beispiel einem Schulcomputer.»
- Verwaltung: ganz unten auf jeder Seite, als leiser Knopf. Die Verwaltung hat keine Info-Seite, und ein fester Ort am Seitenende ist leicht zu finden.
- «Angemeldet bleiben» ist bei der Anmeldung schon vorausgewählt und verlängert sich bei Nutzung; daran ändert sich nichts.
- Gast-Ansicht und Vorschau behalten ihren Knopf oben rechts («Anmelden» bzw. zurück zur Verwaltung), weil man dort hinaus will.

## Prüfung

- Tests: Weiterleitung von `/verwaltung`, Ziel nach der Anmeldung, fünf Navigationspunkte ohne «Übersicht», Kurzbeschrieb auf jeder Seite, kein Abmelden im Kopf, Abmelden auf der Info-Seite und am Ende der Verwaltungsseiten.
- E2E-Lauf: Abmelden über die neuen Orte, Bildschirmfotos Handy und Computer.
