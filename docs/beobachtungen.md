# Beobachtungen (Posteingang für Befunde ausserhalb des Scopes)

Hier landen Befunde, die beim Arbeiten auffallen, aber nicht zum aktuellen Issue gehören.

- **Eintragen** (Claude, ohne Rückfrage): neuer Eintrag ans Ende von «Offen», Aufbau wie unten. Passendes **Thema** aus den vorhandenen Einträgen übernehmen statt ein neues zu erfinden.
- **Auswerten** mit dem Skill `beobachtungen-auswerten`. Wann, entscheidet Koschi.
- **Ein Issue** entsteht daraus nur mit ausdrücklicher Zustimmung (Regeln in `../CLAUDE.md`).
- Das Repo ist öffentlich: keine vertraulichen Inhalte in Einträgen.

Letzte Auswertung: 30.10.2026 (15 Einträge, alle abgeschlossen)

## Offen

### 2026-10-30 — Eingabemaske: Doppelklick legt doppelt an (Verwaltung)

**Thema:** Eingabemaske

**Fundort:** `app/inhalte.py` (`lege_runde_an` und die übrigen Anlege-Funktionen), `app/routen/verwaltung_inhalte.py`

**Beobachtung:** Für die Lehrperson ist doppeltes Absenden im Tagebuch abgefangen (#16). In der Verwaltung legen zwei gleiche POSTs weiterhin zwei Runden (bzw. Fragen, Impulse) an.

**Ursprung:** Review zu #16 (Restteil des ausgewerteten Eintrags vom 30.10.)

**Einschätzung:** Folgenlos, solange nur die Auftraggeberin erfasst und ein Doppel sieht und löscht. Gleiches Muster wie im Tagebuch möglich (gleicher Inhalt innert 10 Sekunden).

### 2026-10-30 — Entwurfsschutz: Entwürfe bleiben im Tab liegen

**Thema:** Datenschutz

**Fundort:** `app/static/js/entwurf.js`

**Beobachtung:** (1) Meldet sich nach Ablauf der Sitzung im selben Tab eine andere Person an, bleibt der Entwurf der ersten im `sessionStorage` (nicht angezeigt, aber über die Entwicklerwerkzeuge lesbar). (2) Ein nicht gespeicherter Entwurf zu `tagebuch-{id}` bleibt nach dem Löschen des Eintrags liegen; ohne `AUTOINCREMENT` kann dieselbe `id` für einen neuen Eintrag derselben Person wieder vergeben werden, dann erscheint der alte Text als «wiederhergestellt». (3) Abmelden auf Seiten ohne `entwurf.js` (z. B. Fehlerseite) löscht Entwürfe nicht; die Konto-ID im Schlüssel verhindert die Anzeige für andere.

**Ursprung:** #16 (Task 10, Gesamt-Review M3)

**Einschätzung:** Geteilte Handys im Pilot unwahrscheinlich, Schliessen des Tabs räumt alles. Möglicher Weg: beim Laden alle `entwurf:`-Schlüssel mit fremdem Konto-Präfix löschen; beim Löschen eines Eintrags `data-entwurf-verwerfen` für `tagebuch-{id}` auf «Meine Einträge» rendern.

### 2026-10-30 — Lehrpersonen-Ansicht: Abfragen und Event-Loop

**Thema:** Leistung

**Fundort:** `app/seiten_lehrperson.py:263,307`, Context-Processor für den Titel (#15), `app/routen/lehrperson.py` (`runde_speichern`)

**Beobachtung:** «Meine Einträge» fragt pro Karte `sichtbare_runde` und `inhalte.fragen` einzeln ab. Der Context-Processor öffnet pro Seite eine zweite Verbindung für den Titel (Spec-Nachtrag «Titel über die Anfrage-Verbindung», kein Muss, nicht umgesetzt). `runde_speichern` ist eine `async`-Route mit synchronem SQLite; wartet eine Schreibsperre bis zu `busy_timeout` 5 s, blockiert das den Event-Loop für alle Anfragen.

**Ursprung:** Gesamt-Review zu #16 (M4) und Fix-Welle

**Einschätzung:** Bei fünf Lehrpersonen bedeutungslos. Trigger: spürbar langsame Seiten oder mehr Nutzende; dann Formular in einer synchronen Dependency lesen oder SQLite-Teil per `run_in_threadpool` auslagern.

### 2026-10-30 — Lehrpersonen-Ansicht: Struktur und Benennung im Code

**Thema:** Code-Struktur

**Fundort:** `app/sichtbar.py`, `app/eintraege.py` (`entferne_aufnahmen`, `gruppiere`), `app/seiten_lehrperson.py:230` (SQL auf `aufnahmen`), `app/routen/lehrperson.py`

**Beobachtung:** `sichtbar.py`: Walrus in einer Comprehension, `date.fromisoformat` plus `ist_erreicht` fünfmal wiederholt (Helfer `_erreicht`). `entferne_aufnahmen` und das SQL auf `aufnahmen` in `seiten_lehrperson.py` gehören inhaltlich nach `aufnahmen.py`. Lösch-Kontext zweimal gebaut, Schlüssel `VORLAGEN["runde_loeschen"]` dient auch dem Tagebuch. Konstanten mitten in der Datei, fehlende Typen, `hole_bezug` doppelt, `_weiter` ohne Rückgabetyp, Sortierschlüssel `runde_id or eintrag_id` in `gruppiere` nur implizit.

**Ursprung:** #16 (Tasks 3, 4, 5, 6, 8)

**Einschätzung:** Lesbarkeit, kein falsches Verhalten. Verschieben nach `aufnahmen.py` jetzt kollidiert mit #17; dort bei #17 mit erledigen, den Rest bei der nächsten Arbeit an der Datei.

### 2026-10-30 — Lehrpersonen-Ansicht: Kleinigkeiten an der Oberfläche

**Thema:** Oberfläche

**Fundort:** `app/templates/lehrperson/tagebuch_eintrag.html`, `start.html` (Band), `runde.html`, Info-Seite

**Beobachtung:** `tagebuch_eintrag.html` hat als einzige Seite kein `h1` (nur die Überzeile; schwächt die Navigation per Screenreader, Fix: `art_text` als `h1` mit Klasse `ueberzeile`). Band-`div` ohne Klasse `formatiert`. «seit …» gedämpft statt als Marke. Info-Seite: `h1` «Worum es geht» und erste Karte gleich betitelt (hängt am Platzhalter-Inhalt).

**Ursprung:** #16 (Tasks 6, 7, 8, 9)

**Einschätzung:** Gestaltung gehört zu #20; das `h1` beim nächsten Anfassen der Seite mitnehmen.

### 2026-10-30 — Tests der Lehrpersonen-Ansicht: Lücken

**Thema:** Tests

**Fundort:** `tests/test_groesse.py`, `tests/test_runde.py`, `tests/test_tagebuch_routen.py`, `tests/test_eintraege.py`, `tests/test_tagebuch.py`, `tests/test_ansicht.py`, `tests/e2e-pilot.mjs`

**Beobachtung:** Von der Spec verlangt, aber nicht als Test vorhanden: `POST /lehrperson/runden/{id}` knapp unter 1 MiB (nur `/anmelden` mit 60 KiB), Grenzfall genau `GRENZE`, der Pfad über `pruefe_csrf` ohne dauerhaften Test, ungültige IDs auf POST nur mit `abc` an einer Tagebuch-Route. Weiter: kein Rollback-Test, der eine Datei stehen lässt; `test_loeschen_in_laufender_transaktion` prüft nicht, dass nichts gelöscht wurde; `test_aendern` prüft `geaendert` nur auf `> ALT`; «seit …», Ziel von «Dazu schreiben», Karte «Zur Leitfrage» und der `value` des zweiten kleinen Knopfs ungetestet; `test_neu_400_behaelt_text` prüft das Feld nicht; `leitfrage/1` hart kodiert. E2E: Neuanmeldung dupliziert `meldeAn()`, Skript-Text nur im Textfeld statt auf der Karte geprüft, `heute` aus der JS-Lokalzeit, Dunkel-Lauf prüft nur den Überlauf. In Task 7 kein RED-Lauf protokolliert.

**Ursprung:** #16 (Tasks 2, 4, 5, 6, 7, 8, 9; Gesamt-Review M2)

**Einschätzung:** Verhalten jeweils per Probe oder anderem Test belegt, keine Fehler gefunden. Trigger: bei der nächsten Arbeit an der jeweiligen Testdatei nachziehen.

### 2026-10-30 — Tests der Lehrpersonen-Ansicht: Lesbarkeit

**Thema:** Tests

**Fundort:** `tests/test_testdaten.py`, `tests/testdaten.py` (`abzug`), `tests/test_migration_003.py`, `tests/test_groesse.py`, `tests/test_tagebuch.py`, `tests/test_ansicht.py`

**Beobachtung:** Assertion in `test_testdaten.py` verdreht formatiert; `testdaten.abzug` sortiert mit `sorted()` ohne `key` (bei `None` im Vergleich ein `TypeError`, heute unerreichbar, weil die erste Spalte eindeutig ist); ungenutzte Fixture `einstellungen` in `test_migration_003`, ungenutzte Fixture `heute_ist` in `test_gast_start_ohne_persoenliches`; Testname `test_knapp_unter_grenze` irreführend; Tupelvergleiche mit `fmt: skip` schwer lesbar.

**Ursprung:** #16 (Tasks 1, 2, 5, 6)

**Einschätzung:** Kosmetik. Trigger: wie oben.

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
