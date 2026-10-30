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
