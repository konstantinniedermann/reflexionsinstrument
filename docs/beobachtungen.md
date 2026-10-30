# Beobachtungen (Posteingang für Befunde ausserhalb des Scopes)

Hier landen Befunde, die beim Arbeiten auffallen, aber nicht zum aktuellen Issue gehören.

- **Eintragen** (Claude, ohne Rückfrage): neuer Eintrag ans Ende von «Offen», Aufbau wie unten. Passendes **Thema** aus den vorhandenen Einträgen übernehmen statt ein neues zu erfinden.
- **Auswerten** mit dem Skill `beobachtungen-auswerten`. Wann, entscheidet Koschi.
- **Ein Issue** entsteht daraus nur mit ausdrücklicher Zustimmung (Regeln in `../CLAUDE.md`).
- Das Repo ist öffentlich: keine vertraulichen Inhalte in Einträgen.

Letzte Auswertung: noch keine

## Offen

### 2026-10-15 — GitHub Actions über Tags statt Commit-SHAs eingebunden

**Thema:** CI

**Fundort:** `.github/workflows/prototyp.yml`

**Beobachtung:** `actions/checkout@v4`, `configure-pages@v5` usw. sind über verschiebbare Tags eingebunden. Ein kompromittierter Tag würde beim nächsten Lauf fremden Code mit Pages-Schreibrechten ausführen.

**Ursprung:** Review zu #1

**Einschätzung:** Für den Wegwerf-Prototyp vertretbar. Für die Pilot-Version (#7) auf SHAs pinnen, falls sie weiter über Actions deployt wird.

### 2026-10-15 — E2E-Prüfung läuft nur lokal auf macOS

**Thema:** Tests

**Fundort:** `tests/e2e-prototyp.mjs` (fester Chrome-Pfad unter `/Applications`)

**Beobachtung:** Die CI führt nur die Unit-Tests aus. Die E2E-Prüfung braucht Chrome unter macOS und muss von Hand gestartet werden.

**Ursprung:** Review zu #1

**Einschätzung:** Für den Prototyp genügt das. Bei der Pilot-Version entscheiden, ob E2E in die CI gehört (Chrome-Pfad per Umgebungsvariable).

### 2026-10-15 — Test-Server der E2E-Prüfung stürzt bei Verzeichnis-Anfragen ab

**Thema:** Tests

**Fundort:** `tests/e2e-prototyp.mjs`, statischer Server (`readFileSync` ohne Prüfung auf Datei)

**Beobachtung:** Eine Anfrage auf ein Verzeichnis wie `/css/` besteht die `existsSync`-Prüfung, `readFileSync` wirft dann `EISDIR` und beendet das Skript.

**Ursprung:** Eigene Beobachtung bei #1

**Einschätzung:** Tritt im heutigen Ablauf nicht auf, weil der Prototyp nur Dateien lädt. Mit `statSync(...).isFile()` in einer Minute behoben, falls das Skript weiterlebt.

### 2026-10-15 — Runner-Image `ubuntu-latest` wechselt auf Ubuntu 26

**Thema:** CI

**Fundort:** `.github/workflows/prototyp.yml`, Hinweis im Actions-Log

**Beobachtung:** GitHub kündigt an, dass `ubuntu-latest` ab dem 19.10.2026 auf Ubuntu 26 umgestellt wird.

**Ursprung:** Deploy-Lauf nach dem Merge von #11

**Einschätzung:** Für einen Workflow, der nur Node-Tests und einen Pages-Upload macht, vermutlich folgenlos. Nach dem nächsten Lauf kurz prüfen.

### 2026-10-30 — TestClient warnt: httpx durch httpx2 ersetzen

**Thema:** Tests

**Fundort:** `pyproject.toml` (filterwarnings)

**Beobachtung:** Der Starlette-TestClient meldet, dass `httpx` veraltet ist und `httpx2` verwendet werden soll.

**Ursprung:** Umsetzung #13

**Einschätzung:** Warnung gezielt unterdrückt. Der Wechsel auf httpx2 wäre eine neue Dependency und braucht Koschis Freigabe; spätestens nötig, wenn Starlette httpx nicht mehr unterstützt.

### 2026-10-30 — Unklar, ob die GitHub-Verbindung von fly.io `main` deployt

**Thema:** Betrieb

**Fundort:** fly.io, App `reflexionsinstrument`, GitHub-Verbindung in der Weboberfläche

**Beobachtung:** Koschi hat die App über die Weboberfläche mit GitHub verbunden, als `main` noch kein `Dockerfile` und kein `fly.toml` hatte. Nach dem Merge von #22 entstand in den ersten Minuten kein neues Release; die laufende Version stammt aus `make deploy` vom Branch.

**Ursprung:** Deploy #13

**Einschätzung:** Im fly-Dashboard prüfen, ob und wie die Verbindung deployt und ob sie `fly.toml` aus dem Repo verwendet (Volume `daten`). Sonst könnte ein späterer automatischer Deploy ohne Volume starten. Bis zur Klärung weiter mit `make deploy`. Nachtrag 30.10.: Die Merges #22–#26 lösten keinen Deploy aus; die einzige Bot-Bereitstellung (Stand vor dem Dockerfile) hängt seit 15:41 UTC auf «in_progress». Empfehlung an Koschi: Verbindung im Dashboard trennen. Nachtrag 30.10. abends: Erledigt. Die GitHub-App «Fly.io» ist auf GitHub deinstalliert (im fly-Dashboard gab es keinen Schalter dafür). Im Repo bleibt nur der alte Bot-Deployment-Eintrag «production», bewusst nicht gelöscht. Deploy weiterhin nur mit `make deploy`.

### 2026-10-30 — Basis-Images über Tags statt Digests eingebunden

**Thema:** CI

**Fundort:** `Dockerfile` (`python:3.13-slim`, `ghcr.io/astral-sh/uv:0.13.6`)

**Beobachtung:** Die Actions sind auf Commit-SHAs gepinnt, die Images im Dockerfile nur über Tags. Ein verschobener Tag würde beim nächsten Build ein anderes Image liefern.

**Ursprung:** Gesamt-Review #13

**Einschätzung:** Für einen vierwöchigen Pilot mit seltenen Deploys gering. Pinnen per `@sha256:…` wäre in Minuten gemacht, kostet aber Pflege bei Sicherheitsupdates.

### 2026-10-30 — Fehlerseiten 500 ohne Sicherheits-Header, `HEAD /` gibt 405

**Thema:** Sicherheit

**Fundort:** `app/main.py`, `app/sicherheit.py`

**Beobachtung:** Starlettes `ServerErrorMiddleware` liegt ausserhalb der eigenen Middleware, deshalb fehlen bei einem 500 die Sicherheits-Header (Antwort ist reiner Text). Ausserdem beantwortet `/` eine HEAD-Anfrage mit 405, was externe Erreichbarkeits-Prüfungen stören kann.

**Ursprung:** Reviews #13

**Einschätzung:** Praktisch ohne Folgen. Wird relevant, falls eine eigene Fehlerseite (HTML) oder ein Uptime-Monitor dazukommt.

### 2026-10-30 — Kleine Härtungen an Migrationen und E2E-Skript

**Thema:** Tests

**Fundort:** `app/db.py` (`migriere`), `tests/e2e-pilot.mjs`

**Beobachtung:** `migriere` liest `user_version` vor `BEGIN IMMEDIATE`; zwei gleichzeitig startende Prozesse könnten dieselbe Migration versuchen (der zweite scheitert laut). Ein Dateiname wie `1a_x.sql` führt zu `ValueError`. Im E2E-Skript wächst die Liste der CDP-Ereignisse unbegrenzt. (Erledigt mit #14: `muss` bricht den Ablauf bei Fehlschlag ab.)

**Ursprung:** Task-Reviews #13

**Einschätzung:** Bei einer Maschine und einem Prozess folgenlos. Die Ereignisliste ist bei der heutigen Länge der Abläufe unkritisch.

### 2026-10-30 — Wiederherstellung aus einem Volume-Snapshot nie geprobt

**Thema:** Betrieb

**Fundort:** fly.io, Volume `daten` (`snapshot_retention = 5`)

**Beobachtung:** Während der Laufzeit sind die täglichen Snapshots von fly.io die einzige Sicherung der Einträge und Aufnahmen. Ob und wie schnell sich daraus ein Volume wiederherstellen lässt (neues Volume aus Snapshot, Maschine darauf umhängen), ist nicht ausprobiert.

**Ursprung:** Löschkonzept #8

**Einschätzung:** Eine Probe vor dem Testlauf (#9) mit Testdaten dauert etwa eine halbe Stunde und kostet für ein paar Minuten ein zweites Volume. Ohne Probe bleibt im Ernstfall nur Ausprobieren unter Zeitdruck.

### 2026-10-30 — Eingabemaske: Doppelklick legt doppelt an

**Thema:** Bedienung

**Fundort:** Formulare «Neue Runde», «Neue Frage» usw. unter `/verwaltung/inhalte`

**Beobachtung:** Ein Doppelklick auf «Speichern» schickt das Formular zweimal ab; ohne JavaScript legt das den Eintrag doppelt an.

**Ursprung:** Gesamt-Review #15

**Einschätzung:** Doppelte Einträge lassen sich löschen. Eine Abhilfe wäre ein einmaliger Formular-Schlüssel oder ein kleines Skript, das den Knopf sperrt; die Maske ist bewusst ohne JavaScript.

### 2026-10-30 — Eingabemaske: Doppeltes «Endgültig löschen» endet auf «Nicht gefunden»

**Thema:** Bedienung

**Fundort:** Löschbestätigung unter `/verwaltung/inhalte`

**Beobachtung:** Bei langsamem Netz und zweimaligem Klick auf «Endgültig löschen» löscht die erste Anfrage, die zweite endet auf der Seite «Nicht gefunden» statt auf der Liste mit «Gelöscht.».

**Ursprung:** Gesamt-Review #15

**Einschätzung:** Folgenlos, die Daten sind richtig gelöscht; nur die Rückmeldung irritiert.

### 2026-10-30 — Eingabemaske: Nur ein Fehler pro Absenden, Felder ohne Markierung

**Thema:** Bedienung, Barrierefreiheit

**Fundort:** Formulare der Eingabemaske

**Beobachtung:** Pro Absenden wird nur der erste Fehler gemeldet. Betroffene Felder tragen weder `aria-invalid` noch einen Rahmen; der Fehler ist nur über den Text darunter erkennbar.

**Ursprung:** Gesamt-Review #15

**Einschätzung:** Bei den kurzen Formularen tragbar. Rahmen und `aria-invalid` sind eine kleine Ergänzung, falls die Auftraggeberin Mühe damit hat.

### 2026-10-30 — Kommando rechnet mit ungeprüftem Datum

**Thema:** Bedienung

**Fundort:** `app/kommandos.py` (`platzhalter-laden --projektstart`), `app/inhalte.py` (`lies_projektstart`)

**Beobachtung:** Seit #15 nimmt die Maske nur Jahre 2020–2099 an. Das Kommando `platzhalter-laden --projektstart` prüft den Bereich nicht; ein Jahr 9999 kann beim Addieren der Wochen einen `OverflowError` auslösen. Ein schon gespeicherter, unplausibler erster Tag wird von `lies_projektstart` ungeprüft geliefert (Vorschläge zeigen ihn, Speichern meldet dann 400).

**Ursprung:** Re-Review der Fixes zu #15

**Einschätzung:** Nur für Entwicklung bzw. Altdaten erreichbar, kein Absturz in der Maske. `ist_plausibel` aus `app/zeit.py` im Kommando mitbenutzen wäre eine Zeile.

### 2026-10-30 — Zurückgestellte Kleinigkeiten aus den Reviews zu #14 und #15

**Thema:** Tests

**Fundort:** `tests/` (u. a. `test_kommandos.py`, `test_sitzung.py`, `test_anmeldeschutz.py`, `test_verwaltung.py`, `test_verwaltung_inhalte.py`, `test_inhalte.py`, `e2e-pilot.mjs`), `app/csrf.py`, `app/templates/basis.html`

**Beobachtung:** Aus den Task-Reviews blieben bewusst zurückgestellte Kleinigkeiten: Testverbindungen ohne `close()`, einzelne Tests ohne Statusprüfung oder mit schwacher Aussage (Bestätigung «nur aus fester Liste», E2E «Impuls löschen», Zähltexte), fehlende Tests für einige Randzweige (Wettlauf beim Löschen, Rollback der obersten Transaktion). Dazu aus dem Gesamt-Review #14: CSRF-Fehler nutzt `KeinZugriff` mit eigenem Titel statt einer eigenen Ausnahme; auf 404-Seiten fehlen Anzeigename und «Abmelden» im Kopf; `__Host-`-Präfix für Cookies erst bei eigener Domain sinnvoll.

**Ursprung:** Task-Reviews und Gesamt-Reviews #14, #15

**Einschätzung:** Kein Verhalten falsch, Politur. Bei einer ruhigen Stunde gesammelt nachziehen oder bei der Auswertung verwerfen.

