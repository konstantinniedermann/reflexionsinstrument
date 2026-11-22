# Design: Zusatzinfos und Fragen frei anordnen

Grundlage: Wunsch der Auftraggeberin vom 22.11.2026 (sinngemäss). Heute hängt jede Zusatzinfo an einer Frage («Zusatzinfo nach dieser Frage»). Sie möchte Informationsblöcke und Fragen unabhängig voneinander anordnen und die Reihenfolge später ändern können, zum Beispiel «zwei Fragen, eine Information, eine Frage». Die Lehrpersonen sollen erst weiterkommen, wenn die Fragen davor beantwortet sind. Die Entscheidungen hat Claude getroffen (Projektregel «Fragen selbst beantworten»). Löst die Zusatzinfo pro Frage aus dem [Design vom 21.11.](2026-11-21-mehrere-zusatzinfos-design.md) ab; dort war genau dieser Ansatz (B) als «nicht gebraucht» verworfen worden.

## Ziel

- Eine Runde ist eine Abfolge von **Fragen** und **Zusatzinfos** in beliebiger Reihenfolge. Das Fallbeispiel bleibt die Ausgangslage zuoberst.
- Die Auftraggeberin legt Zusatzinfos als eigene Bausteine an und verschiebt Fragen und Zusatzinfos frei gegeneinander.
- Die Sperre bleibt wie bisher: Eine Zusatzinfo erscheint erst, wenn alle Fragen davor beantwortet sind.
- Für die Lehrpersonen ändert sich bei bestehenden Inhalten nichts. Was die Auftraggeberin schon erfasst hat, steht danach an derselben Stelle.

Nicht Ziel: ein Assistent mit einer Seite pro Abschnitt, Sperren ohne Zusatzinfo, Ziehen mit dem Finger (Drag-and-drop), Bilder oder Anhänge.

## Ansätze

| Ansatz | Vorteil | Nachteil |
|---|---|---|
| A: wie bisher, Zusatzinfo hängt an einer Frage | Kein Umbau | Genau die Kopplung, die sie loswerden will: Wer eine Frage verschiebt, verschiebt die Info mit |
| **B: Zusatzinfo als eigener Baustein** (Tabelle `zusatzinfos`, gemeinsame Reihenfolge mit den Fragen der Runde) | Frei anordenbar, auch vor der ersten Frage oder mehrere hintereinander. Antworten, Export und Auswertung lesen weiter nur `fragen` und bleiben unberührt | Verschieben über zwei Tabellen, neue Seiten in der Maske, eine Migration |
| C: eine gemeinsame Tabelle für Fragen und Infos (neuer `typ` in `fragen`) | Eine Reihenfolge in einer Tabelle | Das `CHECK` auf `typ` lässt sich in SQLite nur per Neubau der Tabelle ändern, an der die Antworten hängen. Jede Stelle, die Fragen zählt (Marke «x von y», Export, Auswertung), müsste Infos ausfiltern |

**Gewählt: B.** Das ist, was sie beschreibt, und es lässt die Antworten unberührt.

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Wie bildet die Lehrpersonen-Seite Abschnitte? | Die Abfolge wird von oben gelesen. Eine Zusatzinfo beginnt einen neuen Abschnitt, wenn im laufenden schon eine Frage steht. Daraus folgt: Zusatzinfos vor der ersten Frage stehen sofort da, mehrere Zusatzinfos hintereinander erscheinen zusammen, eine Zusatzinfo am Schluss erscheint, wenn alle Fragen davor beantwortet sind. | Ihre Regel «erst weiter, wenn die Fragen davor beantwortet sind». Für bestehende Inhalte ergibt das genau die heutigen Abschnitte |
| Wann geht ein Abschnitt auf? | Unverändert: wenn alle Fragen des vorherigen beantwortet sind (Text, Skalawert oder Aufnahme; «Keine Angabe» zählt nicht), und er bleibt offen, sobald eine Frage in ihm oder danach eine Antwort hat | Bewährt, und die Regel liegt schon an einer Stelle |
| Sperre zwischen zwei Fragegruppen ohne Zusatzinfo? | Nein. Gesperrt wird nur vor einer Zusatzinfo. | In ihren Beispielen steht vor jedem neuen Abschnitt eine Information. Eine Sperre ohne neue Information schützt nichts. Braucht sie doch einen Halt, genügt eine kurze Zusatzinfo («Nun folgen weitere Fragen.») |
| «Weiter zur Zusatzinformation»: neue Seite? | Nein. Die Runde bleibt eine Seite, die Abschnitt für Abschnitt wächst. Nach dem Speichern springt sie zur neu sichtbaren Zusatzinfo. | So bleiben frühere Antworten sichtbar und änderbar. Ihr «Weiter» beschreibt die Abfolge, keinen Seitenwechsel |
| Was sieht die Lehrperson an der gesperrten Stelle? | Den heutigen Satz («Sobald du die Frage oben beantwortet und gespeichert hast, folgt eine Zusatzinformation mit weiteren Fragen.»), unter dem letzten sichtbaren Baustein. Die Zahl zählt nur Fragen | Unverändert |
| Wo legt sie eine Zusatzinfo an? | Auf der Seite der Runde: Knopf «Neue Zusatzinfo» neben «Neue Frage». Neue Bausteine kommen ans Ende. Das Formular hat ein Pflichtfeld «Zusatzinfo», formatiert wie das Fallbeispiel. Das Feld im Frageformular entfällt. | Ein Ort pro Baustein, wie bei den Fragen |
| Wie ordnet sie? | Die Seite der Runde zeigt unter dem Fallbeispiel den ganzen **Ablauf** als Karten: Fragen und Zusatzinfos gemischt, jede mit «Bearbeiten», «Löschen», «Nach oben», «Nach unten». Verschieben tauscht mit dem Nachbarn, egal welcher Art. | Bekannte Bedienung aus Infoblock und Fragen. Ziehen mit dem Finger ist auf dem Handy fehleranfällig und bräuchte JavaScript |
| Sieht sie, wann eine Zusatzinfo erscheint? | Ja, jede Info-Karte ist gelb wie bei den Lehrpersonen und trägt einen Vermerk: «Erscheint sofort beim Öffnen der Runde» (keine Frage davor) oder «Erscheint, sobald die Fragen davor beantwortet sind» | Sie sieht beim Ordnen, wo die Lehrpersonen anhalten |
| Löschen | Eine Zusatzinfo lässt sich immer löschen (an ihr hängen keine Antworten). Eine Frage löscht keine Info mehr mit. | Folgt aus der Trennung |
| Bestehende Inhalte | Migration 007 legt jede `fragen.zusatzinfo` als Baustein direkt nach ihrer Frage an und eine noch wartende `runden.zusatzinfo` (Runde ohne Frage) als Baustein der Runde. Die Reihenfolge wird pro Runde neu nummeriert, danach fallen beide Spalten weg. | Nichts geht verloren, nichts verschiebt sich. Der Sonderfall «wartende Zusatzinfo» verschwindet |
| Sprung nach dem Speichern | Anker `zusatzinfo-<Id der Zusatzinfo>` statt der Frage-Id | Die Id der Frage trägt nichts mehr |
| Gast und Vorschau | Gleiche Regel wie bisher | Unverändert |
| Platzhalter-Inhalte | Runden beschreiben einen `ablauf` aus Fragen und Zusatzinfos. Eine Runde zeigt das Beispiel «zwei Fragen, Zusatzinfo, Frage» | Entwicklung und Anleitung zeigen den neuen Ablauf |
| Export und Auswertung | Unverändert | Die Zusatzinfo ist Inhalt, keine Antwort |

## Umsetzung

- Migration 007: Tabelle `zusatzinfos (id, runde_id → runden ON DELETE CASCADE, inhalt, reihenfolge)`. Fragen bekommen pro Runde `reihenfolge = 2 × Rang`, die Zusatzinfo dahinter `2 × Rang + 1`, eine wartende Info `1`. Dann `ALTER TABLE … DROP COLUMN zusatzinfo` auf `fragen` und `runden` (SQLite ≥ 3.35, lokal und im Image erfüllt). Keine neue Dependency.
- `inhalte.py`: `ablauf(db, runde_id)` liefert die gemischte Liste. Anlegen nimmt die nächste Nummer über beide Tabellen. Verschieben und Löschen nummerieren den ganzen Ablauf der Runde neu.
- `seiten_lehrperson.py`: Die Zeilen werden zu Bausteinen (Frage mit Feld und Wert, oder Zusatzinfo). Nur die Bildung der Abschnitte ändert sich, `offene_abschnitte` zählt weiter nur Fragen.

## Prüfung

- Tests: Migration mit Altdaten (Info nach Frage 1 und nach Frage 3, wartende Info, Runde ohne Info) ergibt dieselbe Abfolge. Abschnittsregel: Info vor der ersten Frage, zwei Infos hintereinander, Info am Schluss, «zwei Fragen, Info, Frage». Verschieben über die Art hinweg, Löschen nummeriert neu. Maske: Info anlegen, bearbeiten, löschen, Vermerk. Die bestehenden Tests zur Zusatzinfo bleiben als Netz bestehen und werden nur auf den neuen Baustein umgestellt.
- E2E und Handy-Ansicht (390 px, CDP-Emulation): Runde «zwei Fragen, Zusatzinfo, Frage» in allen Stufen, Maske mit gemischtem Ablauf.
- Nach dem Merge: Migration auf einer Kopie der Prod-Datenbank mit Vergleich der Abfolge vorher/nachher, Deploy von `origin/main`.
- Anleitung für die Auftraggeberin (`intern/`) neu bauen.
