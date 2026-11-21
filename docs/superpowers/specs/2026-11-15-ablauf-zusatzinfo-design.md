# Design: Zusatzinfo pro Runde, unterstützende Frage im Tagebuch, Blocksatz

> Die eine Zusatzinfo pro Runde ist abgelöst durch [mehrere Zusatzinfos pro Runde](2026-11-21-mehrere-zusatzinfos-design.md).

Grundlage: Rückmeldung der Auftraggeberin vom 15.11.2026 (sinngemäss, Inhalte stehen nicht im Repo). Die Entscheidungen hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Rückmeldung

1. Die Hinweistexte (Begrüssung, Hinweise) sehen mit Flattersatz «komisch» aus; sie wünscht Blocksatz.
2. Ablauf einer Runde in den Wochen 1–3: Am Montag erscheint ein Fallbeispiel, dazu wird die erste Frage beantwortet. Danach kommt eine **Zusatzinfo**, die erst erscheinen soll, wenn die erste Frage bearbeitet ist. Nach der Zusatzinfo folgen zwei weitere Fragen.
3. Woche 4 hat zwei Reflexionsfragen, kein Fallbeispiel.
4. Im Tagebuch gibt es eine **unterstützende Frage**, die man freiwillig aufklappen kann oder nicht.

Punkt 3 und das wöchentliche Freischalten am Montag deckt die Pilot-Version schon ab (Runde ohne Fallbeispiel, Freischaltdatum pro Runde).

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Wo gilt Blocksatz? | Alle formatierten Fliesstexte der Lehrpersonen-, Gast- und Vorschau-Ansicht: Begrüssung, Hinweise, Infoblock, Fallbeispiel, Zusatzinfo. Mit automatischer Silbentrennung (Seite ist `lang="de"`). Nicht: Fragen, Knöpfe, Karten, Eingabemaske | Einheitliches Bild der Lesetexte. Ohne Silbentrennung reisst Blocksatz in schmalen Handy-Spalten grosse Lücken |
| Wie wird die Zusatzinfo erfasst? | Ein Textfeld «Zusatzinfo (freiwillig)» bei der Runde, unter dem Fallbeispiel, mit Formatierung wie das Fallbeispiel | Gleiche Bedienung wie das Fallbeispiel |
| Wo steht sie? | Fest nach der **ersten** Frage der Runde (nach Reihenfolge). Die übrigen Fragen folgen danach | Genau ihr Ablauf. Eine frei wählbare Position bräuchte eine Einstellung pro Frage, die sie nicht verlangt hat |
| Wann erscheint sie? | Sobald die erste Frage eine gespeicherte Antwort hat (Text, Skalawert oder Aufnahme) oder eine spätere Frage schon beantwortet ist. Bis dahin sind Zusatzinfo und die weiteren Fragen ausgeblendet; an ihrer Stelle steht ein ruhiger Satz, dass nach dem Speichern eine Zusatzinformation mit weiteren Fragen folgt | Ihre Vorgabe «erst, wenn die Ausgangslage bearbeitet wurde». Die zweite Bedingung verhindert, dass schon gegebene Antworten verschwinden, wenn die erste gelöscht wird |
| Was heisst «Keine Angabe» bei einer Skala als erster Frage? | Gilt nicht als beantwortet | Wie bei der Marke «Angefangen, x von y» |
| Wohin springt die Seite nach dem Speichern? | Wurde die Zusatzinfo durch dieses Speichern sichtbar, zur Zusatzinfo; sonst wie bisher | Die Lehrperson sieht sofort, was neu da ist |
| Runde ohne Zusatzinfo | Alle Fragen auf einmal, wie bisher | Woche 4 und alles, was sie schon erfasst hat, bleibt unverändert |
| Gast und Vorschau | Gleiche Regel; als «beantwortet» gilt dort der eben abgeschickte (nicht gespeicherte) Wert | So lässt sich der Ablauf ohne Konto und in der Vorschau durchspielen |
| Verwaltung | Die Detailseite der Runde zeigt die Zusatzinfo unter dem Fallbeispiel, mit dem Vermerk «erscheint nach Frage 1» | Sie sieht ihren ganzen Inhalt an einem Ort |
| Export | Unverändert | Die Zusatzinfo ist Inhalt, keine Antwort |
| Unterstützende Frage im Tagebuch | Die bisherigen «Leitfragen» heissen überall «Unterstützende Fragen». Sie erscheinen nicht mehr als eigene Auswahl, sondern beim freien Schreiben und beim freien Sprechen als zugeklapptes Feld «Unterstützende Frage» (bei mehreren: «Unterstützende Fragen») über dem Eingabefeld | Ihre Beschreibung: freiwillig aufklappen oder nicht. Eine eigene Auswahl daneben wäre ein zweiter Weg zum selben Ziel |
| Was wird gespeichert? | Der Eintrag bleibt «frei» bzw. «Aufnahme». Ob jemand die Frage aufgeklappt hat, wird nicht erfasst | Datensparsamkeit; für die Interviews nicht nötig |
| Alte Einträge «Zur Leitfrage» | Bleiben lesbar und exportierbar, Anzeige «Zur unterstützenden Frage» | Auf Prod gibt es keine, Testdaten können sie haben |

## Umsetzung

- Migration 005: Spalte `zusatzinfo TEXT` in `runden`. Keine neue Tabelle, keine neue Dependency.
- Die Regel «Zusatzinfo sichtbar?» liegt an einer Stelle im Code und wird für Lehrperson, Gast und Vorschau gleich verwendet.
- Die Routen zum Anlegen eines Eintrags «zur Leitfrage» entfallen; Anzeige und Export alter Einträge bleiben.
- Blocksatz nur per Stylesheet (`text-align: justify; hyphens: auto` für `.formatiert` in der Lehrpersonen-Ansicht).

## Prüfung

- Tests: Regel für die Sichtbarkeit (ohne Antwort, mit Antwort auf Frage 1, nur spätere Antwort, Skala «Keine Angabe», Aufnahme), Runde ohne Zusatzinfo, Gast und Vorschau, Eingabemaske speichert und zeigt die Zusatzinfo, Tagebuch zeigt die unterstützende Frage zugeklappt, die alte Leitfragen-Route gibt 404.
- Handy-Ansicht (390 px, CDP-Emulation): Runde vor und nach dem Speichern von Frage 1, Startseite mit Blocksatz, Tagebuch mit auf- und zugeklappter Frage.
- Nach dem Merge Deploy und Nachweis auf fly.io.
