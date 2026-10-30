# Reflexionsinstrument für Lehrpersonen

Eine einfache Anwendung, mit der Lehrpersonen zu mehreren Zeitpunkten ein Reflexionsinstrument ausfüllen und ein Tagebuch führen. Jede Lehrperson sieht nur ihre eigenen Einträge. Die Projektverantwortliche sieht alle Einträge mit Namen, und die Lehrpersonen wissen das vorher.

## Stand

Die Anforderungen an die Pilot-Version stehen in [docs/anforderungen.md](docs/anforderungen.md), die Technik in [docs/adr/ADR-001-technik-pilot.md](docs/adr/ADR-001-technik-pilot.md). Die Pilot-Version ist im Aufbau: Das Grundgerüst läuft unter https://reflexionsinstrument.fly.dev. Es gibt die Anmeldung (Login und Abmelden), die Verwaltung der Zugänge für Lehrpersonen und die Eingabemaske für alle Inhalte (Titel und Begrüssung, Infoblock, Runden mit Fragen, Leitfragen, Impulse, Hinweise) durch die Auftraggeberin sowie die Lehrpersonen-Ansicht (Runden, Tagebuch, Meine Einträge).

Der **klickbare Wegwerf-Prototyp** hat dazu gedient, Feedback zu holen. Er ist nicht die Pilot-Version. Aufbau und Entscheidungen: [docs/prototyp.md](docs/prototyp.md).

- Online: https://konstantinniedermann.github.io/reflexionsinstrument/
- Lokal: `prototyp/index.html` im Browser öffnen (Doppelklick genügt)

Alle Texte im Prototyp sind Platzhalter. Eingaben bleiben im jeweiligen Browser.

## Pilot-Version

Voraussetzung: [uv](https://docs.astral.sh/uv/). Alle Befehle stehen in `make help`.

| Befehl | Zweck |
|---|---|
| `make install` | Abhängigkeiten installieren |
| `make dev` | App lokal starten auf http://localhost:8000 (Daten in `.daten/`) |
| `make lint test` | Code, Formatierung und Tests prüfen (läuft auch in der CI) |
| `make platzhalter` | Erfundene Platzhalter-Inhalte in `.daten/` laden (nie in Produktion) |
| `make e2e` | App im Headless-Chrome prüfen (Login, Zugänge anlegen, Zugriffsschutz, Eingabemaske für Inhalte, Lehrpersonen-Ansicht mit Runden, Tagebuch und Meine Einträge; Handy- und Desktop-Breite, hell und dunkel), Screenshots in `tests/.e2e/bilder-pilot/`. Braucht Node ab 22 und Google Chrome, läuft nur lokal |
| `make deploy` | Auf fly.io veröffentlichen (Frankfurt), braucht die fly-CLI und eine Anmeldung |
| `make logs`, `make ssh` | Logs ansehen bzw. Shell auf der Maschine öffnen |

Einstellungen über Umgebungsvariablen: `DATEN_VERZEICHNIS` (Ablage der Datenbank), `GEHEIMER_SCHLUESSEL` (Sitzungen) und `PRODUKTION`. `PRODUKTION` gilt nur beim genauen Wert `1` als eingeschaltet. Im Produktionsbetrieb startet die App ohne `GEHEIMER_SCHLUESSEL` oder mit einem Schlüssel unter 32 Zeichen nicht. Den Schlüssel auf fly.io einmalig mit `fly secrets set GEHEIMER_SCHLUESSEL=...` setzen (zufällig, z. B. `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`).

### Erstes Konto der Auftraggeberin

Das Konto der Auftraggeberin entsteht einmalig per Kommando, danach legt sie die Zugänge der Lehrpersonen selbst in der Verwaltung an. Das Passwort wird nie als Argument übergeben: Im Terminal fragt das Kommando zweimal danach.

Lokal (Daten in `.daten/`):

```
uv run python -m app.kommandos auftraggeberin-anlegen --benutzername projektleitung --anzeigename Projektleitung
```

Auf fly.io, als `appuser`, damit die Datenbankdateien nicht `root` gehören:

```
fly ssh console --pty -C "setpriv --reuid=appuser --regid=appuser --init-groups python -m app.kommandos auftraggeberin-anlegen --benutzername … --anzeigename …"
```

Ein Anzeigename mit Leerzeichen steht in einfachen Anführungszeichen (`--anzeigename 'Vorname Nachname'`). Die Maschine schläft, wenn niemand die App benutzt, und `fly ssh` weckt sie nicht. Meldet es «has no started VMs», zuerst `fly machine start <ID>` (ID aus `fly status`) oder die Seite im Browser öffnen.

Hat die Auftraggeberin ihr Passwort vergessen, setzt dieses Kommando ein neues (gleich aufgerufen, auf fly.io mit demselben `setpriv`-Vorspann); alle bestehenden Anmeldungen dieses Kontos enden dabei:

```
uv run python -m app.kommandos passwort-setzen --benutzername projektleitung
```

### Platzhalter-Inhalte für die Entwicklung

Damit die Maske beim Entwickeln nicht leer ist, lädt ein Kommando erfundene Inhalte (Titel, Infoblock, Runden mit Fragen, Leitfragen, Impulse):

```
make platzhalter
```

Das ist `uv run python -m app.kommandos platzhalter-laden` mit `DATEN_VERZEICHNIS=.daten`. Gibt es schon Inhalte, bricht das Kommando ab; mit `--ersetzen` werden sie vorher gelöscht. Mit `PRODUKTION=1` verweigert das Kommando die Arbeit. Auf fly.io nie ausführen.

## Prüfen (Prototyp)

| Befehl | Prüft |
|---|---|
| `node --test tests/*.test.js` | Logik: Freischaltung der Runden, Trennung der Einträge, CSV-Export |
| `node tests/e2e-prototyp.mjs` | Durchklicken im Headless-Chrome in Handy-Breite, beide Rollen, Screenshots in `tests/.e2e/bilder/` |

Beides braucht nur Node (ab Version 22) und keine Dependencies. Die E2E-Prüfung braucht zusätzlich Google Chrome unter macOS und läuft nur lokal, nicht in der CI.

## Leitplanken

- Einfachheit vor Funktionsumfang, auf dem Handy bedienbar
- Datenschutz: minimal personenbezogene Daten, keine Kontaktdaten, Hosting in der EU (Frankfurt), Löschung nach Projektende ([Datenschutz](docs/datenschutz.md), [Löschkonzept](docs/loeschkonzept.md))
