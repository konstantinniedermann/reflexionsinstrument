# Design: Mehrere Zusatzinfos pro Runde

Grundlage: Wunsch der Auftraggeberin vom 21.11.2026. Sie möchte zum Fall selbst mehr Zusatzinfos ergänzen können, im Ablauf «Fall – Fragen – Zusatzinfo – Fragen – Zusatzinfo – Fragen». Die Entscheidungen hat Claude getroffen (Projektregel «Fragen selbst beantworten»). Löst die eine Zusatzinfo pro Runde aus dem [Design vom 15.11.](2026-11-15-ablauf-zusatzinfo-design.md) ab.

## Ziel

- Eine Runde kann beliebig viele Zusatzinfos haben, jede an einer Stelle zwischen den Fragen.
- Jede Zusatzinfo erscheint erst, wenn die Fragen davor beantwortet sind. So beantworten die Lehrpersonen die Fragen unbeeinflusst von der nächsten Information.
- Was sie schon erfasst hat (eine Zusatzinfo nach Frage 1), bleibt unverändert erhalten.
- Keine Lehrperson darf feststecken. Der Hinweis sagt genau, was zu tun ist.

Nicht Ziel: eine Zusatzinfo vor Frage 1 (dafür gibt es das Fallbeispiel), Bilder oder Anhänge, eigene Freischaltdaten pro Zusatzinfo.

## Ansätze

| Ansatz | Vorteil | Nachteil |
|---|---|---|
| **A: Zusatzinfo hängt an einer Frage** («erscheint nach dieser Frage»), Spalte `fragen.zusatzinfo` | Ihr Muster ist immer «Fragen, dann Info». Die Reihenfolge der Fragen trägt die Info mit, dazu kommt nur eine Spalte. Der Bestand passt 1:1 (Info nach Frage 1). | Wer eine Frage verschiebt oder löscht, verschiebt oder löscht ihre Info mit. Die Maske muss das sagen. |
| B: Zusatzinfo als eigenes Element in der Reihenfolge der Runde (eigene Tabelle, gemeinsame Reihenfolge mit den Fragen) | Frei platzierbar, auch vor Frage 1 | Verschieben über zwei Tabellen, neue Seiten in der Maske, deutlich mehr Code für einen Fall, den sie nicht braucht |
| C: Tabelle `zusatzinfos` mit Stellung «nach Frage Nr. n» | Info unabhängig von einer bestimmten Frage | Nach dem Verschieben oder Löschen einer Frage steht die Info stillschweigend bei einer anderen Frage |

**Gewählt: A.** Am einfachsten für sie: Sie schreibt die Info direkt bei der Frage, nach der sie kommen soll.

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Wo erfasst sie eine Zusatzinfo? | Im Formular der Frage: Feld «Zusatzinfo nach dieser Frage (freiwillig)», formatiert wie das Fallbeispiel. Das Feld im Formular der Runde entfällt. | Ein Ort pro Info, direkt bei ihrer Stelle |
| Wie sieht sie den Ablauf? | Die Detailseite der Runde zeigt unter jeder Frage-Karte deren Zusatzinfo, mit dem Vermerk «erscheint, sobald die Fragen davor beantwortet sind» | Der ganze Ablauf auf einer Seite |
| Abschnitte | Die Zusatzinfos teilen die Fragen einer Runde in Abschnitte: Abschnitt 1 = Fragen bis zur ersten Info. Jeder weitere Abschnitt = eine Info und die Fragen bis zur nächsten. | Ihr Ablauf |
| Wann geht ein Abschnitt auf? | Wenn der vorherige offen ist und **alle** seine Fragen beantwortet sind (Text, Skalawert oder Aufnahme; «Keine Angabe» zählt nicht). Er bleibt offen, sobald irgendeine Frage in ihm oder danach eine gespeicherte Antwort hat. | «Alle» verhindert, dass die Info sichtbar wird, bevor die Fragen davor unbeeinflusst beantwortet sind. Bei einer einzelnen Frage davor ist das genau die bisherige Regel. Die zweite Bedingung verhindert, dass gegebene Antworten verschwinden, wenn eine frühere gelöscht wird. |
| Was sieht die Lehrperson an der ersten geschlossenen Stelle? | Einen ruhigen Satz: «Sobald du die Frage oben beantwortet und gespeichert hast, folgt eine Zusatzinformation mit weiteren Fragen.» Bei mehreren Fragen im Abschnitt: «… alle Fragen oben …». Ohne Fragen danach: «… folgt eine Zusatzinformation.» Weitere geschlossene Abschnitte bleiben ganz verborgen. | Sie weiss genau, was zu tun ist, und sieht nicht, wie viel noch kommt |
| Feststecken | Wer eine Frage nicht beantworten mag, muss etwas schreiben oder einen Wert wählen. «Keine Angabe» schaltet nichts frei. | Bewusst in Kauf genommen. Die Auftraggeberin könnte das anders sehen, darum steht es im Bericht. |
| Info nach der letzten Frage | Erlaubt, erscheint am Schluss als abschliessende Information | Kein Grund, es zu verbieten |
| Sprung nach dem Speichern | Zur ersten Zusatzinfo, die durch dieses Speichern aufging (Anker `zusatzinfo-<Frage-Id>`), sonst wie bisher | Die Lehrperson sieht sofort, was neu da ist |
| Gast und Vorschau | Gleiche Regel; als beantwortet gilt der eben abgeschickte Wert. So lässt sich der Ablauf Abschnitt für Abschnitt durchspielen, solange die Werte im Formular mitgeschickt werden. | Wie bisher |
| Bestehende Zusatzinfos | Migration 006 verschiebt jede Zusatzinfo einer Runde zu deren erster Frage, also an dieselbe Stelle wie bisher. Hat die Runde noch keine Frage, bleibt die Info bei der Runde stehen. Die Detailseite zeigt sie mit dem Vermerk «erscheint, sobald die Runde eine Frage hat», und das Formular der ersten neuen Frage zeigt sie vorbelegt. Es gilt, was dort abgeschickt wird; ein bewusst geleertes Feld verwirft sie. | Nichts von dem, was sie schon erfasst hat, geht verloren oder verschiebt sich |
| Löschen einer Frage mit Zusatzinfo | Die Löschseite sagt, dass die Zusatzinfo mitgelöscht wird | Keine Überraschung |
| Platzhalter-Inhalte | Zusatzinfos stehen bei den Fragen; Runde 1 bekommt zwei, damit der Ablauf sichtbar ist | Entwicklung und Anleitung zeigen den neuen Ablauf |
| Export und Auswertung | Unverändert | Die Zusatzinfo ist Inhalt, keine Antwort |

## Umsetzung

- Migration 006: `fragen.zusatzinfo TEXT`. Dazu ein `UPDATE`, das `runden.zusatzinfo` zur ersten Frage (kleinste `reihenfolge`, dann `id`) kopiert und bei der Runde leert. Keine neue Tabelle, keine neue Dependency.
- Die Regel liegt an einer Stelle (`seiten_lehrperson.py`): Abschnitte bilden und die Zahl der offenen Abschnitte bestimmen. Lehrperson, Gast, Vorschau, das Speichern von Antworten und das Speichern einer Aufnahme verwenden sie gleich.
- Das Formular der ersten Frage zeigt eine wartende Zusatzinfo vorbelegt; `lege_frage_an` leert sie danach bei der Runde.

## Prüfung

- Tests: Migration mit Altdaten (Runde mit Info und Fragen, Runde mit Info ohne Fragen), Abschnittsregel (keine Antwort, ein Teil des Abschnitts, ganzer Abschnitt, Skala «Keine Angabe», Aufnahme, spätere Antwort hält offen), Sprung zur neu geöffneten Info, Runde ohne Zusatzinfo unverändert, Gast und Vorschau, Eingabemaske speichert und zeigt die Info bei der Frage, Löschseite nennt die Info.
- Handy-Ansicht (390 px, CDP-Emulation): Runde mit zwei Zusatzinfos in allen drei Stufen.
- Nach dem Merge: Kopie der Prod-Datenbank, Deploy von `origin/main`, Nachweis, dass die bestehenden Zusatzinfos bei Frage 1 stehen.
- Anleitung für die Auftraggeberin (`intern/`) neu bauen.
