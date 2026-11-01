# Design: Drei Gestaltungsmuster zur Auswahl

Grundlage: neue Rückmeldung der Auftraggeberin zur Gestaltung, Weiterführung von [Bereichsfarben](2026-10-31-bereichsfarben-design.md). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Rückmeldung

1. Gestaltung angelehnt an eine Website, die ihr gefällt (wie in #20 wird sie hier nicht genannt).
2. Matte Farben statt kräftiger.
3. Jedes Register (jeder Navigationspunkt) hat eine eigene Farbe. Ist ein Register offen, ist der Seitenhintergrund ein weicher Ton dieser Farbe, die Registerfarbe bleibt aber erkennbar.
4. Die Navigation aus dem ersten Prototyp bleibt, damit die Bedienung übersichtlich bleibt.

## Ziel

Die Auftraggeberin probiert auf dem Handy drei Muster aus und entscheidet sich für eines. Danach wird das gewählte Muster in die Pilot-Version übernommen (eigener Schritt). Die Muster sind Wegwerf-Prototypen.

## Merkmale der Vorlage

- weisser Grund, feine schwarze Trennlinien statt Schatten
- fette, eng gesetzte Grotesk-Schrift für Titel, kleine Serifenschrift für Nebentexte
- Knöpfe als umrandete Pillen mit dünnem schwarzem Rand
- Listen als ganze Zeilen in matten Pastelltönen, durch Linien getrennt

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Was ist ein «Register»? | Die vier Punkte der unteren Navigation: Start, Tagebuch, Einträge, Info. Die Runden bekommen zusätzlich eine eigene Farbe, ihre Seiten zählen zum Register Start | So steht es in der Navigation; Runden sind der Kern des Instruments und wurden bisher farbig erkannt |
| Navigation | Gleiche Punkte, gleiche Reihenfolge, gleiche Symbole, unten fest wie im ersten Prototyp und im Pilot. Die Muster ändern nur das Aussehen | Wunsch 4 |
| Farbe der Karten | Eine Karte trägt die Farbe des Registers, in das sie führt (Impuls führt ins Tagebuch, also Tagebuch-Farbe) | Weniger Farben, die Zuordnung bleibt lernbar |
| Hintergrund | Ganze Seite im weichen Ton der Registerfarbe (rund ein Drittel Farbe, Rest Weiss); der aktive Navigationspunkt in der vollen Farbe | Wunsch 3 |
| Drei Muster | **A «Spielplan»**: am nächsten an der Vorlage, Zeilen mit Linien statt Karten. **B «Register»**: weisse Karten wie im Pilot, Navigation als farbige Registerreiter. **C «Plakat»**: grosser Titel auf einem Farbband, kräftigere matte Töne | Echte Auswahl: nah an der Vorlage, nah am Gewohnten, mutiger |
| Schrift | Systemschriften (Helvetica/Arial, Georgia), keine Webfont | Wie #20: kein Abruf bei Dritten |
| Umfang | Nur die Sicht der Lehrpersonen: Start, eine Runde, Tagebuch, ein Tagebucheintrag, Einträge, Info. Speichern zeigt nur einen Hinweis | Dort wirkt die Gestaltung; die Verwaltung übernimmt später dieselben Regeln |
| Vergleichen | Oben eine schmale Leiste «Muster A/B/C», die auf derselben Seite das Muster wechselt; Einstieg über eine Auswahlseite | Direkter Vergleich auf dem Handy |
| Farbschema | Nur hell | Muster zum Entscheiden; das dunkle Schema folgt bei der Übernahme |
| Bereitstellung | GitHub Pages unter `/design/` neben dem ersten Prototyp (Ordner `prototyp/design/`) | Bestehender Weg, kostenlos, per Link auf dem Handy |
| Inhalte | Selbst geschriebene Platzhalter | Öffentliches Repo |

Schrift auf allen Farbflächen ist schwarz; alle Farbpaare erreichen mindestens WCAG AA (4.5 : 1).

## Prüfung

- Durchklicken aller Seiten in allen drei Mustern in Handy-Breite (390 px) per CDP-Emulation, Bildschirmfotos, kein horizontales Scrollen.
- Aufruf der veröffentlichten Seite nach dem Deploy.
