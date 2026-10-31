# Design: Gestaltung in Anlehnung an eine Vorlage der Auftraggeberin (#20)

Weiterentwickelt in [Bereichsfarben als Navigationshilfe](2026-10-31-bereichsfarben-design.md): Farbe vollflächig statt punktuell, Balken und Etiketten entfallen.

Grundlage: [Anforderungen](../../anforderungen.md) (Abschnitt «Gestaltung»: Bereiche mit Farben kennzeichnen), Issue #20. Die Auftraggeberin hat eine Website genannt, die ihr gefällt, und wünscht «eine Anlehnung, eine Tendenz, nichts Aufwendiges». Zur Tonalität der festen Texte gab es keinen Input; sie bleiben, wie sie sind. Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Was die Vorlage ausmacht

Die Vorlage wird hier bewusst nicht genannt und nicht im Detail beschrieben (öffentliches Repo). Ihre Merkmale:

- hellgrauer Seitenhintergrund, schwarzer Text
- eine einzige serifenlose Grotesk-Schrift, Überschriften fett und eng gesetzt
- Flächen mit stark gerundeten Ecken, keine Schatten
- Knöpfe und Navigationspunkte als Pillen
- jeder Navigationspunkt hat eine eigene, flache, kräftige Farbe

## Entscheidung

Übernommen wird die **Formensprache und die Farbzuordnung pro Bereich**, nicht die Lautstärke. Die Projektvorgabe «ruhig, professionell» bleibt massgebend.

| Übernommen | Nicht übernommen |
|---|---|
| Hintergrund `#f1f1f1`, weisse Karten, schwarzer Text | Fotos, Schmuckschrift im Titel |
| Helvetica/Arial für alles (die Serifenschrift entfällt) | Sehr grosse Schriftgrössen |
| Grosse Radien (Karten 22 px), Knöpfe und Marken als Pillen | Bewegte, gedrehte Navigation |
| Hauptknopf schwarz mit weisser Schrift | Farbe als Seitenhintergrund; Farbe steht nur auf einzelnen Karten und Elementen |
| Eine Farbe pro Bereich, angelehnt an die Palette der Vorlage | |

### Bereichsfarben

Die Farbe kennzeichnet: aktiver Punkt der unteren Navigation, Bereichsetikett, Impuls-Karte, offene Runde, Marken der Einträge, Rand des Fallbeispiels und der Leitfrage. Schrift darauf ist schwarz (bzw. weiss auf Schwarz und Blau-Violett).

| Bereich | Farbe |
|---|---|
| Start | Schwarz `#000000` (dunkles Schema: hell) |
| Runden | Gelb `#ffe100` |
| Tagebuch (auch Leitfragen) | Rosa `#e77cb0` |
| Impulse | Grün `#7bc96f`, bewusst hell gewählt, damit schwarze Schrift AA erreicht |
| Meine Einträge | Blau-Violett `#5949f4` (Schrift weiss) |
| Info | Grau `#d9d9d9` |

Auf den Seiten einer Runde trägt der Start-Punkt der Navigation die Runden-Farbe, passend zum Balken über dem Inhalt.

Im dunklen Farbschema bleiben die Bereichsfarben gleich, Hintergrund und Karten werden dunkel (`#111` / `#1e1e1e`), der Hauptknopf wird hell mit dunkler Schrift.

## Umsetzung

- Alle Farben und Radien als Variablen in `:root` von `app/static/css/style.css`. Jede Seite trägt schon die Klasse `bereich--<name>` am `main`; dort wird `--bereich` gesetzt.
- Untere Navigation: Jeder Punkt trägt seine Bereichsklasse; der aktive Punkt zeigt das Symbol in einer Pille in der Bereichsfarbe.
- Startseite: Die Überschriften «Runden» und «Tagebuch» werden zu Etiketten in Bereichsfarbe, die Impuls-Karte hat die Impuls-Farbe, die Info-Karte das Grau.
- Unterseiten: Ein kurzer Balken in der Bereichsfarbe über dem Inhalt zeigt, wo man ist.
- Verwaltung: übernimmt Schrift, Radien und Knöpfe über die gemeinsamen Variablen; die Marken der Einträge tragen die Bereichsfarben wie bei den Lehrpersonen.
- Kein JavaScript, keine Webfont (Helvetica/Arial sind auf allen Geräten vorhanden, kein Abruf bei Dritten), keine neue Dependency.

## Prüfung

- Ein Test liest die Farbvariablen beider Farbschemata aus dem Stylesheet und prüft die Paare aus Schrift- und Flächenvariable auf WCAG AA (mindestens 4.5 : 1). Fest eingetragene Farben (Schwarz/Weiss auf Bereichsfarben) und Fokus-Rahmen sind von Hand nachgerechnet.
- E2E-Lauf mit Bildschirmfotos in Handy- und Computeransicht, hell und dunkel.
