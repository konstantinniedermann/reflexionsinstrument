# Beobachtungen (Posteingang für Befunde ausserhalb des Scopes)

Hier landen Befunde, die beim Arbeiten auffallen, aber nicht zum aktuellen Issue gehören.

- **Eintragen** (Claude, ohne Rückfrage): neuer Eintrag ans Ende von «Offen», Aufbau wie unten. Passendes **Thema** aus den vorhandenen Einträgen übernehmen statt ein neues zu erfinden.
- **Auswerten** mit dem Skill `beobachtungen-auswerten`. Wann, entscheidet Koschi.
- **Ein Issue** entsteht daraus nur mit ausdrücklicher Zustimmung (Regeln in `../CLAUDE.md`).
- Das Repo ist öffentlich: keine vertraulichen Inhalte in Einträgen.

Letzte Auswertung: 31.10.2026 (19 Einträge, alle abgeschlossen)

## Offen

## Ausgewertet am 31.10.2026

19 Einträge, alle abgeschlossen. Massstab: Der Pilot ist befristet (vier Wochen, fünf Lehrpersonen) und soll mit wenig weiterem Aufwand fertig werden. Was kein falsches Verhalten für Lehrpersonen oder Auftraggeberin bedeutet, wird nicht mehr bearbeitet. Die Einträge mit dem Ausgang «nichts tun» wurden darum nicht einzeln nachgeprüft: Ob sie zutreffen, ändert den Ausgang nicht.

### Erledigt / überholt

- 2026-10-30 — Nachweis auf fly.io endet an der Anmeldung → überholt: Testkonten werden per `fly ssh` angelegt und danach gelöscht (so bei #37), angemeldete Seiten prüft zudem Koschi auf dem Gerät (#17, #37).

### An bestehende Issues gehängt

- 2026-10-30 — #18 Minors aus den Reviews → Für die Auftraggeberin zählen nur zwei Punkte: Excel zeigt die Datumsspalte als «#####» und macht aus den Adressen der Aufnahmen keine Links. Beides als Satz für die Testanleitung an #9. Der Löschhinweis zum Export ist mit #8 und #10 (Abschluss) abgedeckt. Der Rest ist Kosmetik und Testabdeckung, siehe unten.

### Abgehakt (befristeter Pilot, kein falsches Verhalten)

Gemeinsamer Trigger: Das Instrument wird über den Pilot hinaus betrieben oder weiterentwickelt. Dann diese Liste vor der ersten Arbeit wieder lesen.

- 2026-10-30 — Eingabemaske: Doppelklick legt doppelt an (Verwaltung) → nur die Auftraggeberin erfasst, ein Doppel sieht und löscht sie.
- 2026-10-30 — Entwurfsschutz: Entwürfe bleiben im Tab liegen → geteilte Handys sind im Pilot nicht vorgesehen.
- 2026-10-30 — Lehrpersonen-Ansicht: Abfragen und Event-Loop → bei fünf Lehrpersonen ohne Wirkung.
- 2026-10-30 — Lehrpersonen-Ansicht: Struktur und Benennung im Code → Lesbarkeit.
- 2026-10-30 — Doppelte Logik um Aufnahmen → Lesbarkeit.
- 2026-10-30 — Aufnahmen: kleine Robustheitspunkte → ohne Folgen im Betrieb.
- 2026-10-30 — Lehrpersonen-Ansicht: Kleinigkeiten an der Oberfläche → Gestaltung ist mit #20 abgeschlossen.
- 2026-10-30 — Aufnahme-Seiten: kleine Bedienpunkte → Kosmetik und seltene Rückfallwege.
- 2026-10-30 — Rückfall ohne Aufnahmefähigkeit: Formate → betrifft nur Browser ohne Aufnahmefunktion; iPhone und Chrome nehmen auf.
- 2026-10-30 — Doppelter gesprochener Eintrag bei verlorener Antwort → selten, die Lehrperson kann ihn löschen.
- 2026-10-30 — Gast und Vorschau: Randfälle im Betrieb → `HEAD` steht als Memory fest, einen Verbindungspool gibt es nicht.
- 2026-10-30 — Tests der Lehrpersonen-Ansicht: Lücken → Verhalten per Probe belegt.
- 2026-10-30 — Tests der Lehrpersonen-Ansicht: Lesbarkeit → Kosmetik.
- 2026-10-30 — Tests von Gast und Vorschau: Lücken → Verhalten heute korrekt.
- 2026-10-30 — Tests von Gast und Vorschau: Lesbarkeit → Kosmetik.
- 2026-10-30 — Aufnahmen: Testlücken ohne bekannten Fehler → Aufnahme ist auf dem iPhone belegt (#17).
- 2026-10-31 — E2E: Abo für Benachrichtigungen im Headless-Chrome nur gelegentlich → Zustellung ist auf fly.io und auf dem iPhone belegt (#37).

## Ausgewertet am 30.10.2026

Alle 15 Einträge gegen `main` (Stand nach #29) geprüft, Laufzeit-Aussagen gegen GitHub Actions, fly.io und eine lokal gestartete App gemessen. Bilanz: 1 mitgemacht, 2 an bestehende Issues gehängt, 2 erledigt, 9 abgehakt mit Trigger, 1 verworfen.

### Mitgemacht

- 2026-10-30 — Eingabemaske: Nur ein Fehler pro Absenden, Felder ohne Markierung → Felder mit Fehler tragen jetzt `aria-invalid` und einen roten Rahmen; damit stimmt auch der Hinweis «Bitte prüfe die markierten Felder.», der vorher nichts markiert fand. Commit «fix: Eingabemaske markiert fehlerhafte Felder». Der Teil «nur ein Fehler pro Absenden» ist abgehakt, Trigger: die Auftraggeberin hat beim Erfassen (#6) Mühe damit.

### An bestehende Issues gehängt (Kommentar mit DoD-Vorschlag)

- 2026-10-30 — Eingabemaske: Doppelklick legt doppelt an → #16. Gemessen: zwei gleiche POSTs legen zwei Runden an. Für Lehrpersonen auf dem Handy hiesse das doppelte Tagebucheinträge; der Plan zu #16 deckt nur das Neuladen ab. → Für die Lehrpersonen-Ansicht erledigt: gleicher Tagebucheintrag innert 10 Sekunden wird nicht doppelt angelegt, Commit «fix: Doppelt abgesendeter Tagebucheintrag wird nur einmal angelegt (#16)». Die Verwaltung ist weiter offen (siehe «Offen»).
- 2026-10-30 — Wiederherstellung aus einem Volume-Snapshot nie geprobt → #9. Snapshots sind eingeschaltet, am 30.10. gab es noch keinen; Probe mit Testdaten vor dem Testlauf.

### Erledigt

- 2026-10-15 — Runner-Image `ubuntu-latest` wechselt auf Ubuntu 26 → Wechsel erfolgt (`ubuntu-26.04`), alle Läufe von CI und Prototyp grün.
- 2026-10-30 — Unklar, ob die GitHub-Verbindung von fly.io `main` deployt → GitHub-App «Fly.io» deinstalliert; Deploy nur mit `make deploy`.

### Abgehakt mit Trigger

- 2026-10-15 — GitHub Actions über Tags statt Commit-SHAs eingebunden → betrifft nur noch `prototyp.yml` (`ci.yml` ist gepinnt). Dazu kommt in `prototyp.yml` die Warnung «Node.js 20 is deprecated». Der Prototyp wird laut ADR-001 abgelöst, sobald die Pilot-Version läuft. Trigger: beim Pilotstart Workflow und Prototyp entfernen oder, falls er öffentlich bleiben soll, auf aktuelle Versionen per SHA umstellen.
- 2026-10-15 — Test-Server der E2E-Prüfung stürzt bei Verzeichnis-Anfragen ab → belegt, im heutigen Ablauf unerreichbar. Trigger: wie oben, entfällt mit dem Prototyp.
- 2026-10-15 — E2E-Prüfung läuft nur lokal auf macOS → bewusst so (Nicht-Ziel im Grundgerüst-Design); `e2e-pilot.mjs` liest den Chrome-Pfad schon aus `CHROME_PFAD`. Trigger: eine zweite Person entwickelt mit, oder ein Merge geht ohne lokalen E2E-Lauf durch.
- 2026-10-30 — TestClient warnt: httpx durch httpx2 ersetzen → Starlette 1.10 unterstützt httpx noch. Trigger: Starlette entfernt die Unterstützung; dann Freigabe für httpx2 als neue Dependency einholen.
- 2026-10-30 — Basis-Images über Tags statt Digests eingebunden → bei einem vierwöchigen Pilot mit seltenen Deploys vertretbar. Trigger: Betrieb über das Projektende hinaus.
- 2026-10-30 — Fehlerseiten 500 ohne Sicherheits-Header, `HEAD /` gibt 405 → beides gemessen (auch `HEAD /healthz` gibt 405), ohne Folgen. Trigger: ein Uptime-Monitor oder eine eigene Fehlerseite kommt dazu.
- 2026-10-30 — Kleine Härtungen an Migrationen und E2E-Skript → belegt; ein zweiter Prozess entsteht nur, wenn ein Kommando per `fly ssh` genau während einer neuen Migration startet. Trigger: mehr als eine Maschine, oder ein Deploy scheitert an der Migration.
- 2026-10-30 — Eingabemaske: Doppeltes «Endgültig löschen» endet auf «Nicht gefunden» → folgenlos, das 404 ist von Tests so festgelegt. Trigger: die Auftraggeberin meldet die Seite als irritierend.
- 2026-10-30 — Zurückgestellte Kleinigkeiten aus den Reviews zu #14 und #15 → Politur ohne falsches Verhalten. Trigger: bei der nächsten Arbeit an der jeweiligen Testdatei dort nachziehen.

### Verworfen

- 2026-10-30 — Kommando rechnet mit ungeprüftem Datum → Die Kernaussage trifft nicht zu: `platzhalter-laden` ruft zuerst `speichere_allgemein` auf, das über `datum_feld` (`app/eingaben.py`) → `ist_plausibel` (`app/zeit.py`) prüft. `--projektstart 9999-12-30` endet mit «Bitte ein Datum zwischen 2020 und 2099 wählen.» und Exit 1, ohne `OverflowError`. Richtig ist nur, dass `lies_projektstart` einen Altwert ungeprüft liefert; der entsteht aber nur durch eine Änderung direkt in der Datenbank.

### Falsche Prämissen

| Eintrag | Behauptung | Gemessen |
|---|---|---|
| Basis-Images über Tags | «Die Actions sind auf Commit-SHAs gepinnt» | nur in `ci.yml`, nicht in `prototyp.yml` |
| Kommando rechnet mit ungeprüftem Datum | Kommando prüft den Bereich nicht, `OverflowError` möglich | Prüfung über `speichere_allgemein`; der vorgeschlagene Fix hätte nichts behoben |
| Zurückgestellte Kleinigkeiten | kein Test für das Rollback der obersten Transaktion | `test_allgemein_fehler_schreibt_nichts`, `test_transaktion_verschachtelt` |
| Härtungen an Migrationen | «Bei einer Maschine und einem Prozess» | Kommandos per `fly ssh` sind ein zweiter Prozess neben der App |
| Snapshot nie geprobt | tägliche Snapshots sind die Sicherung | am 30.10. noch kein Snapshot vorhanden |
| Nur ein Fehler pro Absenden | Fehler nur über den Text erkennbar | `aria-describedby` verband Feld und Fehler schon; dafür behauptete der Kopfhinweis eine Markierung, die es nicht gab |
| E2E nur lokal auf macOS | Chrome-Pfad per Umgebungsvariable wäre noch zu tun | in `e2e-pilot.mjs` schon umgesetzt (`CHROME_PFAD`) |
