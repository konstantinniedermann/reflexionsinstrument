# Design: Grundgerüst der Pilot-Version (#13)

Grundlage: [Anforderungen](../../anforderungen.md), [ADR-001](../../adr/ADR-001-technik-pilot.md). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»). Wo es eine Alternative gab, steht die Begründung dabei.

## Zweck

Ein lauffähiges, leeres Gerüst auf fly.io, auf dem #14 (Anmeldung), #15 (Eingabemaske), #16 (Lehrpersonen-Ansicht) und #17–#19 aufbauen. Das Gerüst legt die Muster fest, die alle späteren Issues übernehmen: Aufbau des Pakets, Zugriff auf die Datenbank, Migrationen, Templates, Tests und Deployment. Fachliche Funktionen gehören nicht dazu.

## Ziele

- Die App läuft lokal (`make dev`) und auf fly.io unter einer neutralen `fly.dev`-Adresse in Frankfurt.
- Das Datenbankschema für alle Bausteine der Anforderungen besteht und wird beim Start automatisch angelegt oder nachgeführt.
- Datenbank und Aufnahmen liegen auf einem Volume und überleben einen Neustart der Maschine.
- Die Seiten haben den Stil des Prototyps, ohne externe Schriften oder Skripte.
- Sicherheits-Header und HTTPS sind von Anfang an aktiv.
- Die CI prüft Ruff und pytest. `make help` listet alle Befehle.

## Nicht-Ziele

- Login, Konten, Sitzungen (#14). Die Startseite ist vorerst eine Platzhalter-Seite «Im Aufbau».
- Formulare, Ansichten, Aufnahmen, Export (#15–#19).
- Automatisches Deployment aus GitHub. Deployt wird lokal mit `make deploy` (Begründung unten).
- E2E in der CI (bleibt lokal, siehe `docs/beobachtungen.md`).

## Anti-Ziele

- Kein ORM, kein Frontend-Build, keine Dependencies ausserhalb der Liste in ADR-001.
- Keine Muster, die später jedes Issue umbauen muss. Das Gerüst ist absichtlich klein, aber die Ordner, Namen und Hilfsfunktionen sind die, mit denen weitergebaut wird.

## Aufbau

```
app/
  __init__.py
  main.py            FastAPI-App, Lebenszyklus (Migration beim Start), Routen /, /healthz
  config.py          Einstellungen aus Umgebungsvariablen
  db.py              Verbindung, Migrationen, Dependency für Routen
  sicherheit.py      Middleware für Sicherheits-Header
  migrationen/
    001_grundschema.sql
  templates/
    basis.html       Grundlayout (Kopf, Hauptbereich), lädt nur /static/css/style.css
    start.html       Platzhalter «Im Aufbau»
  static/css/style.css   aus prototyp/css/style.css übernommen
tests/
  conftest.py        App mit temporärem Datenverzeichnis
  test_db.py, test_app.py, test_sicherheit.py
pyproject.toml, uv.lock, .python-version
Dockerfile, docker-entrypoint.sh, .dockerignore, fly.toml
Makefile
.github/workflows/ci.yml
```

Die Python-Tests liegen in `tests/` neben den Tests des Prototyps. pytest sammelt nur `test_*.py`, Node nur `*.test.js`. Der Prototyp und seine Tests fallen nach dem Start weg.

## Konfiguration

| Variable | Bedeutung | Standard lokal | fly.io |
|---|---|---|---|
| `DATEN_VERZEICHNIS` | Ordner für `reflexion.db` und `aufnahmen/` | `./.daten` (gitignored) | `/data` (Volume) |
| `GEHEIMER_SCHLUESSEL` | Signatur der Sitzungs-Cookies (wird ab #14 gebraucht) | fester Entwicklungswert, mit Warnung | `fly secrets set` |
| `PRODUKTION` | `1` schaltet HSTS ein und verweigert den Start ohne `GEHEIMER_SCHLUESSEL` oder mit einem Schlüssel unter 32 Zeichen | aus | `1` in `fly.toml` |

`config.py` liest diese einmal und stellt ein unveränderliches Einstellungs-Objekt bereit. Tests setzen ein eigenes Datenverzeichnis.

## Datenbank

- SQLite aus der Standardbibliothek, eine Datei `reflexion.db` im Datenverzeichnis.
- Pro Verbindung: `PRAGMA foreign_keys = ON`, `journal_mode = WAL`, `busy_timeout = 5000`, `row_factory = sqlite3.Row`.
- Pro Anfrage eine Verbindung über eine FastAPI-Dependency (`hole_db`), die am Ende geschlossen wird. Bei 5 Personen genügt das; kein Pool.
- **Migrationen:** nummerierte SQL-Dateien in `app/migrationen/`. Der Stand steht in `PRAGMA user_version`. Beim Start werden alle Dateien mit höherer Nummer der Reihe nach in einer Transaktion ausgeführt. Spätere Issues fügen `002_….sql` usw. hinzu und ändern bestehende Dateien nie. Kein Zurückrollen (YAGNI: die Datenbank lebt vier Wochen).
- Zeitstempel als ISO-Text in UTC (`strftime('%Y-%m-%dT%H:%M:%SZ','now')`), Daten (Freischaltung, Projektstart) als `YYYY-MM-DD`.

### Grundschema (001)

| Tabelle | Spalten (Kurzform) | Zweck |
|---|---|---|
| `konten` | id, anzeigename, benutzername (eindeutig, ohne Gross-/Kleinschreibung), passwort_hash, rolle (`lehrperson`/`auftraggeberin`), sitzungsversion (Standard 1), erstellt | Anmeldung, Rollen, Widerruf von Sitzungen |
| `einstellungen` | schluessel (PK), wert | Projektstart und weitere Einzelwerte |
| `texte` | schluessel (PK), inhalt, geaendert | feste Texte als Inhalt: Begrüssung, Hinweistexte |
| `info_abschnitte` | id, titel, inhalt, reihenfolge | Infoblock |
| `runden` | id, titel, fallbeispiel (optional), freischaltdatum, reihenfolge | Runden |
| `fragen` | id, runde_id → runden (Kaskade), typ (`freitext`/`skala`), text, skala_min_text, skala_max_text, reihenfolge | Fragen einer Runde |
| `leitfragen` | id, text, reihenfolge | Leitfragen fürs Tagebuch |
| `impulse` | id, text, sichtbar_ab | wöchentliche Impulse |
| `aufnahmen` | id, konto_id → konten (Kaskade), dateiname (eindeutig), mime_typ, groesse_bytes, erstellt | Sprachaufnahmen als Dateien |
| `antworten` | id, frage_id → fragen (**gesperrt**, solange Antworten bestehen), konto_id → konten (Kaskade), text, skalawert, aufnahme_id → aufnahmen (bei Löschen leeren), erstellt, geaendert; eindeutig (frage_id, konto_id) | eine aktuelle Antwort pro Frage und Lehrperson |
| `tagebucheintraege` | id, konto_id → konten (Kaskade), art (`frei`/`leitfragen`/`aufnahme`/`impuls`), text, impuls_id → impulse (bei Löschen leeren), impuls_text, leitfrage_id → leitfragen (bei Löschen leeren), leitfrage_text, aufnahme_id → aufnahmen (bei Löschen leeren), erstellt, geaendert | Tagebuch |

**Schutz der Forschungsdaten (Entscheidung Claude):** Inhalte werden auch während der Laufzeit bearbeitet. Ein Fehlklick darf keine Einträge der Lehrpersonen löschen. Deshalb:
- Eine Frage mit Antworten lässt sich nicht löschen (`ON DELETE RESTRICT`). Damit lässt sich auch eine Runde mit beantworteten Fragen nicht löschen, weil die Kaskade Runde → Fragen an der Sperre scheitert. #15 zeigt dafür eine verständliche Meldung. Texte ändern bleibt möglich.
- Tagebucheinträge zu einem Impuls oder einer Leitfrage speichern deren Text beim Anlegen mit (`impuls_text`, `leitfrage_text`). Der Export weiss so auch nach dem Löschen eines Impulses, worauf sich ein Eintrag bezog.
- Nur das Löschen eines Kontos entfernt Einträge (gewollt, für Testkonten und auf Wunsch).

SQLite kann Fremdschlüssel-Regeln nicht nachträglich ändern. Darum stehen diese Regeln schon in 001.

Die Skala-Bezeichnungen und die Verknüpfung Tagebuch–Leitfrage sind Annahmen von Claude. Ergibt sich in #15/#16 etwas anderes, kommt eine neue Migration dazu. Die Dateien der Aufnahmen löscht die App selbst; die Kaskade in der Datenbank entfernt nur die Zeilen (#14/#17 kümmern sich darum).

## Seiten und Routen

- `GET /` → `start.html`: Titel «Reflexionsinstrument», Karte «Die Pilot-Version ist im Aufbau.» Ab #14 wird daraus die Login-Seite.
- `GET /healthz` → `{"status": "ok"}`, führt `SELECT 1` aus, bei Fehler 503. Fly prüft diese Adresse.
- `/static` → `app/static` über StaticFiles.
- Templates über `Jinja2Templates` mit Autoescape (Standard). `basis.html` setzt `lang="de"`, Viewport, `<link rel="stylesheet" href="/static/css/style.css">` und sonst nichts von aussen.

## Sicherheit

Middleware für jede Antwort:

| Header | Wert |
|---|---|
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'` |
| `Strict-Transport-Security` | `max-age=31536000` (nur bei `PRODUKTION=1`; ohne `includeSubDomains`, weil `fly.dev` nicht uns gehört) |
| `X-Content-Type-Options` | `nosniff` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `microphone=(self), camera=(), geolocation=()` |
| `X-Frame-Options` | `DENY` |

HTTPS erzwingt fly.io (`force_https = true`): Anfragen über HTTP werden umgeleitet. Kein Inline-JavaScript und kein Inline-CSS, damit die CSP ohne `unsafe-inline` auskommt. Das gilt auch für alle späteren Issues.

## Container und fly.io

- `Dockerfile`: `python:3.13-slim`, uv aus dem offiziellen Image kopiert, `uv sync --frozen --no-dev` aus `uv.lock`. So installiert der Build genau die geprüften Versionen. (Munica hatte Ausfälle, weil der Build ohne Lockfile frei auflöste.)
- Nicht-root: Entrypoint startet als root, chownt `/data` (fly mountet das Volume als root) und wechselt per `setpriv` auf `appuser`, wie bei Munica. `exec`, damit uvicorn Signale direkt bekommt.
- `uvicorn app.main:app --host 0.0.0.0 --port 8080 --proxy-headers --forwarded-allow-ips "*"` (fly-Proxy davor).
- `fly.toml`: App-Name `reflexionsinstrument` (neutral, ohne Personen- oder Schulnamen; von Koschi angelegt), `primary_region = "fra"`, Volume `daten` (1 GB) auf `/data`, `force_https`, `auto_stop_machines = "stop"`, `min_machines_running = 0`, Health-Check auf `/healthz`, VM `shared-cpu-1x`, 256 MB.
- **Deployment lokal mit `make deploy`** statt über GitHub Actions: So liegt kein fly-Token in GitHub, und das Repo ist öffentlich. Bei einem Betreiber und vier Wochen Laufzeit spart Automatik nichts.
- Der erste Deploy (App anlegen, Volume, Secret) geht nach aussen und kostet Geld. Davor fragt Claude Koschi einmal. Er steht als letzte, abtrennbare Aufgabe im Plan. Der Pull Request wird erst nach dem Deploy und den Nachweisen auf fly.io gemergt, weil diese zur DoD gehören. Organisation: `reflexion`, eigens von Koschi angelegt, damit die Kosten getrennt von seinen übrigen Apps abgerechnet werden.

## CI

`.github/workflows/ci.yml`, bei Push auf `main` und bei Pull Requests: Checkout, uv einrichten, `uv sync --frozen`, `ruff check`, `ruff format --check`, `pytest`. Alle Actions auf Commit-SHAs gepinnt, mit Versionskommentar. Den Prototyp-Workflow passt dieses Issue nicht an. Seine Actions bleiben vorerst über Tags eingebunden (Beobachtungseintrag), er fällt mit dem Prototyp weg.

## Makefile

`make help` (Standardziel), `install` (`uv sync`), `dev` (uvicorn mit Reload auf Port 8000), `test` (pytest), `lint` (ruff check + format --check), `format`, `deploy` (`fly deploy`), `logs` (`fly logs`), `ssh` (`fly ssh console`).

## Prüfung und Nachweis

- **pytest:** Migration auf leerer Datenbank (alle Tabellen da, `user_version` = 1), Migration ist idempotent (zweiter Start ändert nichts), Fremdschlüssel aktiv (Kaskade beim Löschen eines Kontos), `/healthz` antwortet 200, `/` rendert und enthält keine externen Adressen, alle Sicherheits-Header gesetzt, HSTS nur mit `PRODUKTION=1`, Start mit `PRODUKTION=1` ohne Schlüssel schlägt fehl, `/static/css/style.css` wird ausgeliefert.
- **Lokal:** Screenshot der Startseite in 390 px Breite (Headless Chrome, wie beim Prototyp), hell und dunkel.
- **fly.io (DoD):** `curl https://<app>.fly.dev/healthz` antwortet 200. HTTP leitet auf HTTPS um. Header per `curl -I` geprüft. Persistenz: per `fly ssh console` eine Zeile in `einstellungen` schreiben, `fly machine restart`, Zeile wieder lesen.
- **CI grün** auf dem Pull Request.

## Dem Umsetzer überlassen

Genaue Formulierung der Platzhalter-Seite, Aufteilung der Tests auf Dateien, Ruff-Regelauswahl (Standard plus `I` für Importsortierung), Versionsgrenzen in `pyproject.toml` (untere Grenzen, das Lockfile pinnt).
