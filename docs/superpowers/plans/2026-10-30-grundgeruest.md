# Grundgerüst der Pilot-Version — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Leeres, lauffähiges FastAPI-Gerüst mit SQLite-Schema, Sicherheits-Headern, CI, Makefile und fly.io-Konfiguration, auf dem #14–#19 aufbauen.

**Architecture:** Paket `app/` mit App-Factory `erstelle_app()`, Einstellungen aus Umgebungsvariablen, SQLite mit nummerierten SQL-Migrationen (`PRAGMA user_version`), serverseitig gerenderte Jinja2-Templates, CSS aus dem Prototyp. Container mit uv und Lockfile, Deployment lokal per `fly deploy`.

**Tech Stack:** Python 3.13, FastAPI, uvicorn, Jinja2, sqlite3, pytest, httpx, ruff, uv, fly.io.

**Spec:** `docs/superpowers/specs/2026-10-30-grundgeruest-design.md`

## Global Constraints

- Dependencies nur: `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `itsdangerous`, `bcrypt`; dev: `pytest`, `httpx`, `ruff`. Nichts anderes installieren.
- Python `>=3.12` in `pyproject.toml`, `.python-version` = `3.13`, Image `python:3.13-slim`.
- Bezeichner, Kommentare, Texte auf Deutsch (wie im Prototyp), ohne ß, Umlaute in Texten erlaubt, in Bezeichnern ausgeschrieben (`ue`, `ae`, `oe`).
- Kein Inline-JavaScript, kein Inline-CSS, keine externen Schriften oder Skripte (CSP ohne `unsafe-inline`).
- Keine echten Inhalte der Auftraggeberin, keine Namen, Schulen, Orte im Repo.
- Commits: Präfix `feat:`/`test:`/`docs:`/`refactor:`/`fix:`, mit `(#13)` am Ende der ersten Zeile, Trailer:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy8wrhdWVtdWcGb3tyj`
- Ruff: Standardregeln plus `I`, Zeilenlänge 100. `uv run ruff check` und `uv run ruff format --check` müssen nach jeder Task sauber sein.
- Ein Ruff-Hook formatiert und entfernt ungenutzte Imports zwischen Edits: Import und Verwendung im selben Edit schreiben (oder ganze Datei mit Write).

## Review Focus

1. **Frisches Volume ohne Ordner:** `DATEN_VERZEICHNIS` existiert nicht → App legt es samt `aufnahmen/` beim Start an, statt abzustürzen. (Task 3, `test_start_legt_datenverzeichnis_an`)
2. **Fehlerhafte Migration:** Bricht eine Migration mitten im Skript ab, bleibt die Datenbank auf dem alten Stand (keine halben Tabellen, `user_version` unverändert). (Task 2, `test_fehlerhafte_migration_rollt_zurueck`)
3. **Benutzername in anderer Schreibweise:** `Anna` und `anna` gelten als derselbe Benutzername. (Task 2, `test_benutzername_eindeutig_ohne_gross_klein`)
4. **Fehlerseiten ohne Header:** Auch 404-Antworten tragen CSP und die übrigen Header. (Task 3, `test_header_auch_bei_404`)
5. **Produktion mit leerem Schlüssel:** `PRODUKTION=1` und `GEHEIMER_SCHLUESSEL=""` (gesetzt, aber leer) verweigert den Start. (Task 1, `test_produktion_mit_leerem_schluessel_schlaegt_fehl`)

---

### Task 1: Projekt-Setup und Einstellungen

**Files:**
- Create: `pyproject.toml`, `uv.lock` (durch uv), `.python-version`, `app/__init__.py`, `app/config.py`, `tests/conftest.py`, `tests/test_config.py`
- Modify: `.gitignore` (ergänzen: `.daten/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `.ruff_cache/`)

**Interfaces:**
- Produces (`app/config.py`):
  - `@dataclass(frozen=True) class Einstellungen` mit Feldern `daten_verzeichnis: Path`, `geheimer_schluessel: str`, `produktion: bool` und Properties `db_pfad -> Path` (= `daten_verzeichnis / "reflexion.db"`), `aufnahmen_verzeichnis -> Path` (= `daten_verzeichnis / "aufnahmen"`).
  - `def lade_einstellungen(umgebung: Mapping[str, str] | None = None) -> Einstellungen` — liest `os.environ`, wenn `umgebung` None ist. `PRODUKTION` ist wahr nur bei `"1"`. Standardverzeichnis `Path(".daten")`. Ohne Schlüssel und ohne Produktion: Entwicklungswert `"nur-fuer-entwicklung"` plus `warnings.warn`. Produktion ohne oder mit leerem Schlüssel: `RuntimeError`.
- Produces (`tests/conftest.py`): Fixture `einstellungen(tmp_path) -> Einstellungen` mit `daten_verzeichnis=tmp_path / "daten"`, Schlüssel `"test-schluessel"`, `produktion=False`.

- [ ] **Step 1:** `pyproject.toml` anlegen (`[project]` name `reflexionsinstrument`, version `0.1.0`, `requires-python = ">=3.12"`, `[tool.ruff]` line-length 100, `[tool.ruff.lint] extend-select = ["I"]`, `[tool.pytest.ini_options] testpaths = ["tests"]`), `.python-version` mit `3.13`. Dann `uv add fastapi uvicorn jinja2 python-multipart itsdangerous bcrypt` und `uv add --dev pytest httpx ruff`. Erwartet: `uv.lock` entsteht, `uv run python -c "import fastapi"` läuft.
- [ ] **Step 2: Failing tests** in `tests/test_config.py`:
  - `test_standardwerte_ohne_umgebung`: `lade_einstellungen({})` → `daten_verzeichnis == Path(".daten")`, `produktion is False`, `geheimer_schluessel == "nur-fuer-entwicklung"` (Warnung mit `pytest.warns(UserWarning)` erwartet).
  - `test_pfade_abgeleitet`: `db_pfad.name == "reflexion.db"`, `aufnahmen_verzeichnis.name == "aufnahmen"`, beide unter `daten_verzeichnis`.
  - `test_produktion_ohne_schluessel_schlaegt_fehl`: `{"PRODUKTION": "1"}` → `RuntimeError`.
  - `test_produktion_mit_leerem_schluessel_schlaegt_fehl`: `{"PRODUKTION": "1", "GEHEIMER_SCHLUESSEL": ""}` → `RuntimeError`.
  - `test_produktion_mit_schluessel`: `{"PRODUKTION": "1", "GEHEIMER_SCHLUESSEL": "x", "DATEN_VERZEICHNIS": "/data"}` → `produktion is True`, `daten_verzeichnis == Path("/data")`.
  - `test_produktion_nur_bei_eins`: `{"PRODUKTION": "true", "GEHEIMER_SCHLUESSEL": "x"}` → `produktion is False`.
- [ ] **Step 3:** `uv run pytest tests/test_config.py -v` → FAIL (ImportError).
- [ ] **Step 4:** `app/config.py` implementieren wie in Interfaces.
- [ ] **Step 5:** `uv run pytest -v` → PASS; `uv run ruff check && uv run ruff format --check` → sauber.
- [ ] **Step 6:** Commit `feat: Projekt-Setup und Einstellungen (#13)`.

### Task 2: Datenbank und Grundschema

**Files:**
- Create: `app/db.py`, `app/migrationen/001_grundschema.sql`, `tests/test_db.py`

**Interfaces:**
- Consumes: `Einstellungen` (Task 1).
- Produces (`app/db.py`):
  - `MIGRATIONEN: Path` = Ordner `app/migrationen`.
  - `def verbinde(db_pfad: Path) -> sqlite3.Connection` — `isolation_level=None` (Transaktionen steuert der Code selbst), `row_factory = sqlite3.Row`, Pragmas `foreign_keys = ON`, `journal_mode = WAL`, `busy_timeout = 5000`.
  - `def migriere(conn: sqlite3.Connection, verzeichnis: Path = MIGRATIONEN) -> int` — führt alle `NNN_*.sql` mit `NNN > user_version` aufsteigend aus, gibt die neue Version zurück.
  - `def hole_db(request: Request) -> Iterator[sqlite3.Connection]` — FastAPI-Dependency: öffnet `verbinde(request.app.state.einstellungen.db_pfad)`, yieldet, schliesst im `finally`.

**Algorithmus `migriere`** (weil `executescript` sonst selbst committet): pro Datei
`conn.executescript(f"BEGIN IMMEDIATE;\n{sql}\nPRAGMA user_version = {nummer};\nCOMMIT;")`, bei Exception `conn.execute("ROLLBACK")` falls `conn.in_transaction`, dann erneut werfen. Vor jeder Datei `user_version` neu lesen (ein zweiter Prozess könnte schon migriert haben).

**Schema 001** (Spalten exakt wie im Spec, Abschnitt «Grundschema»). Verbindliche Details:
- Alle Tabellen `STRICT`, `id INTEGER PRIMARY KEY`.
- `konten.benutzername TEXT NOT NULL UNIQUE COLLATE NOCASE`; `rolle TEXT NOT NULL CHECK (rolle IN ('lehrperson','auftraggeberin'))`; `sitzungsversion INTEGER NOT NULL DEFAULT 1`.
- Zeitstempel-Spalten `TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ','now'))`.
- `fragen.typ CHECK (typ IN ('freitext','skala'))`, `fragen.runde_id ... REFERENCES runden(id) ON DELETE CASCADE`.
- `antworten.frage_id ... REFERENCES fragen(id) ON DELETE RESTRICT`, `antworten.konto_id ... ON DELETE CASCADE`, `antworten.aufnahme_id ... ON DELETE SET NULL`, `UNIQUE (frage_id, konto_id)`, `skalawert INTEGER` (nullable).
- `tagebucheintraege.art CHECK (art IN ('frei','leitfragen','aufnahme','impuls'))`, `konto_id ... ON DELETE CASCADE`, `impuls_id`/`leitfrage_id`/`aufnahme_id ... ON DELETE SET NULL`, `impuls_text TEXT`, `leitfrage_text TEXT`.
- `aufnahmen.dateiname TEXT NOT NULL UNIQUE`, `konto_id ... ON DELETE CASCADE`.
- Indizes: `antworten(konto_id)`, `tagebucheintraege(konto_id)`, `fragen(runde_id)`.

- [ ] **Step 1: Failing tests** in `tests/test_db.py` (Hilfs-Fixture `conn` = `verbinde(tmp_path / "t.db")`):
  - `test_migration_legt_alle_tabellen_an`: nach `migriere(conn)` enthält `sqlite_master` genau die Tabellen `konten, einstellungen, texte, info_abschnitte, runden, fragen, leitfragen, impulse, aufnahmen, antworten, tagebucheintraege`; Rückgabewert `1`; `PRAGMA user_version` = 1.
  - `test_migration_ist_idempotent`: zweimal `migriere` → zweites Mal `1`, keine Exception.
  - `test_pragmas_aktiv`: `PRAGMA foreign_keys` = 1, `PRAGMA journal_mode` = `"wal"`.
  - `test_konto_loeschen_entfernt_eintraege`: Konto + Runde + Frage + Antwort + Tagebucheintrag + Aufnahme anlegen, Konto löschen → Antwort, Tagebucheintrag, Aufnahme weg.
  - `test_frage_mit_antwort_nicht_loeschbar`: Frage mit Antwort löschen → `sqlite3.IntegrityError`.
  - `test_runde_mit_beantworteter_frage_nicht_loeschbar`: Runde löschen → `sqlite3.IntegrityError`; Runde ohne Antworten löschen → Fragen weg.
  - `test_impuls_loeschen_behaelt_eintrag`: Eintrag mit `impuls_id` und `impuls_text="Platzhalter-Impuls"`, Impuls löschen → Eintrag da, `impuls_id IS NULL`, `impuls_text` unverändert.
  - `test_benutzername_eindeutig_ohne_gross_klein`: `Anna` und `anna` einfügen → `sqlite3.IntegrityError`.
  - `test_ungueltige_rolle_abgelehnt`: `rolle='gast'` → `sqlite3.IntegrityError`.
  - `test_fehlerhafte_migration_rollt_zurueck`: eigenes `tmp_path`-Verzeichnis mit `001_ok.sql` (`CREATE TABLE a (x INTEGER);`) und `002_kaputt.sql` (`CREATE TABLE b (x INTEGER); SELEKT;`) → `migriere(conn, verzeichnis)` wirft `sqlite3.Error`; `user_version` = 1, Tabelle `b` existiert nicht, Tabelle `a` existiert.
- [ ] **Step 2:** `uv run pytest tests/test_db.py -v` → FAIL.
- [ ] **Step 3:** `app/db.py` und `001_grundschema.sql` implementieren.
- [ ] **Step 4:** `uv run pytest -v` → PASS; Ruff sauber.
- [ ] **Step 5:** Commit `feat: SQLite-Grundschema mit Migrationen (#13)`.

### Task 3: App, Seiten und Sicherheits-Header

**Files:**
- Create: `app/main.py`, `app/sicherheit.py`, `app/templates/basis.html`, `app/templates/start.html`, `app/static/css/style.css` (Kopie von `prototyp/css/style.css`, Kopfkommentar angepasst auf «Reflexionsinstrument – Pilot»), `tests/test_app.py`, `tests/test_sicherheit.py`
- Modify: `tests/conftest.py` (Fixture `client`)

**Interfaces:**
- Consumes: `Einstellungen`, `lade_einstellungen` (Task 1); `verbinde`, `migriere`, `hole_db` (Task 2).
- Produces:
  - `app/sicherheit.py`: `def sicherheits_header(produktion: bool) -> dict[str, str]` (Werte exakt wie Spec-Tabelle «Sicherheit»; HSTS nur bei `produktion`), `class SicherheitsHeaderMiddleware` (reine ASGI-Middleware, setzt die Header auf jede HTTP-Antwort, auch Fehler; Konstruktor `(app, produktion: bool)`).
  - `app/main.py`: `def erstelle_app(einstellungen: Einstellungen | None = None) -> FastAPI` — ohne Argument `lade_einstellungen()`. Speichert `app.state.einstellungen`. Lifespan: `daten_verzeichnis` und `aufnahmen_verzeichnis` mit `mkdir(parents=True, exist_ok=True)` anlegen, dann `migriere(verbinde(db_pfad))` und Verbindung schliessen. Mountet `/static`. Modulweite `templates = Jinja2Templates(directory=<app/templates>)`, die spätere Issues importieren. Kein modulweites `app`-Objekt; uvicorn startet mit `--factory app.main:erstelle_app`. `docs_url=None, redoc_url=None, openapi_url=None` (keine öffentliche API-Doku).
  - Routen: `GET /` → `start.html` (HTML 200); `GET /healthz` → `{"status": "ok"}` nach `SELECT 1` über `hole_db`, bei `sqlite3.Error` 503 mit `{"status": "fehler"}`.
  - `basis.html`: `<!doctype html>`, `<html lang="de">`, Meta charset + viewport, `<title>{% block titel %}Reflexionsinstrument{% endblock %}</title>`, nur `<link rel="stylesheet" href="/static/css/style.css">`, Blöcke `titel` und `inhalt`. Seitenstruktur mit den Klassen des Prototyps (Container/Karte aus `style.css` übernehmen, nichts Neues erfinden).
  - `start.html`: Überschrift «Reflexionsinstrument», eine Karte mit «Die Pilot-Version ist im Aufbau.»
- Produces (`tests/conftest.py`): Fixture `client(einstellungen)` → `with TestClient(erstelle_app(einstellungen)) as c: yield c` (der `with`-Block löst den Lifespan aus).

- [ ] **Step 1: Failing tests** in `tests/test_app.py`:
  - `test_start_legt_datenverzeichnis_an`: vor dem Client existiert `einstellungen.daten_verzeichnis` nicht; nach Start existieren Verzeichnis, `aufnahmen/` und `reflexion.db` mit `user_version` 1.
  - `test_healthz`: 200, JSON `{"status": "ok"}`.
  - `test_startseite_rendert`: 200, `text/html`, enthält `Reflexionsinstrument`, `lang="de"` und `/static/css/style.css`.
  - `test_startseite_ohne_externe_quellen`: Antworttext enthält weder `http://` noch `https://` noch `<script` noch ` style=`.
  - `test_css_wird_ausgeliefert`: `GET /static/css/style.css` → 200, `text/css`, enthält `--papier`.
  - `test_keine_api_doku`: `GET /docs` und `GET /openapi.json` → 404.
- [ ] **Step 2: Failing tests** in `tests/test_sicherheit.py`:
  - `test_header_gesetzt`: `GET /` hat `content-security-policy` exakt wie Spec, `x-content-type-options: nosniff`, `referrer-policy: no-referrer`, `permissions-policy: microphone=(self), camera=(), geolocation=()`, `x-frame-options: DENY`.
  - `test_kein_hsts_ohne_produktion`: kein `strict-transport-security`.
  - `test_hsts_in_produktion`: App mit `Einstellungen(..., produktion=True)` → `strict-transport-security: max-age=31536000`.
  - `test_header_auch_bei_404`: `GET /gibt-es-nicht` → 404 mit `content-security-policy`.
- [ ] **Step 3:** `uv run pytest -v` → neue Tests FAIL.
- [ ] **Step 4:** Implementieren.
- [ ] **Step 5:** `uv run pytest -v` → PASS; Ruff sauber. Kurz lokal starten: `DATEN_VERZEICHNIS=.daten uv run uvicorn --factory app.main:erstelle_app --port 8000` und `curl -s localhost:8000/healthz` → `{"status":"ok"}`.
- [ ] **Step 6:** Commit `feat: App-Gerüst mit Startseite, Health-Check und Sicherheits-Headern (#13)`.

### Task 4: Makefile, CI, Container und fly.io-Konfiguration

**Files:**
- Create: `Makefile`, `.github/workflows/ci.yml`, `Dockerfile`, `docker-entrypoint.sh`, `.dockerignore`, `fly.toml`
- Modify: `README.md` (Abschnitt «Pilot-Version»: lokal starten, prüfen, deployen über `make help`; Prototyp-Abschnitt bleibt)

**Interfaces:**
- Consumes: `erstelle_app` (Factory, Task 3).
- Produces: Make-Ziele `help` (Standard; listet Ziele mit `## Beschreibung`-Kommentaren), `install`, `dev`, `test`, `lint`, `format`, `deploy`, `logs`, `ssh`.

Verbindliche Werte:
- `make dev`: `DATEN_VERZEICHNIS=.daten uv run uvicorn --factory app.main:erstelle_app --reload --port 8000`.
- `ci.yml`: Name `CI`, Trigger `push` auf `main` und `pull_request`, `permissions: contents: read`, Job auf `ubuntu-latest`: `actions/checkout`, `astral-sh/setup-uv`, dann `uv sync --frozen`, `uv run ruff check`, `uv run ruff format --check`, `uv run pytest`. Beide Actions auf den Commit-SHA des aktuellen Release-Tags gepinnt, Tag als Kommentar (`# v4.2.2`). SHA mit `gh api repos/<owner>/<repo>/git/ref/tags/<tag>` ermitteln (bei annotierten Tags dem `object.url` bis zum Commit folgen).
- `Dockerfile`: `FROM python:3.13-slim`, `COPY --from=ghcr.io/astral-sh/uv:<feste Version> /uv /bin/uv`, `ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/opt/venv PATH=/opt/venv/bin:$PATH`, zuerst `pyproject.toml uv.lock .python-version` kopieren und `uv sync --frozen --no-dev --no-install-project`, dann `app/` kopieren. `useradd --uid 1001 appuser`, Entrypoint wie Munica (`chown -R appuser:appuser /data` wenn vorhanden, dann `exec setpriv --reuid=appuser --regid=appuser --init-groups --no-new-privs "$@"`). `CMD ["uvicorn", "--factory", "app.main:erstelle_app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers", "--forwarded-allow-ips", "*"]`. `EXPOSE 8080`.
- `.dockerignore`: alles ausser `app/`, `pyproject.toml`, `uv.lock`, `.python-version`, `docker-entrypoint.sh` (Allowlist mit `*` und `!`-Einträgen), damit `intern/`, `.daten/`, `prototyp/` nie im Image landen.
- `fly.toml`: `app = "reflexion-pilot"`, `primary_region = "fra"`, `[env] DATEN_VERZEICHNIS = "/data"`, `PRODUKTION = "1"`; `[mounts] source = "daten"`, `destination = "/data"`; `[http_service] internal_port = 8080`, `force_https = true`, `auto_stop_machines = "stop"`, `auto_start_machines = true`, `min_machines_running = 0`; Check `GET /healthz` (interval 30s, timeout 5s, grace_period 10s); `[[vm]] size = "shared-cpu-1x"`, `memory = "256mb"`. Kurzer Kopfkommentar: Deploy lokal mit `make deploy`, Secret `GEHEIMER_SCHLUESSEL` per `fly secrets set`.

- [ ] **Step 1:** Dateien anlegen.
- [ ] **Step 2:** `make help` → listet alle Ziele mit Beschreibung. `make lint test` → grün.
- [ ] **Step 3:** `fly config validate` → gültig (braucht kein Deployment).
- [ ] **Step 4:** Docker-Build prüfen, falls ein Docker-Daemon läuft (`docker info`): `docker build -t reflexion-pilot .` und `docker run --rm -e DATEN_VERZEICHNIS=/tmp/d -p 8081:8080 reflexion-pilot` + `curl localhost:8081/healthz`. Läuft kein Daemon, Schritt im Bericht als «nicht lokal geprüft, Build erfolgt beim Deploy remote» vermerken.
- [ ] **Step 5:** Commit `feat: Makefile, CI, Container und fly.io-Konfiguration (#13)`.

### Task 5: E2E-Prüfung der Pilot-Version im Browser

**Files:**
- Create: `tests/e2e-pilot.mjs`
- Modify: `Makefile` (Ziel `e2e`), `README.md` (Prüf-Tabelle), `.gitignore` falls nötig (Ausgabe liegt in `tests/.e2e/`, schon ignoriert)

**Interfaces:**
- Consumes: CDP-Muster aus `tests/e2e-prototyp.mjs` (Chrome-Start, Websocket, Screenshot) — übernehmen, aber statt eigenem statischen Server die App starten: `uv run uvicorn --factory app.main:erstelle_app --port <frei>` mit `DATEN_VERZEICHNIS` = temporärer Ordner unter `tests/.e2e/daten-pilot/`, warten bis `/healthz` 200 liefert, am Ende App und Chrome beenden.
- Chrome-Pfad aus `CHROME_PFAD`, Standard `/Applications/Google Chrome.app/Contents/MacOS/Google Chrome`.
- Produces: wiederverwendbares Gerüst (Hilfsfunktionen `oeffne(pfad)`, `screenshot(name)`, `pruefe(bedingung, text)`), auf das #14–#19 ihre Abläufe aufsetzen. Screenshots nach `tests/.e2e/bilder-pilot/`.

Prüfungen in #13:
- Startseite in 390 px Breite: Titel sichtbar, kein horizontales Scrollen (`scrollWidth <= innerWidth`), Screenshot hell und dunkel (`Emulation.setEmulatedMedia` mit `prefers-color-scheme`).
- Keine CSP-Verletzungen und keine Konsolenfehler (Events `Runtime.consoleAPICalled` Typ `error`, `Log.entryAdded` Level `error`).
- Desktop-Breite 1280 px: Screenshot.
- Exit-Code 1 bei einer fehlgeschlagenen Prüfung, Ausgabe pro Prüfung eine Zeile `ok …`/`FEHLER …`.

- [ ] **Step 1:** Skript schreiben, `make e2e` ergänzen.
- [ ] **Step 2:** `make e2e` → alle Prüfungen `ok`, Exit 0, drei Screenshots vorhanden.
- [ ] **Step 3:** Gegenprobe: in einer Kopie der Startseite kurzzeitig `style="color:red"` einfügen → Skript meldet CSP-Fehler. Danach rückgängig machen (nicht committen).
- [ ] **Step 4:** Commit `test: E2E-Prüfung der Pilot-Version im Headless-Chrome (#13)`.

### Task 6 (Controller, nach Freigabe durch Koschi): Erster Deploy und Nachweise

Nicht an einen Subagenten delegieren. Vor dem ersten Befehl Koschi fragen.

- [ ] `fly apps create reflexion-pilot --org personal` (Name vergeben → neutralen Ersatz wählen, in `fly.toml` nachziehen)
- [ ] `fly volumes create daten --region fra --size 1 -a reflexion-pilot -y`
- [ ] `fly secrets set GEHEIMER_SCHLUESSEL=$(python3 -c "import secrets;print(secrets.token_urlsafe(48))") -a reflexion-pilot --stage`
- [ ] `make deploy`
- [ ] Nachweise: `curl -s https://reflexion-pilot.fly.dev/healthz` → `{"status":"ok"}`; `curl -sI http://reflexion-pilot.fly.dev/` → 301 auf https; `curl -sI https://…/` → CSP und HSTS vorhanden.
- [ ] Persistenz (als `appuser`, sonst gehören WAL-Dateien root und die App kann nicht mehr schreiben): `fly ssh console -C "setpriv --reuid=appuser --regid=appuser --init-groups …"` mit "python -c \"import sqlite3;c=sqlite3.connect('/data/reflexion.db');c.execute(\\\"INSERT OR REPLACE INTO einstellungen VALUES ('nachweis_persistenz','<Zeitstempel>')\\\");c.commit()\""`, `fly machine restart <id>`, dann Wert lesen → gleich. Danach Zeile löschen.
