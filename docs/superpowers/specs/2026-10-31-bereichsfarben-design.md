# Design: Bereichsfarben als Navigationshilfe, näher an der Vorlage

Grundlage: [Gestaltung (#20)](2026-10-31-gestaltung-design.md), Anforderungen (Abschnitt «Gestaltung»: Bereiche mit Farben kennzeichnen, das macht die Navigation einfacher). Neuer Wunsch: Die App soll bunter und näher an der Vorlage sein, die Farben sollen bei der Navigation helfen, pro Bereich. Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Ausgangslage

#20 hat die Formensprache übernommen, die Farbe aber nur punktuell eingesetzt: ein kurzer Balken über dem Inhalt, die Pille des aktiven Navigationspunkts, kleine Etiketten. Fast alle Flächen sind weiss. Die Vorlage arbeitet anders:

- Jede Unterseite trägt oben ihren Namen als grosse Pille in der Farbe des Bereichs.
- Jeder Navigationspunkt hat dauerhaft seine Farbe, nicht erst, wenn er aktiv ist; der aktive trägt einen Rahmen.
- Listen bestehen aus vollflächig farbigen Blöcken mit schwarzer Schrift.

## Entscheidung

Regel: **Was zu einem Bereich führt oder ihn kennzeichnet, ist vollflächig in seiner Farbe. Formulare und lange Lesetexte bleiben auf Weiss.** Damit wird die App deutlich bunter, Eingabefelder und der Infoblock bleiben aber ruhig lesbar. Die Farben bleiben dieselben wie in #20, sodass «Gelb = Runden, Rosa = Tagebuch, Grün = Impulse, Blau-Violett = Einträge, Grau = Info» überall gilt, auch in der Verwaltung.

### Lehrpersonen

| Ort | Vorher | Neu |
|---|---|---|
| Untere Navigation | nur aktiver Punkt farbig | alle Symbole in ihrer Bereichsfarbe; der aktive mit Ring und fetter Beschriftung |
| Kopf der Unterseiten | kurzer Balken | Pille mit dem Bereichsnamen («Runden», «Tagebuch», «Meine Einträge», «Info»); wo die Überschrift gleich lautet, wird die Überschrift selbst zur Pille |
| Startseite | weisse Karten mit kleinem Etikett | Runden-Karte gelb, Tagebuch-Karte rosa, Impuls grün, Info grau, je vollflächig |
| Runde | Fallbeispiel weiss mit gelbem Rand | Fallbeispiel vollflächig gelb |
| Tagebuch-Auswahl | weisse Karten | Schreiben, Sprechen und Leitfragen rosa, Impuls grün |
| Tagebucheintrag zu einer Leitfrage | weisse Karte mit rosa Rand | rosa Fläche |
| Meine Einträge | weisse Karten, farbige Marke | ganze Karte in der Farbe der Art (Tagebuch rosa, Impuls grün, Runde gelb) |

### Verwaltung

| Ort | Vorher | Neu |
|---|---|---|
| Navigation | unterstrichene Links, kein aktiver Punkt | Pillen in eigener Farbe, aktiver Punkt mit Ring und `aria-current` |
| Inhalte-Übersicht | weisse Karten | Infoblock grau, Runden gelb, Leitfragen rosa, Impulse grün; Allgemein und Hinweise bleiben weiss |

Farben der Verwaltungsnavigation: Übersicht Schwarz, Inhalte Orange `#d35d31`, Einträge Blau-Violett (wie «Meine Einträge»), Vorschau Grau, Zugänge Blau `#1536a2`, Benachrichtigung Grün (Erinnerungen gehören zu den Impulsen). Orange und Blau stammen aus der Palette der Vorlage; Orange trägt schwarze, Blau weisse Schrift.

### Bewusst nicht

- Kein farbiger Seitenhintergrund, keine Fotos, keine bewegte Navigation (wie in #20).
- Der Infoblock bleibt weiss: lange Texte auf Grau würden im dunklen Schema blenden.
- Rot aus der Vorlage wird nicht verwendet, es steht in der App für Fehler.

## Umsetzung

- Neue Hilfsklasse `flaeche`: Hintergrund `--bereich`, Schrift `--auf-bereich`. Innerhalb der Fläche werden Schrift-, gedämpfte und Akzentfarbe auf `--auf-bereich` umgestellt, damit Text, Pfeile, Fokus-Rahmen und Knöpfe darauf lesbar bleiben (Knopf: Schrift in der Bereichsfarbe auf Schwarz bzw. Weiss). Marken in der Fläche werden weiss.
- Die Farbe kommt wie bisher aus der Klasse `bereich--<name>`; neu dazu `bereich--impuls` und für die Verwaltung `bereich--inhalte` und `bereich--zugaenge` (Vorschau nutzt `bereich--info`, Benachrichtigung `bereich--impuls`).
- Bereichsnamen der Pille in einer Zuordnung im Rahmen der Lehrpersonen-Seiten, nicht im CSS (Text gehört nicht ins Stylesheet).
- Aktiver Punkt der Verwaltungsnavigation aus dem Pfad der Anfrage, ohne Änderung an den Routen.
- Kein JavaScript, keine neue Dependency.

## Prüfung

- Kontrasttest um die neuen Farbpaare erweitern (Orange mit schwarzer, Blau mit weisser Schrift).
- Tests: Seitenetikett auf den Unterseiten, aktiver Punkt der Verwaltungsnavigation, Farbklassen auf den Einträgen.
- E2E-Lauf mit Bildschirmfotos in Handy- und Computeransicht, hell und dunkel.
