# Design: Muster B in die Pilot-Version übernehmen

Grundlage: [Drei Gestaltungsmuster](2026-11-01-design-muster-design.md). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Rückmeldung

1. Die Auftraggeberin wählt Muster B «Register».
2. «Impuls der Woche» und «Tagebuch» sollen zwei unterschiedliche Farbtöne haben, damit klar ist, dass es zwei verschiedene Register sind. Im Muster trug der Impuls die Tagebuch-Farbe.
3. Der Titel aus Muster B gefällt: der Seitenname als grosse Pille in der Registerfarbe.
4. Die Registerauswahl unten aus Muster B gefällt: farbige Reiter, der offene höher und mit schwarzer Kante.

## Entscheidungen

| Frage | Entscheidung | Begründung |
|---|---|---|
| Farben | Matte Töne aus Muster B: Start `#d8d2c4`, Runden `#e6d097`, Tagebuch `#e1b2b4`, Einträge `#b9c7df`, Info `#bdd2bf`. Schrift darauf schwarz | Gewähltes Muster |
| Farbe Impuls | Eigener matter Lavendelton `#cdc0e2` | Klar unterscheidbar von Tagebuch (Rosa) und Einträge (Blau); Grün ist schon Info, Gelb die Runden |
| Was trägt die Impuls-Farbe? | Die Impuls-Karte auf der Startseite, «Zum Impuls dieser Woche» in der Tagebuch-Auswahl, der Impuls über dem Schreibfeld und Einträge zum Impuls | Überall, wo der Impuls vorkommt; damit gilt die Regel aus [Bereichsfarben](2026-10-31-bereichsfarben-design.md) wieder: eigene Sache, eigene Farbe |
| Seitenhintergrund | Weicher Ton der Registerfarbe (38 % Farbe, Rest Weiss), wie im Muster. Seiten zu einer Runde tragen den Runden-Ton | Muster B |
| Navigation | Vier Reiter wie im Muster B, unten fest; jeder dauerhaft in seiner Farbe, der offene höher mit schwarzer Oberkante und fetter Beschriftung. Auf Runden-Seiten trägt der Reiter «Start» die Runden-Farbe (wie bisher) | Wunsch 4 |
| Titel | Seitenname als Pille in der Registerfarbe (besteht schon, Grösse wie im Muster) | Wunsch 3 |
| Karten | Weisse Karten ohne Rand, stark gerundet; Karten, die in ein Register führen, vollflächig in dessen Farbe. Knöpfe auf Farbflächen weiss mit schwarzem Rand | Muster B |
| Meine Einträge | Weisse Karte mit breitem Farbstreifen links und farbiger Marke in der Farbe der Art (Tagebuch, Impuls, Runde) | Muster B; auf dem blauen Grund der Einträge-Seite bleiben die Einträge so ruhig lesbar |
| Runden auf der Startseite | Zeilen durch feine Linien getrennt auf der gelben Karte, die offene Runde mit schwarzer Marke | Muster B |
| Verwaltung | Übernimmt Farben, Karten und Knöpfe. Hintergrund im Start-Ton. Die farbigen Pillen oben bleiben; Orange (Inhalte) und Blau (Zugänge) werden matt (`#e6bb97`, `#a9cdc6` Blaugrün, beide mit schwarzer Schrift) | Einheitliches Bild; das kräftige Blau stünde sonst neben dem matten Einträge-Blau |
| Dunkles Farbschema | Hintergrund im dunklen Ton der Registerfarbe, Karten dunkel, Farbflächen und Reiter matt mit schwarzer Schrift | Das Muster war nur hell; so bleibt die Registerfarbe auch dunkel erkennbar |
| Schrift | Systemschriften wie bisher | Kein Abruf bei Dritten |

### Bewusst nicht

- Kein fünfter Reiter für den Impuls: Die Navigation bleibt bei vier Punkten (Wunsch 4 aus dem Muster). Der Impuls ist eine eigene Farbe, kein eigener Navigationspunkt.
- Der Titel der App im Kopf bleibt so, wie er in der Eingabemaske steht (das Muster schrieb ihn klein, das war Platzhalter).

## Umsetzung

- Nur Stylesheet und Vorlagen; kein JavaScript, keine neue Dependency.
- Der Bereich der Seite kommt als Klasse an `<body>`, damit Hintergrund und Reiter ihn kennen.
- Die Farbe des Hintergrunds wird mit `color-mix()` aus der Registerfarbe gemischt; ältere Browser zeigen den neutralen Grund.

## Prüfung

- Kontrasttest mit den neuen Farben (hell und dunkel).
- Tests: Klasse am `<body>`, Einträge mit Farbstreifen der Art, Impuls-Farbe überall, wo der Impuls vorkommt.
- E2E-Lauf mit Bildschirmfotos in Handy-Breite (390 px, CDP-Emulation), hell und dunkel, und Computeransicht.
