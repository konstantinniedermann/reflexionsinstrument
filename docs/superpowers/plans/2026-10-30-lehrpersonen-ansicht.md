# Lehrpersonen-Ansicht — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eine Lehrperson sieht Startseite und Infoblock, beantwortet freigeschaltete Runden, schreibt Tagebucheinträge (frei, zum Impuls, zu einer Leitfrage), ändert und löscht alles unter «Meine Einträge», auf dem Handy und am Computer. Dazu kommen Migration 003, die Grössengrenze für Anfragen und die gemeinsamen Bausteine, auf denen #17, #18 und #19 parallel aufbauen.

**Architecture:** Fachlogik ohne FastAPI in `app/sichtbar.py` (was am Stichtag sichtbar ist, auf `app/inhalte.py` aus #15), `app/eintraege.py` (Antworten, Tagebuch, `Zeile`, `gruppiere`) und `app/aufnahmen.py` (Grundstock für Dateien). `app/ansicht.py` und `app/seiten_lehrperson.py` trennen Route und Darstellung, damit #19 dieselben Templates im Gast- und Vorschau-Modus nutzt. Routen in `app/routen/lehrperson.py`, Templates unter `app/templates/lehrperson/`. `app/groesse.py` begrenzt jede Anfrage auf 1 MiB (Upload-Routen von #17: 16 MiB).

**Tech Stack:** Python 3.13, FastAPI 0.162, Starlette 1.10, Jinja2 (`markupsafe`), sqlite3, `zoneinfo`, pytest, Node-E2E über CDP, eine kleine JavaScript-Datei ohne Build (Task 10).

**Spec:** `docs/superpowers/specs/2026-10-30-lehrpersonen-ansicht-design.md`. Vor jeder Task die genannten Abschnitte lesen; Texte, Meldungen und Begriffe stehen dort. Der Schlussabschnitt «Änderungen nach den Designs #17–#19» fasst zusammen, worauf sich #17–#19 verlassen; diese Festlegungen nicht abschwächen.

## Vorbereitung (vor Task 1, Orchestrator)

- Branch `feat/16-lehrpersonen-ansicht` von `main`, nachdem #15 gemergt ist. Design nach `docs/superpowers/specs/2026-10-30-lehrpersonen-ansicht-design.md` kopieren, `uv run ruff format --check docs/` (prüft die Python-Blöcke im Markdown), Commit `docs: Design der Lehrpersonen-Ansicht (#16)`.
- **Schnittstellen aus #14 und #15 prüfen** (der Plan geht von diesem Stand aus; weicht er ab, die betroffene Task anpassen und die Abweichung im Design nachführen):
  1. `app/typen.py`: `Id = Annotated[int, Path(ge=1, le=2**63 - 1)]`. `app/main.py`: Handler zeigt jeden `RequestValidationError` als 404; `FEHLERTEXTE` (Schlüssel 404, 405) wird von `http_fehler` über `FEHLERTEXTE.get(status, FEHLER_ALLGEMEIN)` gelesen; Middlewares in der Reihenfolge `CookieMiddleware`, dann `SicherheitsHeaderMiddleware` hinzugefügt.
  2. `app/sitzung.py`: `braucht_lehrperson(konto) -> Konto` setzt `request.state.konto`; `Konto(id, anzeigename, benutzername, rolle, sitzungsversion)`. `app/csrf.py`: `pruefe_csrf` liest `await request.form()`, `csrf_feld(request)` als Jinja-Global.
  3. `app/zeit.py`: `ZEITZONE`, `heute`, `hole_heute`, `lies_datum`, `ist_erreicht(datum, heute)`, `woche(datum, projektstart)`, `datum_kurz(datum, mit_jahr=True)`, `zeitplan`; `app.state.heute`. Der Test `test_nur_zeit_kennt_die_uhr` verbietet `date.today(`/`datetime.now(` ausserhalb von `zeit.py`.
  4. `app/vorlagen.py`: Filter `formatiert`, `datum` (leer bei `None`), Globals `zahl(anzahl, einzahl, mehrzahl)`, `zeitplan`, `konto_von`, `csrf_feld`, Context-Processor `instrument_titel`. `vorlagen` importiert `app.inhalte`; kein Fachmodul darf `vorlagen` importieren.
  5. `app/db.py`: `transaktion(db)` (verschachtelbar), `migriere` erlaubt Lücken (es gibt kein `002`).
  6. `app/eingaben.py`: `InhaltFehler(feld, meldung)` mit `.feld`, `.meldung`; `langer_text(wert, feld, leer_meldung)`, `LAENGE_LANG = 20_000`, `zu_lang`.
  7. `app/inhalte.py`: `SKALA_MIN`, `SKALA_MAX`, `runden(db)` (mit `anzahl_fragen`, nach `freischaltdatum, id`), `runde(db, runde_id)`, `fragen(db, runde_id)` (nach `reihenfolge, id`), `impulse(db)` (nach `sichtbar_ab, id`), `impuls(db, impuls_id)`, `leitfragen(db)`, `leitfrage(db, leitfrage_id)`, `info_abschnitte(db)`, `lies_projektstart(db)`. Die letzten fünf entstehen in #15, Tasks 5–6: Namen und Sortierung prüfen.
  8. `app/texte.py`: `lies_text(db, schluessel)`, `REGISTER` mit `begruessung`, `hinweis_tagebuch`, `hinweis_wer_sieht_was`, `hinweis_gast`, `hinweis_datenspeicherung`, `hinweis_aufnahme`.
  9. `tests/conftest.py`: Fixtures `einstellungen`, `client`, `lehrperson`, `zweite_lehrperson`, `auftraggeberin` (Dicts mit `id`, `benutzername`, `passwort`), `db`, `festes_heute`; Funktionen `anmelden`, `csrf_von`, `als_leitung`, `als_lehrperson`, `lege_antwort_an(db, frage_id, konto_id, text="Antwort", aufnahme_id=None)`, `lege_eintrag_an(db, konto_id, art="frei", impuls_id=None, leitfrage_id=None)`, importiert mit `from conftest import …` (u. a. in `tests/test_inhalte.py`, `tests/test_verwaltung_inhalte.py`).
  10. `app/templates/verwaltung/start.html` enthält die Schleife `{% for name in ["Einträge", "Vorschau"] %}`; `verwaltung/rahmen.html` die Links Übersicht, Inhalte, Zugänge.
  11. `tests/e2e-pilot.mjs`: `ablaeufe()` mit den Blöcken von #14 und #15; vor `starteApp()` laufen `auftraggeberin-anlegen` und `platzhalter-laden` **ohne** `--projektstart` (erster Tag = heute). `tests/platzhalter/inhalte.json`: Runden mit `tag` 0/7/14/21, ein Impuls mit `tag` 0, mindestens eine Leitfrage. Helfer `muss`, `pruefe`, `oeffne`, `tippe`, `sende`, `klick`, `text`, `js`, `pfad`, `ueberschrift`, `keinUeberlauf`, `merke`, `keineFehlerSeit`, `screenshot`, `handy`, `desktop`, `farbschema`.
  12. `app/static/css/style.css`: Prototyp-Klassen `.tabs`, `.karte`, `.karte--impuls`, `.karte--eintrag`, `.karte--link`, `.fall`, `.skala`, `.skala__pole`, `.aufklapp`, `.marke`, `.hinweis`; `.inhalt` mit 6rem Abstand unten; letzter Abschnitt `/* Pilot: Eingabemaske */`. SVG-Symbole der Leiste in `prototyp/index.html`.

## Global Constraints

- Keine neuen Dependencies. Erlaubt: Standardbibliothek, `fastapi`, `starlette`, `jinja2`, `markupsafe`. Kein JavaScript-Paket, kein Build.
- Bezeichner, Kommentare und Texte auf Deutsch, ohne ß; in Bezeichnern Umlaute ausgeschrieben. Oberfläche nach der Begriffstabelle der Spec, Anrede «du», keine Emojis, kein Chatbot-Ton. Nie «Datensatz», «ID», «Markdown».
- Kein Inline-JavaScript, kein `style=`, keine `on…=`-Attribute, keine externen Ressourcen. JavaScript nur `app/static/js/entwurf.js` (Task 10); die Seiten funktionieren ohne.
- CSS nur im Abschnitt `/* Pilot: Lehrpersonen-Ansicht */` von `style.css` (Task 1 legt ihn vor den drei Abschnitten für #17–#19 an).
- Einträge der Lehrpersonen nie `| formatiert`, nie `| safe`; Anzeige mit `white-space: pre-wrap` und `overflow-wrap: anywhere`. Begrüssung, Fallbeispiel, Abschnitte und Hinweise mit `| formatiert`; Fragen, Leitfragen und Impulse als reiner Text.
- Datum in Routen nur über `Depends(hole_heute)`, in `kontext_*` und `sichtbar.py` nur über `ansicht.stichtag` bzw. `stichtag`. Zeitstempel nur über `app/zeit.py`.
- Pfad-IDs immer `Id` aus `app/typen.py`. Formularfelder untypisiert `Annotated[str, Form()] = ""`; die dynamischen Felder `antwort_{frage_id}` liest die Route aus `await request.form()`.
- Jede POST-Route `dependencies=[Depends(pruefe_csrf)]`; nach Erfolg 303.
- Jede Abfrage auf `antworten`, `tagebucheintraege`, `aufnahmen` einer Lehrperson filtert in SQL nach `konto_id`. Fremd und unbekannt sind nicht unterscheidbar: 404, nichts geändert.
- Eine Runde oder ein Impuls über die ID nur über `sichtbare_runde`/`sichtbarer_impuls`, bei GET und POST.
- Schreiben über `transaktion(db)`. Einzige Migration ist `003_lehrpersonen_ansicht.sql`, `001` bleibt unverändert.
- Tippflächen mindestens `2.75rem` hoch. 390 px und 1280 px ohne horizontales Scrollen.
- Repo öffentlich: Testdaten erfunden und neutral.
- Commits: Präfix `feat:`/`test:`/`docs:`/`refactor:`/`fix:`, `(#16)` am Ende der ersten Zeile, Umlaute in der Commit-Zeile ausgeschrieben, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy8wrhdWVtdWcGb3tyj`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber. Der Ruff-Hook entfernt ungenutzte Imports zwischen Edits, deshalb Import und Verwendung im selben Edit schreiben.

## Review Focus

1. **Veraltetes Formular auf zwei Geräten:** Ein Formular, das vor dem Hinzufügen einer Frage geladen wurde, enthält deren Feld nicht. Speichern lässt die Antwort auf diese Frage unberührt, statt sie zu löschen. Eine Runde, deren Datum inzwischen in die Zukunft verschoben wurde, ergibt beim POST 404, nichts gespeichert. (Task 4 `test_fehlendes_feld_bleibt_unberuehrt`, Task 7 `test_post_nach_datumsaenderung_404`)
2. **Zurück-Taste und zweites Löschen:** Ein schon gelöschter Eintrag ergibt beim erneuten Löschen 404, nie 500; eine Aufnahme-Datei, die schon fehlt, verhindert das Löschen nicht. Neu laden nach dem Anlegen legt nichts doppelt an. (Task 8 `test_loeschen_doppelt_404`, `test_neu_laden_legt_nicht_doppelt_an`)
3. **Aus Word eingefügter oder feindlicher Text:** `\r\n`, `<script>`, `**fett**` und ein Wort aus 300 Zeichen erscheinen in Runde, Eintrag und «Meine Einträge» escapt, unformatiert und auf 390 px ohne horizontales Scrollen. (Task 7 `test_ausgabe_escapt`, Task 8 `test_eintrag_escapt_unformatiert`, Task 9 E2E «langes Wort»)
4. **Langer, normaler Text an der Grössengrenze:** Ein Tagebucheintrag mit 20 000 Zeichen deutschem Text mit vielen Umlauten wird gespeichert (303), nicht mit 413 abgewiesen. (Task 8 `test_langer_text_mit_umlauten_passt`)
5. **Fehler im Formular einer Runde:** Bei 400 bleiben alle Eingaben stehen, auch die gewählte Skala und der Text anderer Fragen, und nichts ist gespeichert. (Task 7 `test_fehler_400_behaelt_eingaben`)

---

### Task 1: Migration 003, Testdaten und Gerüst für #17–#19

Spec: «Migration 003», «Regel für #17, #18, #19», «Testdaten», «Aufbau im Code» (leere Router, Abschnitte, vorbereitete Plätze).

**Files:**
- Create: `app/migrationen/003_lehrpersonen_ansicht.sql`, `tests/testdaten.py`, `app/routen/aufnahmen.py`, `app/routen/verwaltung_eintraege.py`, `app/routen/gast.py`, `app/routen/verwaltung_vorschau.py`, `tests/test_migration_003.py`, `tests/test_testdaten.py`, `tests/test_geruest.py`
- Modify: `app/main.py` (vier Router einbinden), `tests/conftest.py` (Fixture `heute_ist`; `lege_antwort_an`, `lege_eintrag_an` entfernen), `tests/test_inhalte.py` und `tests/test_verwaltung_inhalte.py` (Import aus `testdaten`), `app/templates/verwaltung/start.html`, `app/templates/verwaltung/rahmen.html`, `app/static/css/style.css`, `tests/e2e-pilot.mjs`

**Interfaces:**
- Produces: Migration mit dem SQL aus der Spec, wörtlich. `tests/testdaten.py` mit den Signaturen aus der Spec «Testdaten» (`lege_runde_an`, `lege_impuls_an`, `lege_leitfrage_an`, `lege_antwort_an`, `lege_eintrag_an`, `lege_aufnahme_an`, `abzug`). Skala-Fragen bekommen die Beschriftungen `"wenig"`/`"viel"`, `reihenfolge` 1…n. `lege_aufnahme_an` schreibt `secrets.token_hex(16) + ".webm"` mit Inhalt `b"\x1aE\xdf\xa3" + bytes(60)` in `verzeichnis`, `mime_typ="audio/webm"`, `groesse_bytes` = Dateigrösse. `abzug` liest alle Tabellen aus `sqlite_master` (ohne `sqlite_%`), Zeilen als sortierte Tupel-Listen.
- Produces (`tests/conftest.py`): `heute_ist(client) -> Callable[[date], date]`: setzt `client.app.state.heute = lambda: datum` und gibt `datum` zurück.
- Produces (Router): je Datei `router = APIRouter()` mit einem Satz Docstring («Leer, wird in #17 gefüllt: …»), in `erstelle_app` nach `verwaltung_inhalte` mit `app.include_router(modul.router)` ohne `prefix`.
- Produces (Templates, CSS, E2E): genau die Kommentarzeilen und Abschnittsnamen aus der Spec. E2E: Funktionen `ablaufLehrperson`, `ablaufAufnahmen`, `ablaufEintraege`, `ablaufGast` (leer, je ein Kommentar «#NN füllt diese Funktion»), im Hauptablauf nach `await ablaeufe();` in dieser Reihenfolge aufgerufen; in `starteChrome()` die beiden Schalter `--use-fake-ui-for-media-stream` und `--use-fake-device-for-media-stream`.

- [ ] **Step 1: Failing tests** `tests/test_migration_003.py`:
  - `test_version_spalte_indizes(db)`: `PRAGMA user_version` == 3; `"dauer_sekunden"` in den Spaltennamen von `PRAGMA table_info(aufnahmen)`; `idx_antworten_aufnahme`, `idx_tagebucheintraege_aufnahme`, `idx_aufnahmen_konto` in `sqlite_master`.
  - `test_migration_erhaelt_daten(tmp_path)`: Ordner mit nur `001_grundschema.sql` (kopiert), `migriere(conn, ordner)` → 1; je eine Zeile in allen Tabellen; `vorher = testdaten.abzug(conn)`; `migriere(conn)` → 3; alle Tabellen ausser `aufnahmen` gleich `vorher`, `aufnahmen` gleich in den alten Spalten, `dauer_sekunden IS NULL`.
  - `test_aufnahme_nur_einmal(db, lehrperson, einstellungen)`: eine Aufnahme, zwei Tagebucheinträge mit derselben `aufnahme_id` → der zweite `sqlite3.IntegrityError`; ebenso zwei Antworten.
  - `test_dauer_nur_ganze_zahl(db, …)`: `UPDATE aufnahmen SET dauer_sekunden = 'x'` und `= -1` → je `IntegrityError`; `= 0` geht.
- [ ] **Step 2: Failing tests** `tests/test_testdaten.py`:
  - `test_lege_runde_an(db)`: Rückgabe `(rid, [f1, f2])`; `f1` Freitext, `f2` Skala mit beiden Beschriftungen, `reihenfolge` 1, 2; `freischaltdatum == "2026-11-23"`.
  - `test_lege_eintrag_kopiert_bezug(db, lehrperson)`: mit `impuls_id` → `impuls_text` = Text des Impulses; mit `leitfrage_id` → `leitfrage_text`.
  - `test_lege_aufnahme_an(db, lehrperson, einstellungen)`: `re.fullmatch(r"[0-9a-f]{32}\.webm", name)`; Datei im Aufnahmen-Ordner beginnt mit `b"\x1aE\xdf\xa3"`; `mime_typ == "audio/webm"`, `groesse_bytes` = Dateigrösse, `dauer_sekunden == 5`.
  - `test_abzug_alle_tabellen(db)`: Schlüssel == alle Tabellennamen des Schemas (11).
  - `test_heute_ist(client, heute_ist)`: `heute_ist(date(2026, 11, 22))` → `client.app.state.heute() == date(2026, 11, 22)`.
- [ ] **Step 3: Failing tests** `tests/test_geruest.py`:
  - `test_leere_router(…)`: für `aufnahmen`, `verwaltung_eintraege`, `gast`, `verwaltung_vorschau`: `modul.router.routes == []`.
  - `test_router_eingebunden_ohne_praefix(einstellungen, monkeypatch)`: pro Modul `monkeypatch.setattr(modul, "router", r)` mit `r.get(f"/geruest-{name}")` (gibt `"ok"` zurück), `erstelle_app`, `TestClient` → `GET /geruest-{name}` == 200.
  - `test_verwaltung_vorbereitete_plaetze`: In `start.html` und `rahmen.html` steht `{# #18:` vor der Trennzeile `{# Trennzeile zwischen #18 und #19, nicht ändern #}` vor `{# #19:`; `start.html` enthält kein `{% for name in`.
  - `test_verwaltung_unveraendert(client, auftraggeberin)`: `als_leitung`, `GET /verwaltung` enthält «Einträge», «Vorschau» und zweimal «folgt».
  - `test_css_abschnitte`: in `style.css` in dieser Reihenfolge `/* Pilot: Lehrpersonen-Ansicht */`, `/* Pilot: Aufnahmen (#17) */`, `/* Ende #17 */`, `/* Pilot: Einträge und Export (#18) */`, `/* Ende #18 */`, `/* Pilot: Gast und Vorschau (#19) */`, `/* Ende #19 */`.
  - `test_e2e_geruest`: `e2e-pilot.mjs` enthält beide Chrome-Schalter, die vier Funktionen und `await ablaufGast();`.
- [ ] **Step 4:** `uv run pytest tests/test_migration_003.py tests/test_testdaten.py tests/test_geruest.py -v` → FAIL.
- [ ] **Step 5:** implementieren. Importe in den beiden Tests von #15 auf `from testdaten import lege_antwort_an[, lege_eintrag_an]` umstellen; neue Tests importieren das Modul (`import testdaten`).
- [ ] **Step 6:** `uv run pytest -v` → PASS (auch Routen-Inventar und alle Tests von #15), Lint sauber. `node --check tests/e2e-pilot.mjs`.
- [ ] **Step 7:** Commit `feat: Migration 003, Testdaten und Geruest fuer #17 bis #19 (#16)`.

### Task 2: Grössengrenze für Anfragen

Spec: «Grösse von Anfragen».

**Files:**
- Create: `app/groesse.py`, `tests/test_groesse.py`
- Modify: `app/main.py`

**Interfaces:**
- Produces (`app/groesse.py`): `GRENZE = 1024 * 1024`, `GRENZE_UPLOAD = 16 * 1024 * 1024`, `UPLOAD_PFADE` (die zwei Muster aus der Spec), `grenze_fuer(pfad: str) -> int` (`fullmatch`), `class ZuGross(starlette.exceptions.HTTPException)` mit Status 413, `class GroessenGrenze` (reine ASGI-Middleware, `__init__(self, app)`).
- Produces (`app/main.py`): `FEHLERTEXTE[413] = ("Zu gross", "Es wurde nichts gespeichert, weil die Eingabe zu gross ist. Eine Aufnahme darf höchstens 10 Minuten lang sein.")`; `app.add_middleware(GroessenGrenze)` **vor** `CookieMiddleware` (innerste Schicht).
- Ablauf in `__call__`: Nicht-HTTP unverändert durchreichen. Grenze aus `scope["path"]`. `Content-Length` aus `scope["headers"]`. Die Middleware übergibt der App ein eigenes `receive`: Ist `Content-Length` vorhanden und nicht nur Ziffern oder grösser als die Grenze, wirft der erste Aufruf `ZuGross()`. Sonst zählt es `len(body)` jeder `http.request`-Nachricht und wirft, sobald die Summe die Grenze übersteigt. Andere Nachrichten unverändert.

- [ ] **Step 1: Failing tests** `tests/test_groesse.py`:
  - `test_grenze_fuer`: `/lehrperson/tagebuch/neu/aufnahme` und `/lehrperson/runden/3/fragen/12/aufnahme` → `GRENZE_UPLOAD`; `/anmelden`, `/lehrperson/runden/3`, `/lehrperson/tagebuch/neu/aufnahme/x`, `/x/lehrperson/tagebuch/neu/aufnahme` → `GRENZE`.
  - `test_anmelden_zu_gross(client)`: `POST /anmelden` mit `csrf` von `csrf_von(client)`, `benutzername = "a" * GRENZE`, `passwort = "x"` → 413, «Zu gross» im Text, «stimmt nicht» nicht im Text.
  - `test_ohne_content_length_gezaehlt(client)`: `POST /anmelden` mit `content=` Generator aus 70 Stücken à 1024 Bytes (`b"benutzername=" + …`) und `content-type: application/x-www-form-urlencoded` → 413.
  - `test_knapp_unter_grenze(client)`: gültiges `csrf`, Benutzername so lang, dass der Body 60 KiB hat → 400 «Benutzername oder Passwort stimmt nicht.» (normales Verhalten).
  - `test_laenge_keine_zahl()`: `GroessenGrenze` direkt mit einer App, die `await receive()` aufruft, `scope` mit `(b"content-length", b"abc")` → `pytest.raises(ZuGross)` (über `asyncio.run`).
  - `test_upload_pfad_grosse_grenze()`: kleine FastAPI-App mit Handler für `StarletteHTTPException` (Status durchreichen), Route `POST /lehrperson/tagebuch/neu/aufnahme` und `POST /andere`, die `await request.body()` lesen, mit `GroessenGrenze`: 1 MiB auf den Upload-Pfad → 200, auf `/andere` → 413; `GRENZE_UPLOAD + 1` auf den Upload-Pfad → 413.
  - `test_413_mit_sicherheits_headern(client)`: Antwort aus `test_anmelden_zu_gross` hat `content-security-policy` und `cache-control: no-store`.
  - `test_get_unberuehrt(client)`: `GET /` → 200.
- [ ] **Step 2:** `uv run pytest tests/test_groesse.py -v` → FAIL.
- [ ] **Step 3:** implementieren.
- [ ] **Step 4:** `uv run pytest -v` → PASS, Lint.
- [ ] **Step 5:** Commit `feat: Groessengrenze fuer Anfragen (#16)`.

### Task 3: Zeitpunkte, Filter, Sichtbarkeit am Stichtag, Ansicht

Spec: «Zeitpunkte anzeigen», «Freischaltung und Stichtag», «`app/sichtbar.py`», «Gemeinsame Darstellung» (nur `app/ansicht.py`).

**Files:**
- Create: `app/sichtbar.py`, `app/ansicht.py`, `tests/test_sichtbar.py`, `tests/test_ansicht.py`
- Modify: `app/zeit.py`, `app/vorlagen.py`, `tests/test_zeit.py`, `tests/test_formatierung.py`

**Interfaces:**
- Produces (`app/zeit.py`): `lokal(zeitstempel: str) -> datetime`, `zeitpunkt_kurz(zeitstempel: str) -> str` (`f"{datum_kurz(d.date())}, {d:%H:%M}"`), neu `zeitstempel(jetzt: datetime | None = None) -> str`: UTC-Text `"%Y-%m-%dT%H:%M:%SZ"`, Standard die aktuelle Zeit (einzige Stelle mit der Uhr; genutzt von `app/eintraege.py`).
- Produces (`app/vorlagen.py`): Filter `zeitpunkt` (`None`/leer → `""`) und `dauer` (Regel der Spec, Minuten aufgerundet).
- Produces (`app/sichtbar.py`): die fünf Funktionen der Spec, auf `inhalte.runden`, `runde`, `impulse`, `impuls` und `zeit.ist_erreicht`.
- Produces (`app/ansicht.py`): `Modus`, `Ansicht` (Felder und Eigenschaften wie Spec; `__post_init__` → `ValueError`), `fuer_lehrperson(konto, heute)` (`basis="/lehrperson"`), `fuer_gast(heute, band, ausgang)` (`basis="/gast"`), `fuer_vorschau(stichtag, band, ausgang)` (`basis=f"/verwaltung/vorschau/{stichtag.isoformat()}"`), `hole_ansicht_lehrperson`.

- [ ] **Step 1: Failing tests** `tests/test_zeit.py`, `tests/test_formatierung.py`:
  - `test_lokal`: `lokal("2026-11-23T17:40:00Z") == datetime(2026, 11, 23, 18, 40, tzinfo=ZEITZONE)`.
  - `test_zeitpunkt_kurz`: `"2026-11-23T17:40:00Z"` → `"Mo 23.11.2026, 18:40"`; `"2026-10-24T22:30:00Z"` → `"So 25.10.2026, 00:30"`.
  - `test_zeitstempel`: `zeitstempel(datetime(2026, 11, 23, 18, 40, 5, tzinfo=ZEITZONE)) == "2026-11-23T17:40:05Z"`; ohne Argument passt das Ergebnis auf `^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$`.
  - `test_filter_dauer_zeitpunkt`: `dauer`: `None` → `""`, `0` → `"0 Sek."`, `45` → `"45 Sek."`, `59` → `"59 Sek."`, `60` → `"1 Min."`, `61` → `"2 Min."`, `600` → `"10 Min."`; `zeitpunkt(None) == ""`, `zeitpunkt("2026-11-23T17:40:00Z") == "Mo 23.11.2026, 18:40"`.
- [ ] **Step 2: Failing tests** `tests/test_sichtbar.py` (Daten über `testdaten`):
  - `test_sichtbare_runden_grenze(db)`: Runden am 23.11., 30.11., 23.11. → Stichtag 22.11.: `[]`; 23.11.: die beiden vom 23.11. in `id`-Reihenfolge; 30.11.: alle drei; Zeilen haben `anzahl_fragen`.
  - `test_naechste_freischaltung(db)`: Stichtag 23.11. → `date(2026, 11, 30)`; 30.11. → `None`; ohne Runden → `None`.
  - `test_sichtbare_runde(db)`: künftige → `None`, unbekannte → `None`, sichtbare → Zeile mit `titel`.
  - `test_aktueller_impuls(db)`: Impulse a (23.11.), b (30.11.), c (30.11.) → 22.11.: `None`; 29.11.: a; 30.11.: c; 31.12.: c.
  - `test_sichtbarer_impuls(db)`: Stichtag 30.11.: a → Zeile (nicht nur der aktuelle); künftiger Impuls am 07.12. → `None`.
- [ ] **Step 3: Failing tests** `tests/test_ansicht.py`:
  - `test_konto_nur_bei_lehrperson`: `Ansicht("gast", d, "/gast", 1)`, `Ansicht("vorschau", d, "/x", 2)`, `Ansicht("lehrperson", d, "/lehrperson", None)` → je `ValueError`.
  - `test_fuer_lehrperson`: `speichert` und `zeigt_eintraege` wahr, `url("/runden/3") == "/lehrperson/runden/3"`, `konto_id == konto.id`, `stichtag == heute`, `ausgang is None`.
  - `test_fuer_gast`: `basis == "/gast"`, `konto_id is None`, `speichert` falsch, `band` und `ausgang == ("Anmelden", "/")` übernommen.
  - `test_fuer_vorschau`: `fuer_vorschau(date(2026, 12, 7), "B", ("Vorschau beenden", "/verwaltung/vorschau")).url("/info") == "/verwaltung/vorschau/2026-12-07/info"`.
- [ ] **Step 4:** FAIL. **Step 5:** implementieren. **Step 6:** `uv run pytest -v` PASS (auch `test_nur_zeit_kennt_die_uhr`), Lint.
- [ ] **Step 7:** Commit `feat: Zeitpunkte, Sichtbarkeit am Stichtag und Ansicht (#16)`.

### Task 4: Antworten einer Runde und Aufnahme-Dateien

Spec: «Speichern einer Runde», «Löschen», «`app/eintraege.py`» (Antworten, `Stand`, Festlegungen), «`app/aufnahmen.py`».

**Files:**
- Create: `app/eintraege.py` (erster Teil), `app/aufnahmen.py`, `tests/test_eintraege.py`, `tests/test_aufnahmen_grundstock.py`

**Interfaces:**
- Consumes: Task 3 (`zeit.zeitstempel`), #15 (`transaktion`, `langer_text`, `InhaltFehler`, `SKALA_MIN`, `SKALA_MAX`).
- Produces (`app/aufnahmen.py`): `DATEINAME`, `aufnahme_pfad(verzeichnis, dateiname) -> Path | None`, `loesche_dateien(verzeichnis, dateinamen) -> None` (Fehler → `logging.getLogger(__name__).warning("Aufnahme-Datei liess sich nicht loeschen")`, ohne Namen), `aufnahmen_von_eintraegen(db, aufnahme_ids) -> list[sqlite3.Row]` (`id`, `dateiname`).
- Produces (`app/eintraege.py`): `antworten_der_runde`, `lies_runden_eingaben`, `speichere_antworten`, `loesche_antworten_der_runde`, `Stand`, `rundenstand` mit den Signaturen der Spec.
  - `lies_runden_eingaben`: nur Felder `antwort_{id}` für Fragen in `fragen`, die im Formular **vorhanden** sind; fehlende bleiben weg. Freitext: `langer_text(wert, feld, None)` → `(text, None)`. Skala: `""` → `(None, None)`; ein ASCII-Ziffernwort im Bereich `SKALA_MIN`…`SKALA_MAX` → `(None, wert)`; sonst `InhaltFehler(feld, "Bitte einen Wert von 1 bis 5 wählen.")`. Feldname im Fehler ist `antwort_{id}`.
  - `speichere_antworten`: in `transaktion`; `jetzt = jetzt or zeit.zeitstempel()`; pro Frage die Regeln aus der Spec (unverändert → nichts; neu → `INSERT` mit `erstellt = geaendert = jetzt`; geändert → `UPDATE … geaendert = jetzt`; leer ohne Aufnahme → `DELETE`; leer mit Aufnahme → Text/Skalawert `NULL`, Zeile bleibt). Rückgabe: Anzahl geänderter Zeilen.
  - `loesche_antworten_der_runde`: `db.in_transaction` → `RuntimeError`; sonst in `transaktion` Dateinamen lesen, Antworten des Kontos zu Fragen der Runde und deren Zeilen in `aufnahmen` löschen; nach dem `COMMIT` `loesche_dateien`. Rückgabe: Anzahl gelöschter Antworten.

- [ ] **Step 1: Failing tests** `tests/test_aufnahmen_grundstock.py`:
  - `test_aufnahme_pfad_muster(tmp_path)`: `"../x.webm"`, `"a.webm"`, `"0"*32 + ".mp3"`, `"A"*32 + ".webm"`, `"0"*32 + ".webm/.."` → `None`; `"0"*32 + ".m4a"` → `tmp_path / name`.
  - `test_loesche_dateien(tmp_path)`: Dateien `a.webm` und eine mit gültigem Namen; `loesche_dateien(tmp_path, ["a.webm", gueltig, "f"*32 + ".ogg"])` → nur die gültige ist weg, keine Ausnahme.
  - `test_loesche_dateien_fehler_geloggt(tmp_path, monkeypatch, caplog)`: `Path.unlink` wirft `PermissionError` → keine Ausnahme, ein Log-Eintrag, der Dateiname steht nicht im Log.
- [ ] **Step 2: Failing tests** `tests/test_eintraege.py` (Runde `rid` mit `f1` Freitext, `f2` Skala über `testdaten`):
  - `test_eingaben_normalisiert`: `{"antwort_f1": "  a\r\nb ", "antwort_f2": "4"}` → `{f1: ("a\nb", None), f2: (None, 4)}`; beide `""` → `{f1: (None, None), f2: (None, None)}`.
  - `test_fehlendes_feld_bleibt_unberuehrt` (Review Focus 1): Formular nur mit `antwort_f1` → `f2` fehlt im Ergebnis; gespeicherte Antwort auf `f2` bleibt nach `speichere_antworten` erhalten.
  - `test_skala_ungueltig` (parametrisiert `"0"`, `"6"`, `"x"`, `"3.0"`, `" 3"`, `"+3"`, `"٣"`): `InhaltFehler`, `feld == f"antwort_{f2}"`, Meldung «Bitte einen Wert von 1 bis 5 wählen.»
  - `test_text_grenze`: 20 001 Zeichen → `InhaltFehler`, Meldung enthält «höchstens 20 000 Zeichen»; 20 000 geht.
  - `test_fremde_felder_ignoriert`: `antwort_999`, `csrf`, `anker` und `antwort_{frage einer anderen Runde}` fehlen im Ergebnis.
  - `test_speichern_neu_unveraendert_geaendert(db, lehrperson)`: mit `jetzt="2026-11-23T10:00:00Z"` → 2, beide Zeilen `erstellt == geaendert == jetzt`; dieselben Eingaben mit `…11:00…` → 0, nichts verändert; nur `f1` geändert mit `…12:00…` → 1, `f1.geaendert` 12:00, `f1.erstellt` 10:00, `f2` unverändert.
  - `test_leeren_loescht(db, lehrperson)`: `f1` und `f2` leer → keine Zeile mehr.
  - `test_leeren_mit_aufnahme_behaelt_zeile(db, lehrperson, einstellungen)`: Antwort mit Text und Aufnahme (`testdaten`) → leer speichern → Zeile da, `text IS NULL`, `aufnahme_id` unverändert.
  - `test_transaktion_des_aufrufers(db, lehrperson)`: in `transaktion(db)` speichern, dann `RuntimeError` → keine Zeile.
  - `test_nur_eigenes_konto(db, lehrperson, zweite_lehrperson)`: Antwort der zweiten auf `f1`; erste speichert `f1` → Antwort der zweiten unverändert; `antworten_der_runde(db, erste, rid)` enthält sie nicht.
  - `test_rundenstand(db, lehrperson)`: Runde A mit 2 Fragen, Runde B ohne Fragen, eine Antwort auf A → `{A: Stand(1, 2), B: Stand(0, 0)}`.
  - `test_loesche_antworten_der_runde(db, lehrperson, zweite_lehrperson, einstellungen)`: Antwort mit Aufnahme in `rid`, Antwort in einer anderen Runde, Antwort der zweiten in `rid` → Rückgabe 1; Datei und Zeile der Aufnahme weg; die beiden anderen Antworten da.
  - `test_loesche_bei_fehlender_datei(…)`: Datei vorher entfernt → keine Ausnahme, Zeilen weg.
  - `test_loeschen_in_laufender_transaktion(db, lehrperson)`: in `transaktion(db)` → `RuntimeError`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** PASS, Lint.
- [ ] **Step 6:** Commit `feat: Antworten einer Runde speichern, Aufnahme-Dateien (#16)`.

### Task 5: Tagebuch, Zeilen und Gruppierung (Fachlogik)

Spec: «Tagebuch: eine Leitfrage pro Eintrag» (Arten und Felder, Prüfung des Texts), «`app/eintraege.py`» (`Zeile`, `Eintrag`, Festlegungen).

**Files:**
- Modify: `app/eintraege.py`
- Create: `tests/test_tagebuch.py`, `tests/test_zeilen.py`

**Interfaces:**
- Consumes: Task 4 (`aufnahmen.loesche_dateien`, Muster der Löschfunktion), Task 3 (`zeit.zeitstempel`).
- Produces: `lies_tagebuchtext`, `lege_tagebucheintrag_an`, `hole_tagebucheintrag`, `aendere_tagebucheintrag`, `loesche_tagebucheintrag`, `anzahl_tagebucheintraege`, `Zeile`, `Eintrag`, `zeilen_von`, `alle_zeilen`, `gruppiere` mit den Signaturen der Spec.
  - `lege_tagebucheintrag_an`: `art` nicht in `("frei", "leitfragen", "impuls", "aufnahme")` oder Bezug passt nicht zur Tabelle «Arten und Felder» → `ValueError` (Programmierfehler); Text über `lies_tagebuchtext(text, pflicht=art != "aufnahme")`; kopiert `impuls["text"]` bzw. `leitfrage["text"]`; `erstellt = geaendert = jetzt or zeit.zeitstempel()`; in `transaktion`.
  - `aendere_tagebucheintrag`: fremd oder unbekannt → `False`, nichts geändert; Text normalisiert (`pflicht` nach Art); `geaendert` nur bei geändertem Text; sonst `True`.
  - `loesche_tagebucheintrag`: wie `loesche_antworten_der_runde` (eigene Transaktion, `RuntimeError` in laufender, Datei nach `COMMIT`); fremd oder unbekannt → `False`.
  - `Zeile`: Antwort → `quelle="antwort"`, `art="runde"`, `angeleitet=True`, `frage` = aktueller Fragetext; Tagebuch → `quelle="tagebuch"`, `art="impuls"` bei `tagebuch_art == "impuls"`, sonst `"tagebuch"`, `angeleitet=False`, `frage` = `leitfrage_text` oder `impuls_text`. `zeilen_von`/`alle_zeilen` sortiert nach `erstellt, quelle, id`.
  - `gruppiere`: Antworten nach `(konto_id, runde_id)` zu einem `Eintrag` (`erstellt` = früheste, `geaendert` = späteste, `zeilen` nach `frage_reihenfolge, frage_id`); Tagebuch je ein `Eintrag`. Sortierung absteigend nach `(erstellt, 1 bei Tagebuch sonst 0, eintrag_id oder runde_id)`.

- [ ] **Step 1: Failing tests** `tests/test_tagebuch.py`:
  - `test_lies_tagebuchtext`: `"  a\r\nb "` → `"a\nb"`; `" "` → `InhaltFehler` mit `feld == "text"` und «Der Eintrag ist noch leer.»; `" "` mit `pflicht=False` → `None`; 20 001 Zeichen → Meldung mit «höchstens 20 000 Zeichen».
  - `test_frei(db, lehrperson)`: Zeile mit `art == "frei"`, Text, `erstellt == geaendert`.
  - `test_impuls_kopiert_text(db, lehrperson)`: Impuls «Impuls A» → Eintrag; `UPDATE impulse SET text = 'Neu'` → `hole_tagebucheintrag(…)["impuls_text"] == "Impuls A"`.
  - `test_leitfrage_kopiert_text(db, lehrperson)`.
  - `test_aufnahme_text_freiwillig(db, lehrperson, einstellungen)`: `art="aufnahme"`, `aufnahme_id`, Text `""` → `text IS NULL`.
  - `test_falsche_kombination` (parametrisiert: `"impuls"` ohne Impuls, `"frei"` mit Leitfrage, `"aufnahme"` ohne `aufnahme_id`, `"x"`) → `ValueError`, keine Zeile.
  - `test_leer_nichts_angelegt(db, lehrperson)`: `"frei"`, `" "` → `InhaltFehler`, `anzahl_tagebucheintraege == 0`.
  - `test_transaktion_des_aufrufers(db, lehrperson)`: in `transaktion(db)` anlegen, dann `RuntimeError` → 0 Einträge.
  - `test_fremder_eintrag(db, lehrperson, zweite_lehrperson)`: `hole_…` → `None`; `aendere_…` → `False`; `loesche_…` → `False`; Eintrag unverändert.
  - `test_aendern(db, lehrperson)`: `erstellt`/`geaendert` per `UPDATE` auf `2026-11-01T00:00:00Z`; gleicher Text → `geaendert` unverändert; neuer Text → `geaendert` neuer, `erstellt` gleich; `""` bei `frei` → `InhaltFehler`; `""` bei `aufnahme` → `text IS NULL`.
  - `test_loeschen_mit_aufnahme(db, lehrperson, einstellungen)`: Datei und Zeilen weg; in laufender Transaktion → `RuntimeError`.
  - `test_anzahl(db, lehrperson, zweite_lehrperson)`: zählt nur eigene, alle Arten.
- [ ] **Step 2: Failing tests** `tests/test_zeilen.py`:
  - `test_alle_zeilen_werte(db, lehrperson, zweite_lehrperson, einstellungen)`: Freitext-Antwort, Skala-Antwort (`skalawert=4`), Antwort nur mit Aufnahme, Tagebuch `frei`, `leitfragen`, `impuls`, `aufnahme` (Dauer 5), Antwort in einer künftigen Runde → je eine `Zeile` mit den erwarteten `quelle`, `art`, `angeleitet`, `tagebuch_art`, `frage`, `skalawert`, `aufnahme_dateiname`, `aufnahme_mime_typ`, `aufnahme_dauer_sekunden`, `anzeigename`; die künftige Runde ist enthalten (ungefiltert).
  - `test_zeilen_von_nur_eigenes`.
  - `test_gruppiere`: Antworten mit `erstellt` 08:00 und 09:00 (`geaendert` 12:00), Tagebuch 10:00 → `[Tagebuch, Runde]`; Runde: `erstellt` 08:00, `geaendert` 12:00, `zeilen` in Fragenreihenfolge. Tagebuch und Runde mit gleichem `erstellt` → Tagebuch zuerst; zwei Tagebucheinträge gleichzeitig → höhere `id` zuerst. Zwei Lehrpersonen in derselben Runde → zwei Karten.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** PASS, Lint.
- [ ] **Step 6:** Commit `feat: Tagebuch, Zeilen und Gruppierung der Eintraege (#16)`.

### Task 6: Rahmen, Navigation, Startseite und Infoblock

Spec: «Startseite», «Infoblock», «Navigation», «Gemeinsame Darstellung», «Templates».

**Files:**
- Create: `app/seiten_lehrperson.py`, `app/templates/lehrperson/_rahmen.html`, `…/_navigation.html`, `…/info.html`, `app/templates/_aufnahme.html`, `tests/test_lehrperson.py`
- Modify: `app/templates/basis.html` (Block `main_klasse` an `<main class="inhalt …">`), `app/templates/lehrperson/start.html`, `app/routen/lehrperson.py`, `app/static/css/style.css`, `tests/test_ansicht.py`

**Interfaces:**
- Consumes: Task 3 (`Ansicht`, `hole_ansicht_lehrperson`, `sichtbar.*`, Filter), Tasks 4–5 (`rundenstand`, `anzahl_tagebucheintraege`).
- Produces (`app/seiten_lehrperson.py`): `kontext_start(db, ansicht) -> dict`, `kontext_info(db, ansicht) -> dict`, `VORLAGEN` (hier `"start"`, `"info"`; spätere Tasks ergänzen). Jeder Kontext enthält `ansicht` und `bereich`. Ohne `ansicht.konto_id` kein Anzeigename, kein Antwortstand, keine Zahl der Einträge.
- Produces (`app/routen/lehrperson.py`): `DB`, `ANSICHT = Annotated[Ansicht, Depends(hole_ansicht_lehrperson)]`, `ERLEDIGT` (Tabelle der Spec), `_meldung(request) -> str | None` (nur aus `ERLEDIGT`), `_weiter(pfad, erledigt=None, anker=None) -> RedirectResponse` (303). Routen `GET ""` und `GET "/info"`.
- Produces (Templates): `_rahmen.html` mit Band (`ansicht.band | formatiert`, `role="note"`), `kopf_rechts` (`super()` plus Ausgang), Meldung oben (`role="status"`), Leiste aus `_navigation.html` (vier bzw. drei Einträge, `aria-current="page"` nach `bereich`, Links über `ansicht.url`), `main_klasse` = `bereich--{{ bereich }}`. `_aufnahme.html` mit `aufnahme`, `url` (`<audio controls preload="none" src="{{ url }}">` und `aufnahme.aufnahme_dauer_sekunden | dauer` bzw. `aufnahme.dauer_sekunden | dauer`).
- Startseite ohne Runden: Karte «Runden» mit «Noch keine Runde.» (Spec schweigt; Festlegung hier).

- [ ] **Step 1: Failing tests** `tests/test_lehrperson.py` (Daten über `testdaten`, erster Tag per `INSERT INTO einstellungen`):
  - `test_start_ohne_inhalte(client, lehrperson)`: 200, «Hallo, Anna Beispiel», «Noch keine Runde.», kein «Woche».
  - `test_start_mit_inhalten(client, lehrperson, db, heute_ist)`: erster Tag 23.11., «Runde Eins» am 23.11., «Runde Geheim» am 30.11., Impuls «Impuls Eins» am 23.11.; `heute_ist(date(2026, 11, 24))` → «Woche 1», «Runde Eins», «Nächste Runde ab Mo 30.11.», «Runde Geheim» nicht im Text, «Impuls Eins», «Dazu schreiben», «Jetzt beantworten», Vorschlag von `hinweis_wer_sieht_was`, `class="inhalt bereich--start"`, `aria-current="page"` am Link `/lehrperson`, Link `/lehrperson/eintraege` in der Leiste.
  - `test_start_vor_erster_runde(…)`: `heute_ist(date(2026, 11, 22))` → «Die erste Runde erscheint am Mo 23.11.», keine Karte «Impuls dieser Woche».
  - `test_start_antwortstand(…)`: 1 von 2 → «Angefangen, 1 von 2»; 2 von 2 → «Beantwortet».
  - `test_start_zahl_eintraege(…)`: ein Eintrag → «1 Eintrag»; zwei → «2 Einträge».
  - `test_info(client, lehrperson, db)`: Abschnitte A (`reihenfolge` 2) und B (1) → B vor A; erstes `<details` hat `open`; letzter Abschnitt «Datenschutz» mit dem Vorschlag von `hinweis_datenspeicherung`; `**x**` im Abschnitt → `<strong>x</strong>`; `class="inhalt bereich--info"`.
  - `test_kein_inline(client, lehrperson)`: Start und Info enthalten weder `style=` noch `<script>` ohne `src` noch ` on` + Buchstaben + `=` in einem Tag.
  - `test_auftraggeberin_403(client, auftraggeberin)`: `als_leitung`, `GET /lehrperson/info` → 403.
- [ ] **Step 2: Failing tests** `tests/test_ansicht.py`: Fixture `seiten_client(einstellungen)`: `erstelle_app`, dazu Test-Routen `GET /test-gast/{seite}` und `GET /test-vorschau/{am}/{seite}`, die `VORLAGEN[seite]` mit `kontext_…(db, fuer_gast(heute, "Band Gast", ("Anmelden", "/")))` bzw. `fuer_vorschau(lies_datum(am), "Band Vorschau", ("Vorschau beenden", "/verwaltung/vorschau"))` rendern; `TestClient`.
  - `test_gast_start_ohne_persoenliches(seiten_client, db, lehrperson)`: Antworten und Einträge der Lehrperson bestehen → «Willkommen», «Band Gast», Link `href="/"` mit «Anmelden», kein «Anna Beispiel», kein «Eintrag», kein Link `/lehrperson/eintraege` oder `/gast/eintraege`, Links beginnen mit `/gast`.
  - `test_vorschau_rechnet_mit_stichtag(seiten_client, db, heute_ist)`: erster Tag 23.11., Runden 23.11., 07.12., 14.12.; `heute_ist(date(2026, 11, 24))`; `/test-vorschau/2026-12-07/start` → «Woche 3», Titel der Runde vom 07.12., «Nächste Runde ab Mo 14.12.», Links beginnen mit `/verwaltung/vorschau/2026-12-07`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren (Leiste mit den SVG-Symbolen aus `prototyp/index.html`; `.tabs` mit `grid-auto-flow: column; grid-auto-columns: 1fr`). **Step 5:** PASS, Lint. `make dev`, Startseite in 390 px ansehen.
- [ ] **Step 6:** Commit `feat: Rahmen, Startseite und Infoblock der Lehrperson (#16)`.

### Task 7: Runde beantworten, speichern, löschen

Spec: «Runde», «Speichern einer Runde», «Löschen», «Gemeinsame Darstellung» (`kontext_runde`).

**Files:**
- Create: `app/templates/lehrperson/runde.html`, `app/templates/lehrperson/loeschen.html`, `tests/test_runde.py`
- Modify: `app/seiten_lehrperson.py`, `app/routen/lehrperson.py`, `app/static/css/style.css`, `tests/test_ansicht.py`

**Interfaces:**
- Consumes: Task 6 (Router-Helfer, `_rahmen.html`), Task 4 (`lies_runden_eingaben`, `speichere_antworten`, `antworten_der_runde`, `loesche_antworten_der_runde`), Task 3 (`sichtbare_runde`).
- Produces: `kontext_runde(db, ansicht, runde_id, eingaben=None, fehler=None, meldung=None)` (Signatur der Spec), `VORLAGEN["runde"]`. `loeschen.html` mit Kontext `frage_text`, `aktion`, `zurueck` (auch für Task 8).
- Routen: `GET`/`POST "/runden/{runde_id}"`, `GET`/`POST "/runden/{runde_id}/loeschen"`. POST: `sichtbare_runde` → sonst 404; `formular = await request.form()`; `InhaltFehler` → `kontext_runde(…, eingaben=dict(formular), fehler={e.feld: e.meldung})`, 400. Erfolg: `anker` gegen `frage-\d{1,10}` bzw. `aufnahme-\d{1,10}` prüfen; Weiterleitung nach Spec. Löschen → `/lehrperson/eintraege?erledigt=geloescht`.

- [ ] **Step 1: Failing tests** `tests/test_runde.py` (Runde `rid` am 23.11. mit `f1` Freitext, `f2` Skala; `heute_ist(date(2026, 11, 24))`):
  - `test_nicht_freigeschaltet_404` (**Akzeptanzkriterium**): Runde am 30.11., `heute_ist(29.11.)` → `GET`, `POST` (gültiges `csrf`, `antwort_…`), `GET`/`POST …/loeschen` → 404 mit «Nicht gefunden»; `testdaten.abzug` unverändert. `heute_ist(30.11.)` → `GET` 200.
  - `test_ungueltige_ids`: `999`, `abc`, `0`, `-1`, `99999999999999999999` → `GET` 404; `POST /lehrperson/runden/999` → 404.
  - `test_anzeige`: Fallbeispiel `**x**` → `<strong>x</strong>`; Fragetext `**y**` bleibt `**y**`; `textarea name="antwort_{f1}" id="frage-{f1}"` mit `maxlength="20000"`; fünf Radios 1–5 und «Keine Angabe» mit `checked`; Vorschlag von `hinweis_tagebuch`; zwei kleine und ein grosser «Speichern»-Knopf (`name="anker" value="frage-{f1}"`).
  - `test_speichern_und_anzeigen`: POST `antwort_f1="Text A"`, `antwort_f2="4"` → 303 auf `/lehrperson/runden/{rid}?erledigt=gespeichert`; GET dieser Adresse: «Gespeichert.», «Text A» im Feld, Radio 4 `checked`, «Zuletzt gespeichert:».
  - `test_unterbrochene_eingabe` (**Akzeptanzkriterium**): nur `f1` speichern, `client.cookies.clear()`, neu `anmelden`, GET → «Text A» im Feld.
  - `test_anker`: `anker=frage-{f1}` → `location` endet auf `?erledigt=gespeichert#frage-{f1}`; `anker` `"frage-1x"`, `"javascript:x"`, `"frage-" + "1"*11` → kein `#`.
  - `test_anker_aufnahme`: `anker=aufnahme-{f1}` → 303 auf `/lehrperson/runden/{rid}/fragen/{f1}/aufnahme`, Text gespeichert; `aufnahme-{f2}` (Skala) und `aufnahme-{Frage einer anderen Runde}` → 303 auf `/lehrperson/runden/{rid}?erledigt=gespeichert`.
  - `test_meldungen`: `?erledigt=aufnahme_geloescht` → «Die Aufnahme wurde gelöscht.»; `?erledigt=<script>` → weder `<script>` noch `&lt;script`.
  - `test_fehler_400_behaelt_eingaben` (Review Focus 5): `antwort_f1="Neu"`, `antwort_f2="7"` → 400, «Bitte prüfe die markierten Felder.», «Bitte einen Wert von 1 bis 5 wählen.», `aria-describedby="fehler-antwort_{f2}"`, «Neu» im Feld; zweite Runde: `antwort_f1="x"*20_001`, `antwort_f2="3"` → 400, Radio 3 `checked`; `abzug` unverändert.
  - `test_post_nach_datumsaenderung_404` (Review Focus 1): GET 200, dann `UPDATE runden SET freischaltdatum = '2026-12-31'`, POST → 404, keine Antwort.
  - `test_feld_anderer_runde_ignoriert`.
  - `test_runde_ohne_fragen`: «Zu dieser Runde gibt es noch keine Fragen.», kein `name="anker"`.
  - `test_runde_loeschen(…, zweite_lehrperson)`: GET Bestätigung mit «Alle deine Antworten zu» und dem Titel, «Endgültig löschen», «Abbrechen»; POST → 303 `/lehrperson/eintraege?erledigt=geloescht`; eigene Antworten weg, die der zweiten da.
  - `test_fremde_antworten_unsichtbar(…, zweite_lehrperson)`: zweite hat «Geheimantwort» gespeichert → Seite der ersten enthält es nicht.
  - `test_ausgabe_escapt` (Review Focus 3): gespeicherte Antwort `"<script>x</script> **f**"` → `&lt;script&gt;` und `**f**` im Feld, kein `<strong>f`.
- [ ] **Step 2: Failing tests** `tests/test_ansicht.py`: `test_gast_runde(seiten_client, db, lehrperson)`: Runde mit gespeicherter Antwort der Lehrperson → Seite `/test-gast/runde/{rid}` enthält `name="csrf"`, Formular-`action="/gast/runden/{rid}"`, kein `data-entwurf`, kein «löschen», nicht die Antwort. `test_kontext_runde_eingaben_fehler_meldung(seiten_client, …)`: Test-Route rendert `kontext_runde(…, eingaben={f"antwort_{f1}": "Neu"}, fehler={f"antwort_{f1}": "Zu lang"}, meldung="Nicht gespeichert.")` → «Neu» im Feld, «Zu lang» am Feld, «Nicht gespeichert.» mit `role="status"`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** PASS (Routen-Inventar deckt die neuen Routen ab), Lint.
- [ ] **Step 6:** Commit `feat: Runden beantworten, speichern und loeschen (#16)`.

### Task 8: Tagebuch und Meine Einträge

Spec: «Tagebuch», «Meine Einträge», «Löschen», «Prüfung und Nachweis» (Fremde Objekte).

**Files:**
- Create: `app/templates/lehrperson/tagebuch_wahl.html`, `…/tagebuch_neu.html`, `…/tagebuch_eintrag.html`, `…/eintraege.html`, `tests/test_tagebuch_routen.py`, `tests/test_fremde_eintraege.py`
- Modify: `app/seiten_lehrperson.py`, `app/routen/lehrperson.py`, `app/static/css/style.css`, `tests/test_ansicht.py`

**Interfaces:**
- Consumes: Task 5 (Tagebuch-Funktionen, `zeilen_von`, `gruppiere`), Task 7 (`loeschen.html`, Router-Helfer), Task 3 (`aktueller_impuls`, `sichtbarer_impuls`, `sichtbare_runden`).
- Produces: `kontext_tagebuch_wahl(db, ansicht)`, `kontext_tagebuch_neu(db, ansicht, art, bezug_id=None, text=None, fehler=None, meldung=None)`, `VORLAGEN["tagebuch_wahl"]`, `VORLAGEN["tagebuch_neu"]`.
- Routen nach der Adressentabelle der Spec. Anlegen → 303 `/lehrperson/tagebuch/{id}?erledigt=gespeichert`; Ändern → 303 auf dieselbe Seite mit `?erledigt=gespeichert`, leer bei `frei`/`leitfragen`/`impuls` → 400 «Zum Löschen bitte ‹Eintrag löschen› wählen.»; Löschen → 303 `/lehrperson/eintraege?erledigt=geloescht`. «Meine Einträge»: `gruppiere(zeilen_von(…))` ohne Runden-Karten, deren Runde am Stichtag nicht sichtbar ist.
- Platzhalter `{# #17: Frei sprechen #}` (Wahl) und `{# #17: Aufnahme ersetzen oder löschen #}` (Eintrag) genau so.

- [ ] **Step 1: Failing tests** `tests/test_tagebuch_routen.py`:
  - `test_wahl(…)`: Links `/lehrperson/tagebuch/neu/frei`, `…/neu/impuls/{aktuell}` mit dem Impulstext, je Leitfrage `…/neu/leitfrage/{id}`; ohne sichtbaren Impuls keine Impuls-Karte; ohne Leitfragen kein «Zu einer Leitfrage schreiben»; `class="inhalt bereich--tagebuch"`.
  - `test_neu_frei(…)`: Formular mit `textarea name="text"`, `maxlength="20000"`, Vorschlag von `hinweis_tagebuch`; POST → 303; Seite zeigt «Gespeichert.», «Freier Eintrag», den Text, «Erstellt», kein «geändert», Link «Zur Startseite».
  - `test_neu_zum_impuls(…)`: Impulstext über dem Feld; nach dem Anlegen `UPDATE impulse SET text='Neu'` → Eintragsseite zeigt weiterhin den alten Text. Ein älterer, nicht mehr aktueller Impuls ist ebenfalls erlaubt (303).
  - `test_neu_zur_leitfrage(…)`: nach dem Anlegen Link «Zu einer weiteren Leitfrage schreiben».
  - `test_neu_bezug_404(…)`: künftiger Impuls (`GET` und `POST`), unbekannte Leitfrage, `abc` → 404; nichts angelegt.
  - `test_neu_leer_400(…)`: «Der Eintrag ist noch leer.», 0 Einträge.
  - `test_neu_laden_legt_nicht_doppelt_an` (Review Focus 2): POST, dann zweimal GET auf `location` → 1 Eintrag.
  - `test_langer_text_mit_umlauten_passt` (Review Focus 4): `("Schöne Grüsse, äöü. " * 1000)` → 303, gespeicherter Text == Eingabe ohne Leerraum am Ende.
  - `test_aendern(…)`: neuer Text → 303, Seite zeigt «geändert»; gleicher Text → kein «geändert»; `""` → 400 «Zum Löschen bitte ‹Eintrag löschen› wählen.», Text unverändert.
  - `test_eintrag_mit_aufnahme(…, einstellungen)`: `testdaten`-Eintrag `art="aufnahme"` (Dauer 5) → «Gesprochener Eintrag», «Notiz zur Aufnahme (freiwillig)», `<audio` mit `src="/lehrperson/aufnahmen/{aid}"` und `preload="none"`, «5 Sek.»; POST `text=""` → 303, `text IS NULL`.
  - `test_loeschen_doppelt_404` (Review Focus 2): Bestätigung mit «Diesen Eintrag löschen? Das lässt sich nicht rückgängig machen.»; POST → 303; derselbe POST nochmals → 404; Aufnahme-Datei eines gelöschten Eintrags ist weg.
  - `test_eintrag_escapt_unformatiert` (Review Focus 3): `"<b>x</b> **f**\r\nZeile"` → `&lt;b&gt;`, `**f**`, Zeilenumbruch als `\n` gespeichert; in Eintragsseite und «Meine Einträge» kein `<b>x` und kein `<strong>`.
  - `test_meine_eintraege(…)`: Antworten (1 von 2) in einer Runde, freier Eintrag, Eintrag zum Impuls, gesprochener Eintrag (60 s) mit gesetzten `erstellt` → Karten neueste zuerst; Marken «Runde», «Tagebuch», «Impuls»; «1 von 2 Fragen beantwortet»; «Zum Impuls: …»; «Aufnahme, 1 Min.»; «geändert» nur bei der geänderten Karte; Satz «Nur du und die Projektleiterin sehen sie.».
  - `test_meine_eintraege_verschobene_runde(…)`: Runde nach dem Antworten auf ein späteres Datum → keine Runden-Karte; Antworten in der Datenbank unverändert.
  - `test_meine_eintraege_leer(…)`: «Noch keine Einträge.» und Link «Ersten Tagebucheintrag schreiben».
- [ ] **Step 2: Failing tests** `tests/test_fremde_eintraege.py` (**Akzeptanzkriterium aus #14**). Fixture `daten_der_ersten(db, lehrperson, einstellungen, heute_ist)`: sichtbare Runde mit Antwort «GeheimA», Einträge `frei` («GeheimT»), `impuls`, `leitfragen`, `aufnahme`.
  - `test_fremde_eintraege_404(client, zweite_lehrperson, daten_der_ersten, db)`: als zweite, für jede `eintrag_id` der ersten: `GET /lehrperson/tagebuch/{id}`, `POST` (gültiges `csrf`, `text="X"`), `GET`/`POST …/loeschen` → 404; `testdaten.abzug` und Aufnahmen-Ordner unverändert.
  - `test_alle_routen_mit_eintrag_id(…)`: aus `iter_route_contexts(erstelle_app(einstellungen).routes)` (wie in `test_routen_inventar.py`) jede Route unter `/lehrperson` mit `{eintrag_id}` im Pfad, eingesetzt die `id` eines Eintrags der ersten → GET bzw. POST (mit gültigem `csrf`) 404; die Liste ist nicht leer (erfasst auch spätere Routen).
  - `test_fremde_antworten_unsichtbar(…)`: als zweite `GET` Runde, `/lehrperson`, `/lehrperson/eintraege` → weder «GeheimA» noch «GeheimT»; `POST …/runden/{rid}/loeschen` → Antwort der ersten unverändert.
- [ ] **Step 3: Failing tests** `tests/test_ansicht.py`: `test_gast_tagebuch(seiten_client, …)`: Wahl und Formular zum Impuls im Gast-Modus → Links und `action` unter `/gast`, `name="csrf"` vorhanden, kein `data-entwurf`; `kontext_tagebuch_neu(…, text="Mein Text", fehler={"text": "Der Eintrag ist noch leer."}, meldung="Nicht gespeichert.")` zeigt alle drei.
- [ ] **Step 4:** FAIL. **Step 5:** implementieren. **Step 6:** `uv run pytest -v` PASS, Lint.
- [ ] **Step 7:** Commit `feat: Tagebuch und Meine Eintraege (#16)`.

### Task 9: E2E-Ablauf der Lehrperson, Doku

Spec: «Prüfung und Nachweis» (E2E, Schritte 1–5, 7–9).

**Files:**
- Modify: `tests/e2e-pilot.mjs` (Funktion `ablaufLehrperson`), `README.md`

**Interfaces:**
- Consumes: alle Seiten; Platzhalter aus dem E2E-Lauf von #15 (Runde 1 sichtbar, Runde 2 mit `id` 2 nicht).
- Produces: Helfer `legeZugangAn(anzeigename, benutzername) -> Promise<string>` (als Auftraggeberin über `/verwaltung/zugaenge`, liest das Passwort aus `dl.zugangsdaten` wie #14). Zugänge `lp.e2e.eins` («Erika Eins») und `lp.e2e.zwei` («Zora Zwei»).

- [ ] **Step 1:** `ablaufLehrperson()` nach der Spec, Schritte 1–5 und 7–8, in 390 px hell; jede besuchte Seite `keinUeberlauf` und `keineFehlerSeit` (bei Schritt 4 und 7 mit `["status of 404"]`, bei Schritt 8 ohne). Zusätzlich:
  - Start: `muss` «Woche 1», Titel von Runde 1, «Nächste Runde ab», der Titel von Runde 2 (vorher aus der Platzhalter-Datei gelesen) nicht in `text()`.
  - Runde 1: kleinen «Speichern»-Knopf unter der ersten Frage → `location.hash === "#frage-…"`, «Gespeichert.»; `oeffne` dieselbe Adresse neu → Text im Feld (**Akzeptanzkriterium unterbrochene Eingabe**).
  - `/lehrperson/runden/2` → `ueberschrift()` «Nicht gefunden» (**Akzeptanzkriterium Freischaltung**).
  - Freier Eintrag mit einem Wort aus 300 × `a` und `<script>alert(1)</script>` → Text sichtbar, kein Dialog (`Page.javascriptDialogOpening` unverändert), kein Überlauf auf Eintragsseite und «Meine Einträge» (Review Focus 3).
  - Zweite Lehrperson öffnet die Adresse eines Eintrags der ersten → «Nicht gefunden».
  - Auftraggeberin öffnet über die Seite von Runde 1 in der Eingabemaske die Löschbestätigung der beantworteten ersten Frage → Erklärung «schon … beantwortet», kein Knopf «Endgültig löschen» (Übergabe aus #15).
  - Start dunkel (390 px) und Start, Runde, «Meine Einträge» in 1280 px, je `keinUeberlauf`.
- [ ] **Step 2:** Screenshots `20-lp-start`, `21-lp-start-dunkel`, `22-lp-start-desktop`, `23-lp-infoblock`, `24-lp-runde`, `25-lp-runde-gespeichert`, `26-lp-tagebuch-wahl`, `27-lp-eintrag-impuls`, `28-lp-meine-eintraege`, `29-lp-loeschen`, `30-lp-nicht-gefunden`, `31-lp-runde-desktop`.
- [ ] **Step 3:** `make e2e` → «… bestanden, 0 fehlgeschlagen». Screenshots ansehen: Leiste unten nicht über Inhalt, Knöpfe tippbar, dunkel lesbar.
- [ ] **Step 4:** README: «Stand»-Absatz um «Lehrpersonen-Ansicht (Runden, Tagebuch, Meine Einträge)» ergänzen, Beschreibung von `make e2e` entsprechend.
- [ ] **Step 5:** `make lint test e2e` grün. Commit `test: E2E-Ablauf der Lehrperson, Doku (#16)`.

### Task 10: Entwurfsschutz im Browser-Tab (Soll)

Spec: «Abgelaufene Anmeldung und Entwurfsschutz». Fällt bei Zeitnot als Erstes weg; dann die übrigen Tasks unverändert lassen.

**Files:**
- Create: `app/static/js/entwurf.js`
- Modify: `app/templates/lehrperson/_rahmen.html` (`<script src="/static/js/entwurf.js" defer>` nur bei `ansicht.speichert`), `runde.html`, `tagebuch_neu.html`, `tagebuch_eintrag.html`, `app/static/css/style.css`, `docs/datenschutz.md` (Zeile aus der Spec in «Welche Daten entstehen»), `tests/test_lehrperson.py`, `tests/test_ansicht.py`, `tests/e2e-pilot.mjs`

**Interfaces:**
- Produces (Attribute): `data-entwurf="{konto_id}:runde-{runde_id}"`, `"{konto_id}:neu-frei"`, `"{konto_id}:neu-impuls-{impuls_id}"`, `"{konto_id}:neu-leitfrage-{leitfrage_id}"`, `"{konto_id}:tagebuch-{eintrag_id}"`; auf der Eintragsseite direkt nach dem Anlegen (`?erledigt=gespeichert`) `data-entwurf-verwerfen` mit dem Schlüssel aus Art und Bezug des Eintrags. Speicher-Schlüssel `entwurf:{schlüssel}:{feldname}` in `sessionStorage`; Normalisierung im Skript wie auf dem Server (`\r\n` → `\n`, `trim`). Hinweis mit Knopf «Verwerfen» als verstecktes Element im Template (`hidden`), das Skript zeigt es.

- [ ] **Step 1: Failing tests** `tests/test_lehrperson.py`: `test_data_entwurf_attribute(…)`: die fünf Schlüssel oben auf den jeweiligen Seiten; nach dem Anlegen zum Impuls `data-entwurf-verwerfen="{kid}:neu-impuls-{iid}"`; `src="/static/js/entwurf.js"` auf Lehrpersonen-Seiten, nicht auf `/verwaltung`. `tests/test_ansicht.py`: im Gast-Modus weder `data-entwurf` noch `entwurf.js`. `test_datenschutz_nennt_entwurf`: `docs/datenschutz.md` enthält `sessionStorage`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren (rund 60 Zeilen, keine Abhängigkeit). **Step 4:** PASS, Lint.
- [ ] **Step 5:** E2E-Schritt 6 der Spec in `ablaufLehrperson`: in Runde 1 tippen, ohne Speichern neu laden → Text wiederhergestellt, Hinweis sichtbar; «Verwerfen» → Feld zeigt den gespeicherten Stand; nach «Abmelden» ist `Object.keys(sessionStorage).filter((k) => k.startsWith("entwurf:")).length === 0`. Keine CSP-Fehler (`keineFehlerSeit`). Screenshot `32-lp-entwurf`. `make e2e` grün.
- [ ] **Step 6:** Commit `feat: Entwurfsschutz im Browser-Tab (#16)`.

## Nach dem Merge (Orchestrator)

- fly.io nach Spec: Deploy, als Testkonto einer Lehrperson die Startseite in 390 px prüfen, einen Tagebucheintrag anlegen und löschen, `user_version` = 3 per `fly ssh console` (als `appuser`). Keine Platzhalter laden. Screenshots aus dem E2E in den Pull Request (Akzeptanzkriterium «Handy und Computer»).
- Danach #17, #18, #19 in eigenen Worktrees von `main` starten; ihre Designs setzen den Stand nach diesem Plan voraus.
