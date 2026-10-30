# Eingabemaske für Inhalte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Auftraggeberin erfasst alle Inhalte selbst (Titel, Begrüssung, erster Tag, Infoblock, Runden mit Fragen, Leitfragen, Impulse, Hinweise), am Handy und am Computer, ohne JavaScript. Dazu kommen die Bausteine für #16–#19: Formatierung, Register der festen Texte und `heute()`.

**Architecture:** Die Fachlogik kommt ohne FastAPI aus und liegt in `app/eingaben.py` (Bereinigung, Fehler), `app/texte.py` (Register) und `app/inhalte.py` (Anlegen, Ändern, Löschen, Reihenfolge, Schutz der Forschungsdaten). Dazu kommt ein Router `app/routen/verwaltung_inhalte.py` mit `braucht_auftraggeberin` auf Router-Ebene, die Templates liegen unter `app/templates/verwaltung/inhalte/`. Es gibt keine Migration. Das Datum kommt nur über `app.state.heute`.

**Tech Stack:** Python 3.13, FastAPI, Jinja2 (`markupsafe`), sqlite3, `zoneinfo`, pytest, Node-E2E über CDP.

**Spec:** `docs/superpowers/specs/2026-10-30-eingabemaske-design.md`. Vor jeder Task lesen, auch den Abschnitt «Klärungen nach dem Builder-Check». Bei Widerspruch gilt die Klärung. Texte, Längen und Meldungen stehen dort.

## Vorbereitung (vor Task 1, Orchestrator)

- Branch `feat/15-eingabemaske` von `main`, nachdem #14 gemergt ist. Design nach `docs/superpowers/specs/2026-10-30-eingabemaske-design.md` kopieren, Commit `docs: Design der Eingabemaske (#15)`.
- **Schnittstellen aus #14 prüfen** (der Plan geht von diesem Stand aus; weicht er ab, die betroffene Task anpassen):
  1. `app/typen.py` stellt `Id = Annotated[int, Path(ge=1, le=2**63 - 1)]` bereit. `main.py` zeigt **jeden** `RequestValidationError` als 404-Fehlerseite. Daraus folgt: Formularfelder sind nie typisiert (siehe Global Constraints).
  2. `braucht_auftraggeberin`, `aktuelles_konto` (`app/sitzung.py`), `pruefe_csrf` und `csrf_feld` (`app/csrf.py`), `KeinZugriff(text, titel)` (`app/zugriff.py`). `pruefe_csrf` liest `await request.form()`, und `Form()`-Parameter derselben Route bleiben lesbar (wie in `app/routen/verwaltung.py`).
  3. `main.py` hat `fehlerseite(...)`, `FEHLERTEXTE` und Fehlerseiten für alle Status. `HTTPException(400)` und `HTTPException(404)` ergeben eine HTML-Fehlerseite.
  4. `tests/conftest.py`: `einstellungen`, `client` (`follow_redirects=False`), `lehrperson`, `auftraggeberin`, `csrf_von(client, pfad)`, `anmelden(client, name, pw)`. Achtung: Das Design nennt `konto_auftraggeberin`/`konto_lehrperson`, die Fixtures heissen aber `auftraggeberin`/`lehrperson`. `als_leitung` steht bisher nur in `tests/test_verwaltung.py`.
  5. `tests/test_routen_inventar.py` ersetzt jeden `{…}` durch `1` und prüft GET → 303, POST ohne CSRF → 403, Lehrperson auf `/verwaltung…` → 403.
  6. `app/kommandos.py` liest das Passwort **vor** jedem Unterbefehl ein (Task 7 ändert das).
  7. `style.css` hat Regeln für `textarea`, aber keine für `input[type=text]`/`input[type=date]`. Hat die Fix-Runde von #14 welche ergänzt, entfallen sie in Task 3.
  8. `tests/e2e-pilot.mjs`: `muss`, `tippe`, `sende`, `keinUeberlauf`, `merke`/`keineFehlerSeit`, `PW_AUFTRAGGEBERIN`. Das Konto wird per `spawnSync` vor `starteApp()` angelegt.
  9. `docs/datenschutz.md` (auf `main`, PR #24), Abschnitt «Hinweistexte»: die fünf Schlüssel und Platzhalter. Abschnitt «Für #15» beschreibt schon das Register, dort gibt es nichts nachzuziehen.

## Global Constraints

- Keine neuen Dependencies. Erlaubt sind Standardbibliothek (`zoneinfo`, `re`, `json`, `dataclasses`, `contextlib`), `markupsafe` (kommt mit Jinja2), `fastapi`, `jinja2`. Kein `tzdata`, kein Markdown- oder Sanitizer-Paket.
- Bezeichner, Kommentare und Texte auf Deutsch, ohne ß. In Bezeichnern Umlaute ausgeschrieben. Oberfläche nach der Begriffstabelle der Spec, Anrede «du». Nie «Datensatz», «ID», «Reihenfolge-Wert», «Markdown», «Schlüssel».
- In der Maske kein JavaScript, kein `style=`, keine externen Ressourcen. Neue CSS-Regeln nur am Ende von `app/static/css/style.css` im Abschnitt `/* Pilot: Eingabemaske */`.
- Keine Migration. `002` bleibt leer, #16 legt `003` an.
- Nirgends `| safe` auf Inhalte. Lange Texte (Begrüssung, Abschnitt, Fallbeispiel, Hinweis) nur mit `| formatiert` ausgeben, kurze als reinen Text.
- Datum in `app/` nur über `Depends(hole_heute)` bzw. Parameter `heute: date`. `date.today()`/`datetime.now()` gibt es nur in `app/zeit.py`.
- Pfadparameter immer `Id` aus `app/typen.py`, mit sprechenden Namen (`abschnitt_id`, `runde_id`, `frage_id`, `leitfrage_id`, `impuls_id`), dazu `schluessel: str`. Formularfelder immer `Annotated[str, Form()] = ""`, weil ein Validierungsfehler sonst als 404 endet. Geprüft wird in der Fachlogik.
- Jede POST-Route hat `dependencies=[Depends(pruefe_csrf)]`. Nach Erfolg kommt immer 303 (Formular abschicken, dann weiterleiten).
- Tippflächen mindestens `2.75rem` hoch. Auf 390 px kein horizontales Scrollen.
- Repo öffentlich: Die Platzhalter-Inhalte sind erfunden und neutral und stehen nie im Register.
- Commits: Präfix `feat:`/`test:`/`docs:`/`refactor:`/`fix:`, `(#15)` am Ende der ersten Zeile, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy8wrhdWVtdWcGb3tyj`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber. Der Ruff-Hook entfernt ungenutzte Imports zwischen Edits, deshalb Import und Verwendung im selben Edit schreiben.

## Review Focus

1. **Gesperrte Art einer beantworteten Frage:** Deaktivierte Radio-Knöpfe schickt der Browser nicht mit. Das Formular trägt deshalb ein verstecktes Feld `typ` mit der bisherigen Art. Speichern des Formulars, so wie es angezeigt wird, ergibt 303, nicht 400. (Task 4 `test_frage_mit_antworten_formular_speichern`)
2. **Veraltete Seite, doppeltes Absenden, Zurück-Taste:** Löschen oder Verschieben eines schon gelöschten Eintrags ergibt die 404-Seite, nie 500. Ein zweites Absenden von «Neue Runde» nach dem Neuladen der Zielseite legt nichts doppelt an. (Task 4 `test_doppelt_loeschen_404`, `test_neu_laden_legt_nicht_doppelt_an`)
3. **Aus Word eingefügter Text:** `\r\n`, `•`+Tab, Einrückung vor dem Listenzeichen und ein 300 Zeichen langes Wort ohne Leerzeichen erscheinen als Liste bzw. umbrochen, auf 390 px ohne horizontales Scrollen. (Task 1 `test_liste_zeichen`, Task 8 E2E «langes Wort»)
4. **Noch kein erster Tag, Datum vor dem Start:** Formulare und Listen funktionieren ohne erster Tag (Datum leer, keine Woche). Eine Runde vor dem ersten Tag zeigt «vor dem Start». (Task 4 `test_runden_ohne_ersten_tag`, `test_runde_vor_dem_start`)
5. **Titel mit Sonderzeichen oder voller Länge:** `<b>x</b>` erscheint escapt in Kopf und `<title>`. Ein Titel mit 60 Zeichen bricht im Kopf um. (Task 3 `test_titel_escapt`, Task 8 E2E)

---

### Task 1: Datum in Zürich und einfache Formatierung

**Files:**
- Create: `app/zeit.py`, `app/formatierung.py`, `tests/test_zeit.py`, `tests/test_formatierung.py`
- Modify: `app/vorlagen.py` (Filter `formatiert`, `datum`; Global `zeitplan`), `app/main.py` (`app.state.heute = zeit.heute` in `erstelle_app`), `tests/conftest.py` (Fixture `festes_heute`)

**Interfaces:**
- Produces (`app/zeit.py`):
  - `ZEITZONE = ZoneInfo("Europe/Zurich")`, `WOCHENTAGE = ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So")`
  - `heute(jetzt: datetime | None = None) -> date`: `jetzt` zeitzonenbewusst, Standard `datetime.now(ZEITZONE)`
  - `hole_heute(request: Request) -> date`: gibt `request.app.state.heute()` zurück
  - `lies_datum(text: str) -> date | None`: nur `^\d{4}-\d{2}-\d{2}$`, dann `date.fromisoformat`, `ValueError` → None
  - `ist_erreicht(datum: date, heute: date) -> bool` (`datum <= heute`)
  - `woche(datum: date, projektstart: date) -> int | None` (None vor dem Start, sonst `(tage // 7) + 1`)
  - `datum_kurz(datum: date, mit_jahr: bool = True) -> str` (`"Mo 30.11.2026"` bzw. `"Mo 30.11."`)
  - `class Zeitplan(NamedTuple)`: `datum: date`, `woche: int | None`, `sichtbar: bool`
  - `zeitplan(datum_text: str, projektstart: date | None, heute: date) -> Zeitplan` (`datum_text` stammt aus der DB und ist gültig)
- Produces (`app/formatierung.py`): `formatiere(text: str | None) -> Markup`. Ablauf nach Spec «Einfache Formatierung», Schritte 1–6. Eine Listenzeile passt auf `^\s*[-*•][ \t]+(\S.*)$` (führender Leerraum erlaubt). Fett wird mit `\*\*(\S(?:.*?\S)?)\*\*` **auf dem escapten Text** ersetzt. Die Tags werden ohne Leerraum dazwischen aneinandergereiht.
- Produces (`app/vorlagen.py`): `filters["formatiert"] = formatiere`. `filters["datum"]` nimmt `date` oder `"YYYY-MM-DD"` und gibt `datum_kurz` zurück, `mit_jahr` als optionales Argument. `globals["zeitplan"] = zeitplan`.
- Produces (`tests/conftest.py`): `festes_heute(client) -> date` setzt `client.app.state.heute = lambda: date(2026, 11, 30)` (ein Montag) und gibt das Datum zurück.

- [ ] **Step 1: Failing tests** `tests/test_zeit.py`:
  - `test_heute_winterzeit`: `heute(datetime(2026, 11, 22, 23, 30, tzinfo=UTC)) == date(2026, 11, 23)`
  - `test_heute_sommerzeit`: `heute(datetime(2026, 10, 24, 22, 30, tzinfo=UTC)) == date(2026, 10, 25)`
  - `test_lies_datum`: `"2026-11-23"` → `date(2026, 11, 23)`. Je None: `"20261123"`, `"2026-11-31"`, `"23.11.2026"`, `""`, `" 2026-11-23"`, `"2026-1-5"`.
  - `test_woche`: Start `date(2026, 11, 23)`: gleicher Tag → 1, +6 → 1, +7 → 2, +21 → 4, −1 → None.
  - `test_ist_erreicht` (gleicher Tag True, Folgetag False).
  - `test_datum_kurz`: `date(2026, 11, 30)` → `"Mo 30.11.2026"`, mit `mit_jahr=False` → `"Mo 30.11."`, `date(2026, 11, 29)` → `"So 29.11.2026"`.
  - `test_zeitplan`: `zeitplan("2026-11-30", date(2026, 11, 23), date(2026, 11, 29)) == Zeitplan(date(2026, 11, 30), 2, False)`. Mit `projektstart=None` ist `woche` None.
  - `test_zeitzone_laedt`: `ZEITZONE.key == "Europe/Zurich"` und `heute()` liefert ein `date`.
  - `test_app_nutzt_heute_aus_state(client)`: `client.app.state.heute is zeit.heute`.
  - `test_nur_zeit_kennt_die_uhr`: keine Datei unter `app/` ausser `zeit.py` enthält `date.today(` oder `datetime.now(`.
- [ ] **Step 2: Failing tests** `tests/test_formatierung.py` (Vergleich mit `str(formatiere(...))`):
  - `test_absaetze`: `"Erster\n\nZweiter"` und `"Erster\n\n\n\nZweiter"` → `"<p>Erster</p><p>Zweiter</p>"`
  - `test_zeilenumbruch`: `"a\nb"` → `"<p>a<br>b</p>"`; `test_crlf`: `"a\r\nb\r\n\r\nc"` → `"<p>a<br>b</p><p>c</p>"`
  - `test_liste_zeichen` (parametrisiert): `"- x"`, `"* x"`, `"• x"`, `"-\tx"`, `"•\tx"`, `"  - x"` → `"<ul><li>x</li></ul>"`
  - `test_liste_nach_textzeile`: `"Dazu gehört:\n- eins\n- zwei"` → `"<p>Dazu gehört:</p><ul><li>eins</li><li>zwei</li></ul>"`
  - `test_text_nach_liste`: `"- eins\nDanach"` → `"<ul><li>eins</li></ul><p>Danach</p>"`
  - `test_kein_listenzeichen`: `"-x"` → `"<p>-x</p>"`; `"**fett** am Anfang"` → `"<p><strong>fett</strong> am Anfang</p>"`
  - `test_fett`: `"Das ist **wichtig** hier"` → `"<p>Das ist <strong>wichtig</strong> hier</p>"`; `"- **a** b"` → `"<ul><li><strong>a</strong> b</li></ul>"`
  - `test_einzelnes_sternpaar`: `"a ** b"` → `"<p>a ** b</p>"`; `"** x **"` → `"<p>** x **</p>"`
  - `test_leer`: `None`, `""`, `"  \n \n"` → `Markup("")`
  - `test_html_escapt`: `"<script>alert(1)</script>"` → `"<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>"`; `'<img src=x onerror="a">'` enthält `&lt;img` und `&#34;`; `"Tom's"` enthält `&#39;`; `"&amp;"` → `"<p>&amp;amp;</p>"`; `"**<b>x</b>**"` → `"<p><strong>&lt;b&gt;x&lt;/b&gt;</strong></p>"`; `"- <script>"` → `"<ul><li>&lt;script&gt;</li></ul>"`
  - `test_feindliche_eingaben_ohne_fremde_tags`: Liste `FEINDLICH` mit mindestens 10 Eingaben (die obigen plus `"**<img src=x onerror=alert(1)>**"`, `"- **<a href=javascript:x>**"`, `"<<p>>"`, `"</p><script>"`). Nach `re.sub(r"</?(p|br|ul|li|strong)>", "", ausgabe)` enthält das Ergebnis kein `<`, und die Ausgabe ist eine `Markup`-Instanz.
  - `test_filter_registriert`: `templates.env.filters["formatiert"]("**a**") == Markup("<p><strong>a</strong></p>")`, `filters["datum"]("2026-11-30") == "Mo 30.11.2026"`, `filters["datum"](date(2026, 11, 30), mit_jahr=False) == "Mo 30.11."`
- [ ] **Step 3:** `uv run pytest tests/test_zeit.py tests/test_formatierung.py -v` → FAIL (ImportError).
- [ ] **Step 4:** `app/zeit.py`, `app/formatierung.py`, Filter und Global, `app.state.heute` und die Fixture implementieren.
- [ ] **Step 5:** `uv run pytest -v` → PASS, Lint sauber.
- [ ] **Step 6:** Commit `feat: Datum in Zuerich und einfache Formatierung (#15)`.

### Task 2: Register der festen Texte und Grundlagen der Inhalte

**Files:**
- Create: `app/eingaben.py`, `app/texte.py`, `app/inhalte.py`, `tests/test_texte.py`, `tests/test_inhalte.py`
- Modify: `app/db.py` (`transaktion`), `tests/conftest.py` (Fixture `db`)

**Interfaces:**
- Produces (`app/db.py`): `@contextmanager transaktion(db: sqlite3.Connection) -> Iterator[None]`. Ist `db.in_transaction` schon wahr, nur `yield` (äussere Transaktion entscheidet). Sonst `BEGIN IMMEDIATE`, nach Erfolg `COMMIT`, bei Ausnahme `ROLLBACK` und weiterwerfen.
- Produces (`app/eingaben.py`):
  - `class InhaltFehler(ValueError)`: `__init__(self, feld: str, meldung: str)`, Attribut `feld`
  - `class Gesperrt(Exception)`: `__init__(self, anzahl: int)`, Attribut `anzahl` (Zahl der Antworten, Task 4)
  - `LAENGE_TITEL_INSTRUMENT = 60`, `LAENGE_TITEL = 100`, `LAENGE_KURZ = 500`, `LAENGE_BESCHRIFTUNG = 60`, `LAENGE_LANG = 20_000`
  - `kurzer_text(wert: str, feld: str, hoechstens: int, leer_meldung: str | None) -> str | None`: `\r`/`\n` werden zu Leerzeichen, dann `strip`. Leer: bei `leer_meldung` None → None, sonst `InhaltFehler(feld, leer_meldung)`. Zu lang → `InhaltFehler(feld, zu_lang(hoechstens))`.
  - `langer_text(wert: str, feld: str, leer_meldung: str | None) -> str | None`: `\r\n`/`\r` → `\n`, `strip`, Grenze `LAENGE_LANG`, sonst wie oben.
  - `datum_feld(wert: str, feld: str, pflicht: bool) -> str | None`: `lies_datum(wert.strip())`. Ergebnis `isoformat()`, leer und nicht Pflicht → None, sonst `InhaltFehler(feld, "Bitte ein Datum wählen.")`.
  - `zu_lang(hoechstens: int) -> str`: `"Der Text ist zu lang (höchstens 20 000 Zeichen)."`. Das Tausendertrennzeichen ist ein geschütztes Leerzeichen, 500 bleibt `"500"`.
- Produces (`app/texte.py`): `Textvorlage` genau wie in der Spec. `REGISTER: dict[str, Textvorlage]` in dieser Reihenfolge: `begruessung` (Bereich `"allgemein"`, Bezeichnung «Begrüssung»), dann im Bereich `"hinweise"`: `hinweis_tagebuch` «Hinweis im Tagebuch», `hinweis_wer_sieht_was` «Wer sieht was», `hinweis_gast` «Hinweis für Gäste», `hinweis_datenspeicherung` «Datenschutz im Infoblock», `hinweis_aufnahme` «Hinweis zu Aufnahmen». `ort` ist ein kurzer Satz aus der Spalte «Wo er erscheint» in `docs/datenschutz.md`. `vorschlag` ist der Platzhalter von dort **wörtlich**. Den Vorschlag für die Begrüssung formuliert der Umsetzer, neutral und ohne Anrede.
  - `@dataclass(frozen=True) class Textstand`: `vorlage: Textvorlage`, `inhalt: str`, `bestaetigt: bool`, `geaendert: str | None`
  - `lies_text(db, schluessel: str) -> str`, `lies_textstand(db, schluessel: str) -> Textstand`, `lies_texte(db, bereich: str) -> list[Textstand]` (Register-Reihenfolge)
  - `speichere_text(db, schluessel: str, inhalt: str) -> None`: unbekannter Schlüssel → `KeyError`. `langer_text(inhalt, "inhalt", "Bitte einen Text eingeben.")`, dann `INSERT … ON CONFLICT(schluessel) DO UPDATE SET inhalt=…, geaendert=strftime('%Y-%m-%dT%H:%M:%SZ','now')`.
- Produces (`app/inhalte.py`, erster Teil; importiert `texte` und `eingaben`, `texte` importiert `inhalte` nicht):
  - `STANDARD_TITEL = "Reflexionsinstrument"`
  - `lies_titel(db) -> str`, `lies_projektstart(db) -> date | None` (aus `einstellungen`, Schlüssel `titel`/`projektstart`)
  - `speichere_allgemein(db, titel: str, begruessung: str, projektstart: str) -> None`, in `transaktion`. Prüfreihenfolge: `titel` (`kurzer_text`, 60, «Bitte einen Titel eingeben.»), `begruessung` (über `speichere_text`, Fehlerfeld wird `"begruessung"`), `projektstart` (`datum_feld`, nicht Pflicht). Leer löscht den Wert.
  - `zaehle_inhalte(db) -> dict[str, int]` mit den Schlüsseln `info_abschnitte`, `runden`, `fragen`, `runden_ohne_fragen`, `leitfragen`, `impulse`
- Produces (`tests/conftest.py`): `db(einstellungen, client) -> sqlite3.Connection` (`verbinde(einstellungen.db_pfad)`, nach dem Test schliessen; die Migration hat `client` schon ausgeführt).

- [ ] **Step 1: Failing tests** `tests/test_texte.py`:
  - `test_register_vollstaendig`: `list(REGISTER) == ["begruessung", "hinweis_tagebuch", "hinweis_wer_sieht_was", "hinweis_gast", "hinweis_datenspeicherung", "hinweis_aufnahme"]`. Jeder Eintrag hat nicht leere `bezeichnung`, `ort`, `vorschlag` und `schluessel == key`. Nur `begruessung` hat Bereich `"allgemein"`.
  - `test_vorschlaege_wie_datenschutz_doku`: Für die fünf Hinweise gilt `f"«{vorschlag}»" in Path("docs/datenschutz.md").read_text()`.
  - `test_keine_entwicklungs_platzhalter_im_register`: kein `vorschlag` enthält `"Platzhalter"`.
  - `test_ohne_zeile_gilt_vorschlag(db)`: `lies_text == vorschlag`. `lies_textstand` gibt `bestaetigt is False` und `geaendert is None`.
  - `test_speichern_bestaetigt_auch_unveraendert(db)`: Vorschlag unverändert speichern → `bestaetigt is True`, `geaendert` gesetzt.
  - `test_speichern_bereinigt(db)`: `"  a\r\nb  "` → `"a\nb"`.
  - `test_leer_speichern_verboten(db)`: `" \n "` → `InhaltFehler`, `feld == "inhalt"`, Meldung «Bitte einen Text eingeben.»
  - `test_zu_lang(db)`: `"x" * 20_001` → Meldung enthält `"höchstens 20 000 Zeichen"`, `"x" * 20_000` geht.
  - `test_unbekannter_schluessel(db)`: `speichere_text(db, "gibts_nicht", "x")` → `KeyError`.
- [ ] **Step 2: Failing tests** `tests/test_inhalte.py`:
  - `test_kurzer_text_wird_eine_zeile`: `kurzer_text("a\r\nb\nc ", "f", 500, "m") == "a b c"`. `kurzer_text("", "f", 60, None) is None`.
  - `test_titel_standard(db)`: `lies_titel(db) == "Reflexionsinstrument"`, `lies_projektstart(db) is None`.
  - `test_speichere_allgemein(db)`: `("Lernheft", "Hallo **alle**", "2026-11-23")` → Titel, `lies_text(db, "begruessung")`, `lies_projektstart == date(2026, 11, 23)`.
  - `test_allgemein_ohne_ersten_tag(db)`: zuerst mit Datum speichern, dann mit `""` → `lies_projektstart is None`.
  - `test_allgemein_fehler_schreibt_nichts(db)`: gültiger neuer Titel, aber `projektstart="23.11.2026"` → `InhaltFehler` mit `feld == "projektstart"`. Titel und Begrüssung bleiben wie vorher (Rollback).
  - `test_titel_zu_lang(db)`: 61 Zeichen → `feld == "titel"`. `test_begruessung_leer(db)` → `feld == "begruessung"`.
  - `test_transaktion_verschachtelt(db)`: In `transaktion(db)` wird `speichere_allgemein` aufgerufen und danach `RuntimeError` geworfen. Danach ist nichts gespeichert.
  - `test_zaehle_inhalte(db)`: per SQL 2 Runden (eine mit 3 Fragen), 1 Abschnitt → `{"runden": 2, "fragen": 3, "runden_ohne_fragen": 1, "info_abschnitte": 1, "leitfragen": 0, "impulse": 0}`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** `uv run pytest -v` PASS, Lint.
- [ ] **Step 6:** Commit `feat: Register fester Texte und Grundlagen der Inhalte (#15)`.

### Task 3: Übersicht, Allgemein, Titel im Seitenkopf, Zugriffsschutz

**Files:**
- Create: `app/routen/verwaltung_inhalte.py`, `app/templates/verwaltung/inhalte/uebersicht.html`, `…/allgemein.html`, `…/_teile.html` (Makros), `tests/test_verwaltung_inhalte.py`, `tests/test_inhalte_zugriff.py`
- Modify: `app/main.py` (Router einbinden), `app/vorlagen.py` (Context-Processor, Global `zahl`), `app/routen/verwaltung.py` (`_zahl` durch `zahl` aus `vorlagen` ersetzen), alle Templates mit festem «Reflexionsinstrument» (`basis.html`, `anmelden.html`, `fehler.html`, `lehrperson/start.html`, `verwaltung/*.html`), `verwaltung/rahmen.html` (Link «Inhalte»), `verwaltung/start.html` (Karte «Inhalte» wird `karte--link`), `tests/test_verwaltung.py` (`test_uebersicht`; `als_leitung` aus conftest importieren), `tests/conftest.py` (`als_leitung`, `als_lehrperson` hierher), `app/static/css/style.css`

**Interfaces:**
- Consumes: Task 1 (Filter), Task 2 (`speichere_allgemein`, `lies_titel`, `lies_projektstart`, `lies_textstand`, `lies_texte`, `zaehle_inhalte`, `InhaltFehler`).
- Produces (`app/vorlagen.py`):
  - `instrument_titel(request: Request) -> dict[str, str]`: Context-Processor, über `Jinja2Templates(directory=…, context_processors=[instrument_titel])` eingebunden. Liefert `{"instrument_titel": …}`. Den Wert speichert er pro Anfrage in `request.state.instrument_titel`. Er liest über eine kurze eigene Verbindung (`verbinde`, `lies_titel`, `close`). Fehlt `db_pfad` oder tritt ein `sqlite3.Error` auf, gilt `STANDARD_TITEL`, damit eine Fehlerseite nie selbst scheitert.
  - `zahl(anzahl: int, einzahl: str, mehrzahl: str) -> str` als Jinja-Global (`"1 Runde"`, `"2 Runden"`)
- Produces (`app/routen/verwaltung_inhalte.py`):
  - `router = APIRouter(prefix="/verwaltung/inhalte", dependencies=[Depends(braucht_auftraggeberin)])`, `DB = Annotated[sqlite3.Connection, Depends(hole_db)]`, `HEUTE = Annotated[date, Depends(hole_heute)]`
  - `ERLEDIGT = {"gespeichert": "Gespeichert.", "angelegt": "Angelegt.", "geloescht": "Gelöscht."}`; `_meldung(request) -> str | None` (nur aus `ERLEDIGT`)
  - `_weiter(pfad: str, erledigt: str | None = None, anker: str | None = None) -> RedirectResponse` (303, `?erledigt=…`, `#anker`)
  - `_oder_404(zeile)`: None → `HTTPException(404)`
  - Formularfehler: dasselbe Template mit `werte: dict`, `fehler: dict[str, str]`, Status 400. Oben steht «Bitte prüfe die markierten Felder.», am Feld `<p class="fehler" id="fehler-{feld}">`, das Eingabefeld hat `aria-describedby="fehler-{feld}"`.
  - Routen: `GET ""` (Übersicht), `GET`/`POST "/allgemein"` (Erfolg → `/verwaltung/inhalte/allgemein?erledigt=gespeichert`).
- Übersicht: eine `karte karte--link` pro Bereich, jeweils mit `id="bereich-…"` (`allgemein`, `info`, `runden`, `leitfragen`, `impulse`, `hinweise`). Die Links auf die Bereiche der Tasks 4–6 gibt es schon (bis dahin 404, nur auf dem Branch). Stand-Zeilen: «Erster Tag: Mo 23.11.2026» bzw. «Erster Tag noch nicht festgelegt», «N Abschnitte», «N Runden, M Fragen», «N Leitfragen», «N Impulse», «N von 5 Hinweisen bestätigt». Die Marke `marke marke--offen` «Noch offen» erscheint, wenn kein erster Tag festgelegt oder die Begrüssung nicht bestätigt ist (Allgemein), wenn es keine Runde oder eine Runde ohne Fragen gibt (Runden) und wenn nicht alle Hinweise bestätigt sind (Hinweise). An der Stelle des Vorschau-Links steht `{# #19: Vorschau-Link #}`.
- Allgemein: Felder `titel` (text), `begruessung` (textarea `rows="12"`, Formatierungs-Hilfe), `projektstart` (date) mit Hilfetext aus Spec «Erster Tag». Ist die Begrüssung nicht bestätigt, steht `marke` «Vorschlag, noch nicht von dir bestätigt» am Feld. Über dem Formular zeigt eine Karte `id="begruessung-anzeige"` «So erscheint die Begrüssung» den gespeicherten Text bzw. den Vorschlag `| formatiert`. Das entspricht der Regel «Inhalt so zeigen, wie ihn die Lehrperson sieht».
- Makro `formatier_hilfe()` in `_teile.html` mit genau: «Leerzeile = neuer Absatz · Zeile mit «- » am Anfang = Aufzählung · \*\*Wort\*\* = fett».
- CSS: `input[type="text"], input[type="date"]` wie `textarea` (Breite 100 %, `min-height: 2.75rem`, `min-width: 0`, iOS: `appearance: none` beim Datum, damit es die Breite hält). `.formatiert` (`overflow-wrap: anywhere`, Abstände für `p`/`ul`). Kopfzeile einer Karte mit Marke rechts.

- [ ] **Step 1: Failing tests** `tests/test_verwaltung_inhalte.py`:
  - `test_uebersicht_zeigt_bereiche`: 200, sechs Links `href="/verwaltung/inhalte/{allgemein,info,runden,leitfragen,impulse,hinweise}"`, «0 von 5 Hinweisen bestätigt», «Erster Tag noch nicht festgelegt», «Noch offen» in `bereich-allgemein`, `bereich-runden` und `bereich-hinweise`.
  - `test_uebersicht_stand(db)`: per SQL `projektstart=2026-11-23`, 2 Runden (eine ohne Fragen), 3 Fragen → «Erster Tag: Mo 23.11.2026», «2 Runden, 3 Fragen», Marke weiterhin in `bereich-runden`.
  - `test_allgemein_zeigt_vorschlag_markiert`: Das Feld `begruessung` enthält `REGISTER["begruessung"].vorschlag`, dazu «Vorschlag, noch nicht von dir bestätigt».
  - `test_allgemein_speichern`: POST `titel="Lernheft"`, `begruessung="Hallo\n\n- a\n- **b**"`, `projektstart="2026-11-23"` → 303, `location == "/verwaltung/inhalte/allgemein?erledigt=gespeichert"`. Danach GET: «Gespeichert.», keine Vorschlag-Marke, `<p>Hallo</p><ul><li>a</li><li><strong>b</strong></li></ul>` in der Anzeige, `<title>` enthält «Lernheft», `seitenkopf__titel` enthält «Lernheft». Ein frischer Client ohne Anmeldung sieht «Lernheft» auf `/`.
  - `test_allgemein_fehler`: `projektstart="23.11.2026"` → 400, «Bitte prüfe die markierten Felder.», «Bitte ein Datum wählen.», `aria-describedby="fehler-projektstart"`, der eingegebene Titel steht wieder im Feld.
  - `test_titel_escapt`: Titel `<b>x</b>` → `&lt;b&gt;x&lt;/b&gt;` im HTML, `<b>x</b>` nicht.
  - `test_fehlerseite_zeigt_titel`: gespeicherter Titel, `GET /gibts-nicht` → 404 mit dem Titel im Kopf.
  - `test_kein_fester_titel_in_templates`: keine Datei unter `app/templates/` enthält «Reflexionsinstrument».
  - `test_bestaetigung_nur_aus_fester_liste`: `?erledigt=<script>` → weder `<script>` noch `&lt;script` auf der Seite.
  - `test_verwaltung_verlinkt_inhalte`: `/verwaltung` enthält `href="/verwaltung/inhalte"`, die Navigation enthält «Inhalte».
- [ ] **Step 2: Failing tests** `tests/test_inhalte_zugriff.py` (Akzeptanzkriterium «Nur die Auftraggeberin kann Inhalte ändern»):
  - Fixture `beispielinhalte(db)`: je eine Zeile in `info_abschnitte`, `runden`, `fragen` (Runde 1), `leitfragen`, `impulse` (alle `id = 1`), Einstellung `titel`, Text `hinweis_tagebuch`.
  - `routen(einstellungen, methode)`: Inventar wie in `test_routen_inventar.py`, gefiltert auf das Präfix `/verwaltung/inhalte`. `\{\w+_id\}` → `1`, `{schluessel}` → `hinweis_tagebuch`.
  - `abzug(db) -> dict[str, list[tuple]]`: alle Zeilen von `einstellungen`, `texte`, `info_abschnitte`, `runden`, `fragen`, `leitfragen`, `impulse`, `antworten`, `tagebucheintraege`, sortiert.
  - `FORMULAR`: plausible Werte für alle Felder (`titel`, `inhalt`, `text`, `begruessung`, `projektstart`, `freischaltdatum`, `sichtbar_ab`, `typ="freitext"`, `fallbeispiel`, `skala_min_text`, `skala_max_text`, `richtung="runter"`), alle auf «Geändert» bzw. `2026-12-01`.
  - `test_lehrperson_kann_keine_inhalte_aendern(client, db, lehrperson, beispielinhalte)`: als Lehrperson angemeldet. Jede GET-Route → 403 mit «Kein Zugriff». Jede POST-Route mit `csrf_von(client, "/lehrperson")` plus `FORMULAR` → 403 mit «Kein Zugriff». `abzug(db)` vorher == nachher.
  - `test_kontrolle_auftraggeberin_aendert(…)`: dieselbe POST-Anfrage auf `/verwaltung/inhalte/allgemein` als Auftraggeberin → 303, `abzug` ändert sich (schützt vor einem Test, der immer grün ist).
  - `test_inventar_inhalte_nicht_leer`: `/verwaltung/inhalte` und `/verwaltung/inhalte/allgemein` sind in GET enthalten. Spätere Tasks erweitern die Liste nicht von Hand, das Inventar wächst mit.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** `uv run pytest -v` PASS. Das Routen-Inventar aus #14 bleibt grün. Lint.
- [ ] **Step 6:** Commit `feat: Uebersicht der Inhalte, Allgemein und Titel im Seitenkopf (#15)`.

### Task 4: Runden und Fragen, Schutz der Forschungsdaten

**Files:**
- Create: `app/templates/verwaltung/inhalte/runden.html`, `…/runde.html`, `…/formular_runde.html`, `…/formular_frage.html`, `…/loeschen.html`
- Modify: `app/inhalte.py`, `app/routen/verwaltung_inhalte.py`, `…/_teile.html` (Makros `verschieben`, `zeitangabe`), `app/static/css/style.css`, `tests/test_inhalte.py`, `tests/test_verwaltung_inhalte.py`, `tests/conftest.py` (Helfer `lege_antwort_an`, `lege_eintrag_an`)

**Interfaces:**
- Consumes: Task 2 (`transaktion`, `eingaben.*`, `Gesperrt`), Task 1 (`zeitplan`, `lies_datum`), Task 3 (Router-Helfer).
- Produces (`app/inhalte.py`):
  - `SKALA_MIN = 1`, `SKALA_MAX = 5`, `TYPEN = ("freitext", "skala")`
  - `runden(db) -> list[sqlite3.Row]` (`id, titel, fallbeispiel, freischaltdatum, anzahl_fragen`; `ORDER BY freischaltdatum, id`), `runde(db, runde_id: int) -> sqlite3.Row | None` (dieselben Spalten)
  - `datum_vorschlag_runde(db) -> date | None`: letztes `freischaltdatum` + 7 Tage, ohne Runden der erste Tag, ohne ersten Tag None (Klärung)
  - `lege_runde_an(db, titel: str, fallbeispiel: str, freischaltdatum: str) -> int`, `aendere_runde(db, runde_id: int, titel: str, fallbeispiel: str, freischaltdatum: str) -> None`. Titel: Grenze 100, «Bitte einen Titel eingeben.». Fallbeispiel: `langer_text`, freiwillig, leer wird NULL. Datum: Pflicht. `reihenfolge` bleibt 0.
  - `zaehle_antworten_runde(db, runde_id) -> int`, `zaehle_antworten_frage(db, frage_id) -> int` (jede Zeile in `antworten`)
  - `loesche_runde(db, runde_id: int) -> int` (Zahl der mitgelöschten Fragen). Antworten vorhanden → `Gesperrt(anzahl)`. `sqlite3.IntegrityError` beim Löschen → ebenfalls `Gesperrt` (Sicherheitsnetz im Fachcode, die Route fängt nur `Gesperrt`).
  - `fragen(db, runde_id) -> list[sqlite3.Row]` (mit `anzahl_antworten`; `ORDER BY reihenfolge, id`), `frage(db, frage_id) -> sqlite3.Row | None` (mit `anzahl_antworten`)
  - `lege_frage_an(db, runde_id: int, typ: str, text: str, skala_min_text: str, skala_max_text: str) -> int`. `reihenfolge` = max + 1 in **einer** Anweisung (`INSERT … SELECT coalesce(max(reihenfolge), 0) + 1 …`).
  - `aendere_frage(db, frage_id: int, typ: str, text: str, skala_min_text: str, skala_max_text: str) -> None`. In `transaktion`: Weicht die Art ab und gibt es Antworten → `InhaltFehler("typ", «Die Art lässt sich nicht mehr ändern, weil die Frage schon beantwortet wurde. Lege bei Bedarf eine neue Frage an.»)`.
  - Prüfung der Fragefelder: `typ` nicht in `TYPEN` → `InhaltFehler("typ", "Bitte die Art der Antwort wählen.")`. Text: Grenze 500, «Bitte eine Frage eingeben.». Bei Skala: Beschriftungen mit Grenze 60, eine leere → `InhaltFehler("skala_min_text" bzw. "skala_max_text", "Für die Skala braucht es beide Beschriftungen.")`. Bei Freitext werden beide als NULL gespeichert.
  - `loesche_frage(db, frage_id: int) -> None`: `Gesperrt` wie bei der Runde, danach die Runde neu nummerieren.
  - `GEORDNET = {"info": ("info_abschnitte", None), "frage": ("fragen", "runde_id"), "leitfrage": ("leitfragen", None)}`
  - `verschiebe(db, art: str, eintrag_id: int, richtung: str) -> None`: `richtung` nicht in `("hoch", "runter")` → `ValueError`. In `transaktion`: die Gruppe mit `ORDER BY reihenfolge, id` lesen, mit dem Nachbarn tauschen, alle als 1…n schreiben. Am Rand ohne Wirkung.
  - `_nummeriere(db, art: str, gruppe: int | None) -> None` (nach dem Löschen, 1…n)
- Produces (Routen): die Zeilen für Runden und Fragen aus der Spec-Tabelle «Adressen». Weiterleitungen:
  - Runde anlegen → `/verwaltung/inhalte/runden/{id}?erledigt=angelegt`
  - Runde ändern → `…/runden/{id}?erledigt=gespeichert`
  - Runde löschen → `/verwaltung/inhalte/runden?erledigt=geloescht`
  - Frage anlegen/ändern → `…/runden/{runde_id}?erledigt=angelegt|gespeichert#frage-{id}`
  - Frage verschieben → `…/runden/{runde_id}#frage-{id}`
  - Frage löschen → `…/runden/{runde_id}?erledigt=geloescht`
  - Ungültige `richtung` → `HTTPException(400)`. `Gesperrt` → `loeschen.html` mit 409.
- `loeschen.html` (gemeinsam für alle Bereiche): Kontext `ueberschrift`, `frage_text` (z. B. «Runde ‹…› löschen?»), `folgen` (Satz oder None), `gesperrt` (Satz oder None), `aktion` (POST-Pfad), `zurueck` (Abbrechen-Pfad). Ist `gesperrt` gesetzt, gibt es keinen Knopf «Endgültig löschen».
- Makro `verschieben(pfad, bezeichnung, erster, letzter)`: zwei Formulare (POST `{pfad}/verschieben`, `richtung=hoch|runter`), `knopf knopf--klein`, Text «↑ Nach oben»/«↓ Nach unten», `aria-label="‹{bezeichnung}› nach oben"`. Der erste Eintrag hat kein «Nach oben», der letzte kein «Nach unten».
- Routen mit Datumsanzeige übergeben `projektstart = lies_projektstart(db)` und `heute` (aus `HEUTE`). Das Template ruft `zeitplan(eintrag.freischaltdatum, projektstart, heute)` auf.
- Makro `zeitangabe(zp)` (`Zeitplan`): «Mo 30.11.2026 · Woche 2» bzw. «· vor dem Start» (nur mit erstem Tag), dazu Marke «Sichtbar» oder «Ab Mo 30.11.».
- Formular Frage: `fieldset.feld` mit `legend` «Art der Antwort», Radios «Antwort als Text»/«Antwort auf einer Skala von 1 bis 5». Mit Antworten: Radios `disabled`, verstecktes `<input type="hidden" name="typ">` mit der bisherigen Art und der Satz aus der Spec. Frage `textarea rows="3"`, Beschriftungen «Beschriftung bei 1»/«Beschriftung bei 5» mit Hilfe «Nur bei der Skala nötig.». Mit Antworten steht über dem Formular «Diese Frage wurde schon N-mal beantwortet. Die Antworten bleiben erhalten und stehen danach unter dem neuen Text.»
- Formular Runde: `titel`, `freischaltdatum` (date, bei «Neu» `datum_vorschlag_runde`), `fallbeispiel` (`rows="12"`, Formatierungs-Hilfe). Ist die Runde schon sichtbar (`ist_erreicht`), steht der Hinweis aus der Spec «Runden: Reihenfolge…» im Formular.
- Seite der Runde: Angaben mit `zeitangabe`, Fallbeispiel `| formatiert`, Links «Angaben bearbeiten» und «Runde löschen», Fragen als Karten mit `id="frage-{id}"`, Art, Text, Beschriftungen, «Bearbeiten», «Löschen», `verschieben`, Knopf «Neue Frage». Dazu `{# #19: Vorschau-Link #}`.
- Conftest: `lege_antwort_an(db, frage_id: int, konto_id: int, text: str | None = "Antwort", aufnahme_id: int | None = None) -> int`, `lege_eintrag_an(db, konto_id: int, art: str = "frei", impuls_id: int | None = None, leitfrage_id: int | None = None) -> int`. Der Eintrag kopiert `impuls_text`/`leitfrage_text` aus der Quelle, wie es #16 tun wird.

- [ ] **Step 1: Failing tests** `tests/test_inhalte.py` (Fachlogik):
  - `test_runden_nach_datum_sortiert`: Daten `2026-12-07`, `2026-11-23`, `2026-11-23` → Reihenfolge nach Datum, bei Gleichstand nach `id`.
  - `test_datum_vorschlag_runde`: ohne ersten Tag und ohne Runden → None. Erster Tag `2026-11-23` → `date(2026, 11, 23)`. Mit Runde am `2026-11-30` → `date(2026, 12, 7)`.
  - `test_runde_fallbeispiel_leer_ist_null`, `test_runde_ungueltig` (Titel leer → `feld == "titel"`; Datum `""` → `feld == "freischaltdatum"`, «Bitte ein Datum wählen.»).
  - `test_frage_anlegen_am_ende`: drei Fragen → `reihenfolge` 1, 2, 3.
  - `test_freitext_speichert_keine_beschriftungen`, `test_skala_braucht_beschriftungen` (`feld == "skala_min_text"`, Meldung genau), `test_unbekannte_art` (`feld == "typ"`).
  - `test_verschiebe_frage`: `[a, b, c]`, `c` hoch → `[a, c, b]`, `reihenfolge` 1..3. `a` hoch und `c` runter ohne Wirkung. Fragen einer anderen Runde bleiben unverändert. Ungültige Richtung → `ValueError`.
  - `test_verschiebe_repariert_reihenfolge`: Werte `0, 0, 5` per SQL → nach `verschiebe` sauber 1..3.
  - `test_loeschen_nummeriert_neu`: Mitte löschen → 1, 2.
  - `test_frage_mit_antworten_text_aendern`: 2 Antworten. Text und Beschriftungen ändern → `SELECT * FROM antworten` vorher == nachher.
  - `test_frage_mit_antworten_art_aendern_verboten`: `InhaltFehler`, `feld == "typ"`. Art, Text und Antworten bleiben unverändert.
  - `test_frage_mit_antworten_loeschen_gesperrt`: `Gesperrt` mit `anzahl == 2`. Frage und Antworten sind noch da.
  - `test_antwort_nur_aufnahme_sperrt`: Antwort mit `text=None` und Aufnahme → gesperrt.
  - `test_runde_mit_antworten_loeschen_gesperrt` (alles da), `test_runde_ohne_antworten_loeschen` (Rückgabe 2, Runde und Fragen weg).
  - `test_sicherheitsnetz_integrity_error(monkeypatch)`: `app.inhalte.zaehle_antworten_frage` gibt 0 zurück, obwohl Antworten existieren → `loesche_frage` wirft `Gesperrt`, nicht `IntegrityError`.
- [ ] **Step 2: Failing tests** `tests/test_verwaltung_inhalte.py` (Routen, als Auftraggeberin):
  - `test_runde_anlegen_leitet_auf_runde`: 303 auf `/verwaltung/inhalte/runden/{id}?erledigt=angelegt`, die Seite zeigt «Angelegt.».
  - `test_neu_laden_legt_nicht_doppelt_an`: nach dem POST zweimal GET auf `location` → genau eine Runde.
  - `test_neue_runde_datum_vorgeschlagen`: erster Tag `2026-11-23`, eine Runde am `2026-11-23` → Formular `value="2026-11-30"`.
  - `test_runden_ohne_ersten_tag`: Formular «Neue Runde» mit leerem Datum, Liste ohne «Woche», beides 200.
  - `test_runden_liste_zeigt_woche_und_marke(festes_heute)`: erster Tag `2026-11-23`, Runden am 23.11. und 07.12. → «Woche 1», «Sichtbar», «Woche 3», «Ab Mo 07.12.». Keine Knöpfe «Nach oben» in der Rundenliste.
  - `test_runde_vor_dem_start`: Runde am `2026-11-20` → «vor dem Start».
  - `test_hinweis_bei_sichtbarer_runde(festes_heute)`: Bearbeiten einer Runde vom `2026-11-30` zeigt «Diese Runde ist schon sichtbar.», bei `2026-12-07` nicht.
  - `test_fallbeispiel_formatiert`: `"- a\n- b"` → `<ul><li>a</li><li>b</li></ul>` auf der Seite der Runde.
  - `test_frage_anlegen_und_umsortieren`: zwei Fragen anlegen → 303 mit `#frage-{id}`. Die zweite «hoch» → 303 auf `…/runden/{rid}#frage-{id}`, sie steht jetzt im HTML zuerst.
  - `test_verschieben_knoepfe`: Die erste Frage hat kein «Nach oben», die letzte kein «Nach unten». `aria-label="‹{text}› nach oben"` ist vorhanden.
  - `test_frage_skala_ohne_beschriftung_400`: 400, Meldung, `aria-describedby="fehler-skala_min_text"`, der eingegebene Fragetext steht wieder im Feld.
  - `test_frage_mit_antworten_formular_speichern`: Formular enthält `disabled`, `type="hidden" name="typ" value="freitext"`, «schon 2-mal beantwortet». POST mit `typ="freitext"` und neuem Text → 303. POST mit `typ="skala"` und Beschriftungen → 400 mit dem Satz zur Art, Art in der DB unverändert.
  - `test_frage_loeschen_gesperrt_409`: Die GET-Bestätigung zeigt «Diese Frage wurde schon 2-mal beantwortet.» ohne «Endgültig löschen». POST → 409, Frage und Antworten unverändert.
  - `test_sicherheitsnetz_route(monkeypatch)`: wie im Fachtest, POST → 409 statt 500.
  - `test_runde_loeschen`: Bestätigung «Die Runde und ihre 2 Fragen werden gelöscht.». POST → 303 `?erledigt=geloescht`, Runde und Fragen weg.
  - `test_unbekannte_ids_404`: GET und POST auf `runden/999`, `runden/999/bearbeiten`, `runden/999/loeschen`, `runden/999/fragen/neu`, `fragen/999`, `fragen/999/verschieben`, `fragen/999/loeschen` → 404. Ebenso `runden/0`, `runden/abc`, `runden/99999999999999999999` (GET).
  - `test_doppelt_loeschen_404`: Frage löschen, derselbe POST noch einmal → 404.
  - `test_richtung_ungueltig_400`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren (Texte nach Spec, Einzahl/Mehrzahl mit `zahl`). **Step 5:** `uv run pytest -v` PASS (Zugriffstest aus Task 3 deckt die neuen Routen ab), Lint.
- [ ] **Step 6:** Commit `feat: Runden und Fragen erfassen, Antworten geschuetzt (#15)`.

### Task 5: Infoblock und Leitfragen

**Files:**
- Create: `app/templates/verwaltung/inhalte/info.html`, `…/formular_info.html`, `…/leitfragen.html`, `…/formular_leitfrage.html`
- Modify: `app/inhalte.py`, `app/routen/verwaltung_inhalte.py`, `tests/test_inhalte.py`, `tests/test_verwaltung_inhalte.py`

**Interfaces:**
- Consumes: Task 4 (`verschiebe`, `_nummeriere`, `GEORDNET`, `loeschen.html`, Makro `verschieben`), Task 2 (`lies_textstand`).
- Produces (`app/inhalte.py`):
  - `info_abschnitte(db) -> list[sqlite3.Row]` (`ORDER BY reihenfolge, id`), `info_abschnitt(db, abschnitt_id) -> sqlite3.Row | None`
  - `lege_info_an(db, titel: str, inhalt: str) -> int`, `aendere_info(db, abschnitt_id: int, titel: str, inhalt: str) -> None`, `loesche_info(db, abschnitt_id: int) -> None`. Titel: Grenze 100, Pflicht. Inhalt: `langer_text`, Pflicht «Bitte einen Text eingeben.».
  - `leitfragen(db) -> list[sqlite3.Row]` (mit `anzahl_eintraege`), `leitfrage(db, leitfrage_id) -> sqlite3.Row | None` (mit `anzahl_eintraege`)
  - `lege_leitfrage_an(db, text: str) -> int`, `aendere_leitfrage(db, leitfrage_id: int, text: str) -> None`, `loesche_leitfrage(db, leitfrage_id: int) -> None`. Text: Grenze 500, «Bitte eine Leitfrage eingeben.».
- Produces (Routen): Infoblock und Leitfragen laut Spec-Tabelle. Anker `#abschnitt-{id}` bzw. `#leitfrage-{id}`. Weiterleitung auf die Liste mit `erledigt` und Anker, beim Verschieben nur der Anker.
- Infoblock-Liste: Karten mit Titel, Inhalt `| formatiert`, «Bearbeiten», «Löschen», `verschieben`. Am Ende eine feste Karte «Datenschutz (immer am Schluss)» mit `lies_text(db, "hinweis_datenspeicherung") | formatiert`, Link «Bearbeiten» auf `/verwaltung/inhalte/hinweise/hinweis_datenspeicherung` (Route folgt in Task 6), ohne Verschieben und Löschen. Dazu `{# #19: Vorschau-Link #}`.
- Leitfrage mit Einträgen: Im Formular steht «N Tagebucheinträge beziehen sich darauf. Sie behalten den Text, den die Lehrperson damals gesehen hat.» (Einzahl: «1 Tagebucheintrag bezieht sich darauf.»). Auf der Bestätigungsseite steht «Einträge, die sich darauf beziehen, bleiben erhalten.» (Klärung).

- [ ] **Step 1: Failing tests** `tests/test_inhalte.py`: `test_info_anlegen_am_ende`, `test_info_ungueltig` (Titel leer, Inhalt `"x" * 20_001`), `test_info_loeschen_nummeriert_neu`, `test_leitfrage_eine_zeile` (`"a\nb"` → `"a b"`), `test_leitfrage_mit_eintrag_aendern` (`leitfrage_text` des Eintrags unverändert, `leitfrage_id` gesetzt), `test_leitfrage_mit_eintrag_loeschen` (Eintrag da, `leitfrage_id IS NULL`, `leitfrage_text` unverändert).
- [ ] **Step 2: Failing tests** `tests/test_verwaltung_inhalte.py`:
  - `test_info_anlegen_mit_anker`: 303 auf `/verwaltung/inhalte/info?erledigt=angelegt#abschnitt-{id}`.
  - `test_info_liste_formatiert_und_escapt`: Inhalt `"- a\n- **b**"` → `<ul><li>a</li><li><strong>b</strong></li></ul>`. Ein Abschnitt mit `<script>alert(1)</script>` erscheint als `&lt;script&gt;`.
  - `test_info_datenschutz_karte_am_schluss`: «Datenschutz (immer am Schluss)» steht im HTML nach dem letzten Abschnitt, mit dem Vorschlag-Text und dem Link auf `hinweise/hinweis_datenspeicherung`, ohne «Nach oben» und ohne Lösch-Link in dieser Karte.
  - `test_info_verschieben`: «hoch» → 303 nur mit Anker (`?erledigt` fehlt), die Reihenfolge im HTML ist getauscht.
  - `test_info_loeschen`: Die GET-Bestätigung hat den Knopf «Endgültig löschen». POST → 303 `?erledigt=geloescht`.
  - `test_info_fehler_400`: Titel leer → 400 mit «Bitte einen Titel eingeben.», der eingegebene Text bleibt stehen.
  - `test_leitfrage_mit_eintrag_hinweise`: Das Formular zeigt «1 Tagebucheintrag bezieht sich darauf», die Bestätigungsseite «Einträge, die sich darauf beziehen, bleiben erhalten.».
  - `test_leitfragen_verschieben_und_loeschen`.
  - `test_unbekannte_ids_404_info_leitfragen` (GET/POST auf `999` für Bearbeiten, Verschieben, Löschen).
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** PASS, Lint.
- [ ] **Step 6:** Commit `feat: Infoblock und Leitfragen erfassen und sortieren (#15)`.

### Task 6: Impulse und Hinweise

**Files:**
- Create: `app/templates/verwaltung/inhalte/impulse.html`, `…/formular_impuls.html`, `…/hinweise.html`, `…/formular_hinweis.html`
- Modify: `app/inhalte.py`, `app/routen/verwaltung_inhalte.py`, `tests/test_inhalte.py`, `tests/test_verwaltung_inhalte.py`

**Interfaces:**
- Consumes: Task 2 (`REGISTER`, `lies_texte`, `lies_textstand`, `speichere_text`), Task 4 (`loeschen.html`, `zeitangabe`).
- Produces (`app/inhalte.py`):
  - `impulse(db) -> list[sqlite3.Row]` (mit `anzahl_eintraege`; `ORDER BY sichtbar_ab, id`), `impuls(db, impuls_id) -> sqlite3.Row | None`
  - `datum_vorschlag_impuls(db) -> date | None`: dieselbe Regel wie bei Runden (letztes + 7, sonst erster Tag, sonst None). Abweichung vom Haupttext der Spec («erster Tag + 7 × Anzahl») zugunsten der Klärung für Runden, damit beide gleich funktionieren.
  - `lege_impuls_an(db, text: str, sichtbar_ab: str) -> int`, `aendere_impuls(db, impuls_id: int, text: str, sichtbar_ab: str) -> None`, `loesche_impuls(db, impuls_id: int) -> None`. Text: Grenze 500, «Bitte einen Impuls eingeben.». Datum: Pflicht.
- Produces (Routen): Impulse und Hinweise laut Spec-Tabelle. Impulse ohne Verschieben, Anker `#impuls-{id}`. Hinweise: `schluessel` nicht in `REGISTER` oder Bereich nicht `"hinweise"` → 404 (auch `begruessung`). Speichern → 303 auf `/verwaltung/inhalte/hinweise?erledigt=gespeichert#hinweis-{schluessel}`.
- Impulsliste: Karte mit Text, `zeitangabe`, «Bearbeiten», «Löschen». Sind zwei Impulse am selben Tag, steht bei diesen der Satz aus der Spec «Am selben Tag gibt es noch einen Impuls. …». Die Route übergibt dazu `doppelte_tage: set[str]`. Hinweis zu Einträgen wie bei Leitfragen.
- Hinweisliste: pro Eintrag aus `lies_texte(db, "hinweise")` eine Karte `id="hinweis-{schluessel}"` mit Bezeichnung, «Erscheint: {ort}», Marke «Vorschlag, noch nicht von dir bestätigt» (`marke--offen`) bzw. «Bestätigt» (`marke--erledigt`), Text `| formatiert`, Link «Bearbeiten». Formular: Ort als Hilfetext über dem Feld, `textarea rows="12"`, Formatierungs-Hilfe, bei unbestätigtem Text der Satz «Bestätigen heisst speichern, auch unverändert.».

- [ ] **Step 1: Failing tests** `tests/test_inhalte.py`: `test_impulse_nach_datum`, `test_datum_vorschlag_impuls`, `test_impuls_ungueltig` (Datum `"2026-11-31"`), `test_impuls_mit_eintrag_aendern_und_loeschen` (`impuls_text` unverändert, nach dem Löschen `impuls_id IS NULL`).
- [ ] **Step 2: Failing tests** `tests/test_verwaltung_inhalte.py`:
  - `test_impuls_anlegen_mit_vorschlag`: erster Tag `2026-11-23`, Formular `value="2026-11-23"`. POST → 303 `/verwaltung/inhalte/impulse?erledigt=angelegt#impuls-{id}`.
  - `test_impulse_gleicher_tag_hinweis`: zwei am selben Datum → Satz «Am selben Tag gibt es noch einen Impuls.».
  - `test_impuls_loeschen_ueber_bestaetigung`.
  - `test_hinweise_liste`: fünf Karten mit `id="hinweis-…"`, «Erscheint:», fünfmal «Vorschlag, noch nicht von dir bestätigt», keine Karte für die Begrüssung.
  - `test_hinweis_unveraendert_bestaetigen`: POST mit dem Vorschlag-Text → 303 mit Anker. In der Liste steht bei diesem Hinweis «Bestätigt», die Übersicht zeigt «1 von 5 Hinweisen bestätigt».
  - `test_hinweis_leer_400`: «Bitte einen Text eingeben.», keine Zeile in `texte`.
  - `test_hinweis_unbekannt_404`: GET und POST auf `hinweise/begruessung` und `hinweise/gibts_nicht` → 404.
  - `test_datenschutz_link_im_infoblock_fuehrt_zum_hinweis`: `GET /verwaltung/inhalte/hinweise/hinweis_datenspeicherung` → 200.
  - `test_unbekannte_ids_404_impulse`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** PASS, Lint.
- [ ] **Step 6:** Commit `feat: Impulse und Hinweise erfassen (#15)`.

### Task 7: Platzhalter-Inhalte per Kommando

**Files:**
- Create: `tests/platzhalter/inhalte.json`
- Modify: `app/kommandos.py`, `app/inhalte.py`, `Makefile`, `tests/test_kommandos.py`

**Interfaces:**
- Consumes: alle `lege_*_an`, `speichere_allgemein` (Tasks 2, 4–6), `transaktion`, `Gesperrt`, `zeit.heute`, `zeit.lies_datum`.
- Produces (`app/inhalte.py`): `inhalte_vorhanden(db) -> bool` (eine Zeile in `info_abschnitte`, `runden`, `leitfragen` oder `impulse`) und `loesche_alle_inhalte(db) -> None` (die vier Tabellen leeren, in `transaktion`; `IntegrityError` → `Gesperrt`).
- Produces (`app/kommandos.py`):
  - Unterbefehl `platzhalter-laden [--projektstart YYYY-MM-DD] [--ersetzen]`
  - `_lies_passwort` nur noch in `auftraggeberin-anlegen` und `passwort-setzen`
  - `PLATZHALTER_DATEI = Path(__file__).resolve().parent.parent / "tests" / "platzhalter" / "inhalte.json"`
  - `lade_platzhalter(db, daten: dict, projektstart: date) -> dict[str, int]`: alles über die Fachfunktionen, ganz in **einer** `transaktion` (bei `--ersetzen` zuerst `loesche_alle_inhalte`). Rückgabe der Zahlen mit den Schlüsseln von `zaehle_inhalte`.
  - Ablauf: `PRODUKTION == "1"` → stderr «Platzhalter-Inhalte sind in Produktion nicht erlaubt.», Exit 1, **bevor** Datei oder Datenbank geöffnet werden. Ungültiges `--projektstart` → «Bitte das Datum als JJJJ-MM-TT angeben.», Exit 1. Fehlende Datei → Meldung, Exit 1. Inhalte vorhanden ohne `--ersetzen` → «Es gibt schon Inhalte. Mit --ersetzen werden sie vorher gelöscht.», Exit 1. `Gesperrt` → «Es gibt schon Antworten von Lehrpersonen. Die Inhalte werden nicht ersetzt.», Exit 1. `InhaltFehler` → Meldung, Exit 1. Erfolg → stdout «Platzhalter geladen: 4 Abschnitte, 4 Runden, N Fragen, 3 Leitfragen, 4 Impulse.» Standard für `projektstart` ist `zeit.heute()` (über das Modul aufrufen, damit `monkeypatch` greift).
- JSON-Format (`tests/platzhalter/inhalte.json`): `{"titel": str, "begruessung": str, "info": [{"titel", "inhalt"}], "runden": [{"titel", "fallbeispiel": str|null, "tag": int, "fragen": [{"typ", "text", "skala_min_text"?, "skala_max_text"?}]}], "leitfragen": [str], "impulse": [{"text", "tag"}]}`. Inhalt nach Spec «Platzhalter-Inhalte», Grundlage `prototyp/js/inhalte.js`: 4 Abschnitte (einer mit «- »-Liste und `**fett**`), 4 Runden mit `tag` 0/7/14/21 (Runde 4 ohne Fallbeispiel), je 3–4 Fragen mit beiden Arten, 3 Leitfragen, 4 Impulse. Keine Hinweise.
- Makefile: `platzhalter: ## Lädt erfundene Platzhalter-Inhalte in .daten/ (nie in Produktion)` → `DATEN_VERZEICHNIS=.daten uv run python -m app.kommandos platzhalter-laden`. In `help` die Spaltenbreite auf `%-12s`.

- [ ] **Step 1: Failing tests** `tests/test_kommandos.py` (Fixture `daten` aus #14):
  - `test_platzhalter_laden(daten)`: `main(["platzhalter-laden", "--projektstart", "2026-11-23"])` → 0. Die Zahlen entsprechen der JSON-Datei. Runde 1 am `2026-11-23`, Runde 4 am `2026-12-14` mit `fallbeispiel IS NULL`. `einstellungen.projektstart == "2026-11-23"`. In `texte` nur `begruessung`, kein `hinweis_…`.
  - `test_platzhalter_standard_heute(daten, monkeypatch)`: `app.zeit.heute` → `date(2026, 12, 1)` → `projektstart == "2026-12-01"`.
  - `test_platzhalter_verweigert_in_produktion(daten, monkeypatch, capsys)`: `PRODUKTION=1` → 1, Meldung, `not (daten / "reflexion.db").exists()`.
  - `test_platzhalter_verweigert_bei_vorhandenen_inhalten`: zweiter Aufruf → 1, Zahlen unverändert.
  - `test_platzhalter_ersetzen`: einen Abschnitt zusätzlich anlegen, dann `--ersetzen` → 0, Zahlen wieder wie in der Datei.
  - `test_platzhalter_ersetzen_mit_antworten_scheitert`: Antwort auf eine Frage, `--ersetzen` → 1, Meldung, alle Inhalte unverändert (Rollback).
  - `test_platzhalter_liest_kein_passwort`: `eingabe` ist ein Objekt, dessen `readline` `AssertionError` wirft → Exit 0.
  - `test_platzhalter_ungueltiges_datum`: `--projektstart 23.11.2026` → 1.
  - `test_platzhalter_datei_zeigt_formatierung`: Die Datei enthält mindestens einen Abschnitt mit `"\n- "` und `"**"`, eine Runde mit `"fallbeispiel": null` und beide Arten von Fragen.
  - `test_dockerignore_laesst_tests_draussen`: Die Zeilen von `.dockerignore` enthalten `*` und `!app/`, keine beginnt mit `!tests`.
  - Bestehende Tests aus #14 bleiben grün.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` PASS, Lint. `make platzhalter` lokal ausführen, danach `make dev`, kurz ansehen.
- [ ] **Step 5:** Commit `feat: Platzhalter-Inhalte per Kommando laden (#15)`.

### Task 8: E2E-Abläufe und Doku

**Files:**
- Modify: `tests/e2e-pilot.mjs`, `README.md`

**Interfaces:**
- Consumes: Kommando `platzhalter-laden` (Task 7), alle Seiten.
- Produces: Vor `starteApp()` läuft nach `auftraggeberin-anlegen` ein `spawnSync` von `uv run python -m app.kommandos platzhalter-laden` mit `DATEN_VERZEICHNIS=DATEN`. Bei Exit ≠ 0 wird abgebrochen. Neuer Block in `ablaeufe()` nach den Abläufen aus #14, Auftraggeberin neu angemeldet. Kein Dialog: Die Zahl der `Page.javascriptDialogOpening` in `ereignisse` bleibt gleich.

- [ ] **Step 1:** Abläufe nach Spec «Prüfung und Nachweis → E2E», Punkte 1–7, in 390 px hell. Jede besuchte Seite prüft `keinUeberlauf` und `keineFehlerSeit`, bei absichtlichen Formularfehlern mit `["status of 400"]`, bei Lehrpersonen mit `["status of 403"]`. Dazu:
  - Übersicht zusätzlich dunkel und in 1280 px. Seite einer Runde und Formular Frage zusätzlich in 1280 px.
  - Allgemein: neuer Titel mit 60 Zeichen → steht in `.seitenkopf__titel`, kein Überlauf (Review Focus 5). Begrüssung mit Leerzeile, «- »-Liste und `**fett**` speichern → in `#begruessung-anzeige` gibt es `ul li` und `strong`.
  - Infoblock: Abschnitt mit `<script>alert(1)</script>` → Text sichtbar, kein Dialog. Abschnitt mit einem Wort aus 300 × `a` → kein Überlauf (Review Focus 3). Den letzten Abschnitt «Nach oben» → `location.hash === "#abschnitt-{id}"`, das Element liegt im sichtbaren Bereich (`getBoundingClientRect().top < innerHeight`), die Reihenfolge der Titel ist getauscht.
  - Runde ohne Fallbeispiel anlegen, Frage als Text und Frage als Skala. Skala ohne Beschriftung → Text `.fehler` sichtbar am Feld. Fragen umsortieren.
  - Leitfrage und Impuls anlegen, Impuls über die Bestätigungsseite löschen.
  - Hinweise: einen Vorschlag unverändert speichern → «Bestätigt», Übersicht «1 von 5 Hinweisen bestätigt».
  - Lehrperson (Zugang aus dem Ablauf von #14) öffnet `/verwaltung/inhalte` → `h1` «Kein Zugriff».
- [ ] **Step 2:** Screenshots `10-inhalte-uebersicht`, `11-inhalte-uebersicht-dunkel`, `12-infoblock`, `13-runde`, `14-frage-fehler`, `15-hinweise`, `16-loeschen`, `17-runde-desktop`.
- [ ] **Step 3:** `make e2e` → «… bestanden, 0 fehlgeschlagen». Screenshots ansehen: 390 px, Knöpfe nicht abgeschnitten, Verschiebe-Knöpfe tippbar, dunkel lesbar.
- [ ] **Step 4:** README: «Stand»-Absatz um «Eingabemaske für alle Inhalte» ergänzen. Tabelle: Zeile `make platzhalter`, Beschreibung von `make e2e` um die Eingabemaske ergänzen. Kurzer Abschnitt «Platzhalter-Inhalte für die Entwicklung» mit Aufruf, `--ersetzen` und «verweigert mit `PRODUKTION=1`, auf fly.io nie ausführen».
- [ ] **Step 5:** `make lint test e2e` grün. Commit `test: E2E-Ablaeufe fuer die Eingabemaske, Doku (#15)`.

## Nach dem Merge (Orchestrator)

fly.io nach Spec: als Auftraggeberin anmelden, einen Abschnitt anlegen und wieder löschen, Übersicht in 390 px prüfen. Keine Platzhalter laden. Screenshots kommen in den Pull Request (Akzeptanzkriterium «auf Handy und Computer»).
