# Ansicht der Auftraggeberin und Export — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Auftraggeberin sieht pro Lehrperson den Stand, liest alle Einträge mit Filter nach Person, hört Aufnahmen an und lädt eine Tabelle für Excel sowie einen Gesamtexport (ZIP mit Tabelle und Aufnahmen) herunter.

**Architecture:** Fachlogik ohne FastAPI in drei Modulen: `app/export.py` (Tabelle), `app/export_zip.py` (Namen im ZIP, gestreamtes ZIP), `app/auswertung.py` (Zahlen der Seite). Daten nur über die Bausteine von #16 (`alle_zeilen`, `gruppiere`, `rundenstand`, `anzahl_tagebucheintraege`, `sichtbare_runden`, `aufnahme_pfad`). Routen in `app/routen/verwaltung_eintraege.py` (von #16 leer angelegt und eingebunden), Templates unter `app/templates/verwaltung/eintraege/`. Keine Migration, keine Änderung an `app/main.py`.

**Tech Stack:** Python 3.13, FastAPI 0.162, Starlette 1.10 (`Response`, `StreamingResponse`), Jinja2, sqlite3, `csv`, `zipfile`, `unicodedata`, pytest, Node-E2E über CDP.

**Spec:** `docs/superpowers/specs/2026-10-30-auswertung-export-design.md`. Vor jeder Task die genannten Abschnitte lesen; Texte der Oberfläche stehen dort. Der Schlussabschnitt «Klärungen nach dem Builder-Check (Claude)» geht dem übrigen Design vor, wo beide sich unterscheiden.

## Vorbereitung (vor Task 1, Orchestrator)

- Branch `feat/18-auswertung-export` von `main`, nachdem #16 gemergt ist.
- **Schnittstellen aus #16 prüfen** (weicht etwas ab, die betroffene Task anpassen und die Abweichung in den Klärungen des Designs nachführen):
  1. `app/eintraege.py`: `Zeile` mit den Feldern aus dem Design #16 (u. a. `quelle`, `id`, `konto_id`, `anzeigename`, `art`, `tagebuch_art`, `angeleitet`, `runde_id`, `runde_titel`, `runde_freischaltdatum`, `frage_id`, `frage`, `frage_reihenfolge`, `text`, `skalawert`, `aufnahme_id`, `aufnahme_dateiname`, `aufnahme_dauer_sekunden`, `erstellt`, `geaendert`); `alle_zeilen(db) -> list[Zeile]` ungefiltert; `Eintrag(art, konto_id, anzeigename, runde_id, eintrag_id, erstellt, geaendert, zeilen)`; `gruppiere(zeilen) -> list[Eintrag]` neueste zuerst; `Stand(beantwortet, fragen)`; `rundenstand(db, konto_id) -> dict[int, Stand]`; `anzahl_tagebucheintraege(db, konto_id) -> int`.
  2. `app/sichtbar.py`: `sichtbare_runden(db, stichtag) -> list[sqlite3.Row]` mit `id`, `anzahl_fragen`.
  3. `app/aufnahmen.py`: `aufnahme_pfad(verzeichnis, dateiname) -> Path | None` (None bei Namen ohne Muster `DATEINAME`).
  4. `app/zeit.py`: `lokal(zeitstempel) -> datetime` (Europe/Zurich), `woche`, `datum_kurz`; `app/vorlagen.py`: Filter `zeitpunkt`, `dauer`, `datum`, Global `zahl`.
  5. `app/routen/verwaltung_eintraege.py` enthält nur `router = APIRouter()` und ist in `erstelle_app` ohne `prefix` eingebunden.
  6. `app/templates/_aufnahme.html` mit Parametern `aufnahme` (nimmt eine `Zeile`, Dauer aus `aufnahme_dauer_sekunden`) und `url`, `preload="none"`.
  7. `app/templates/verwaltung/start.html` und `rahmen.html`: Kommentare `{# #18: Link Einträge #}` bzw. `{# #18: Navigation Einträge #}`, Trennzeile `{# Trennzeile zwischen #18 und #19, nicht ändern #}`, danach `{# #19: … #}`. Marken-Klassen für «Runde», «Tagebuch», «Impuls» in `lehrperson/eintraege.html` nachsehen (werden übernommen).
  8. `app/static/css/style.css`: Abschnitt `/* Pilot: Einträge und Export (#18) */` … `/* Ende #18 */`.
  9. `tests/testdaten.py`: `lege_runde_an`, `lege_impuls_an`, `lege_leitfrage_an`, `lege_antwort_an(db, frage_id, konto_id, text="Antwort", skalawert=None, aufnahme_id=None)`, `lege_eintrag_an(db, konto_id, art="frei", text="Text", impuls_id=None, leitfrage_id=None, aufnahme_id=None)`, `lege_aufnahme_an(db, konto_id, verzeichnis, dauer_sekunden=5)`. `tests/conftest.py`: Fixture `heute_ist(client)`, Fixtures `db`, `lehrperson` («Anna Beispiel»), `zweite_lehrperson` («Ben Beispiel»), `auftraggeberin`, Helfer `als_leitung`, `als_lehrperson`.
  10. `tests/e2e-pilot.mjs`: leere Funktion `ablaufEintraege()`, aufgerufen nach `ablaufAufnahmen()`; Helfer `legeZugangAn(anzeigename, benutzername) -> Promise<string>` (nachsehen, ob er eine Anmeldung als Auftraggeberin voraussetzt).
  11. `tests/test_geruest.py` (#16): Sind `test_leere_router` und `test_verwaltung_unveraendert` noch so, dass sie durch #18 brechen (`routes == []`, zweimal «folgt»), passt Task 4 sie an, ohne die Prüfung für #17 und #19 abzuschwächen (siehe Task 4).

## Global Constraints

- Keine neuen Dependencies. Nur Standardbibliothek, `fastapi`, `starlette`, `jinja2`, `markupsafe`.
- Bezeichner, Kommentare, Texte auf Deutsch, ohne ß; Umlaute in Bezeichnern ausgeschrieben. Oberfläche nach der Begriffstabelle der Spec («Tabelle (Excel)», «Gesamtexport»), Anrede «du», keine Emojis, nie «Datensatz» oder «ID».
- Kein JavaScript, kein `style=`, keine `on…=`-Attribute. Filter und Downloads sind Links (GET), kein Formular, kein CSRF.
- CSS nur zwischen `/* Pilot: Einträge und Export (#18) */` und `/* Ende #18 */`. E2E nur in `ablaufEintraege`. In `verwaltung/start.html` und `rahmen.html` nur am Platz `#18`; Kommentarzeilen und Trennzeile bleiben.
- Einträge der Lehrpersonen nie `| formatiert`, nie `| safe`; Text mit `.antwort__text` (pre-wrap, `overflow-wrap: anywhere`).
- Kein eigenes SQL in #18. Die Regel «Datum ≤ Stichtag» nur über `sichtbare_runden`. Datum nur über `Depends(hole_heute)`, Zeitstempel nur über `app/zeit.py`.
- Kein Export in eine Datei auf dem Server, keine Logs mit Namen, Pfaden oder Inhalten.
- Keine Migration, keine Änderung an `app/main.py`, `app/vorlagen.py`, `app/eintraege.py`, `app/aufnahmen.py`, `tests/conftest.py`, `tests/testdaten.py`.
- Repo öffentlich: Testdaten erfunden und neutral.
- Tests, die Datum, Woche, «zuletzt» oder die Reihenfolge prüfen, setzen **alle** Zeitpunkte über `setze_zeit`; sonst trägt die Datenbank die echte Uhrzeit ein, und der Test hängt vom Tag ab, an dem er läuft.
- Commits: Präfix `feat:`/`test:`/`docs:`/`fix:`, `(#18)` am Ende der ersten Zeile, Umlaute in der Commit-Zeile ausgeschrieben, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy9PjCyPCUAHE1BBLBG`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber.

## Review Focus

1. **Antwort und Tagebucheintrag mit gleichem Zeitpunkt:** Die Sortierung der Tabelle vergleicht `None` nie mit Text; der Export liefert 200, nicht 500. (Task 1 `test_exportzeilen_gleicher_zeitpunkt_gemischt`)
2. **Aufnahme fehlt, hat einen Namen ohne Muster oder verschwindet während des Downloads:** Das ZIP bleibt gültig, die Tabelle darin sagt «Datei fehlt», nie ein Name ohne Datei. (Task 2 `test_zip_strom_fehlende_datei`, `test_zip_dateien_name_ohne_muster`, Task 6 `test_gesamtexport_datei_geloescht`)
3. **Feindlicher oder ungewöhnlicher Anzeigename** (`../../x`, `=HYPERLINK(…)`, `<script>`, «Zoë Müller», 60 Zeichen ohne Leerzeichen): ZIP-Namen nur aus `[a-z0-9_.-]`, Zelle mit `'`, HTML escapt, Personen-Karte in 390 px ohne Überlauf. (Task 1 `test_zelle_formelzeichen`, Task 2 `test_name_im_zip_feindlich`, Task 4 `test_uebersicht_escapt_namen`, Task 7 E2E)
4. **Mitternacht in Zürich:** Datum und Woche richten sich nach Zürcher Zeit, nicht nach UTC (Sonntag 23:30 UTC = Montag 00:30, neue Woche). (Task 1 `test_exportzeilen_zeitzone`)
5. **Leere Datenbank:** Seite, Tabelle und ZIP funktionieren ohne Zugänge und ohne Einträge. (Task 4 `test_uebersicht_ohne_zugaenge`, Task 6 `test_downloads_ohne_eintraege`)

---

### Task 1: Tabelle (`app/export.py`)

Spec: «Tabelle (CSV)» (Spalten, Reihenfolge, Format, Formel-Injection), Klärungen «Tabelle».

**Files:**
- Create: `app/export.py`, `tests/test_export.py`, `tests/auswertung_daten.py`

**Interfaces:**
- Consumes: `app.eintraege.Zeile`, `app.zeit.lokal`, `app.zeit.woche`.
- Produces (`app/export.py`):
  - `SPALTEN = ("Lehrperson", "Woche", "Datum", "Geändert", "Angeleitet oder freiwillig", "Art", "Runde", "Frage", "Antwort", "Skalawert", "Aufnahme")`
  - `ART_TEXT = {"runde": "Runde", "tagebuch": "Tagebuch", "impuls": "Impuls"}`
  - `zelle(wert: str | int | None) -> str`: `None` → `""`, `int` → `str`, `\r\n` und `\r` → `\n`, dann `"'"` davor, wenn der Wert mit `=`, `+`, `-`, `@`, `\t` oder `\r` beginnt (die Prüfung auf `\r` läuft vor der Normalisierung).
  - `woche_von(zeitstempel: str, projektstart: date | None) -> int | None` = `zeit.woche(zeit.lokal(zeitstempel).date(), projektstart)`, `None` ohne Projektstart.
  - `@dataclass(frozen=True) class Exportzeile: zeile: Zeile; woche: int | None; erstellt: datetime; geaendert: datetime | None` (beide Zürich; `geaendert` `None`, wenn `zeile.geaendert == zeile.erstellt`).
  - `exportzeilen(zeilen: list[Zeile], projektstart: date | None) -> list[Exportzeile]`, sortiert nach `(woche or 0, anzeigename.casefold(), konto_id, erstellt, runde_freischaltdatum or "", frage_reihenfolge or 0, quelle, id)`.
  - `als_csv(exportzeilen: list[Exportzeile], aufnahme: Callable[[Zeile], str]) -> bytes`: `csv.writer(puffer, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\r\n")`, Kopf `SPALTEN`, jede Zelle über `zelle`, Datum `%d.%m.%Y %H:%M`, «Angeleitet oder freiwillig» = `"angeleitet"`/`"freiwillig"`, Spalte «Aufnahme» = `aufnahme(zeile)`; Ergebnis `("﻿" + text).encode("utf-8")`.
- Produces (`tests/auswertung_daten.py`, Testhelfer für Tasks 1–6): `zeile(**abweichungen) -> Zeile` (Antwort von «Anna Beispiel», `konto_id=1`, Runde «Runde Eins» vom `2026-11-23`, Freitext-Frage «Frage A», Reihenfolge 1, Text «Antwort», ohne Aufnahme, `erstellt = geaendert = "2026-11-24T08:00:00Z"`); `setze_zeit(db, tabelle: str, zeilen_id: int, erstellt: str, geaendert: str | None = None)` (`geaendert` Standard = `erstellt`); `setze_projektstart(db, tag: str)`.

- [ ] **Step 1: Failing tests** `tests/test_export.py`:
  - `test_zelle_formelzeichen` (parametrisiert): `"=SUMME(A1)"`, `"+41 79"`, `"-1"`, `"- Punkt"`, `"@x"`, `"\tx"`, `"\rx"`, `"=HYPERLINK(\"http://x\")"` → beginnt mit `"'"`, Rest unverändert (bei `"\rx"`: `"'\nx"`).
  - `test_zelle_normal`: `"Zoë «gut»"` unverändert; `None` → `""`; `4` → `"4"`; `"a\r\nb\rc"` → `"a\nb\nc"`; `"Text = gut"` unverändert.
  - `test_woche_von`: `("2026-11-22T23:30:00Z", date(2026, 11, 23))` → `1`; `("2026-11-22T22:30:00Z", date(2026, 11, 23))` → `None`; `("2026-11-29T23:00:00Z", date(2026, 11, 23))` → `2`; Projektstart `None` → `None`.
  - `test_exportzeilen_zeitzone` (Review Focus 4): `zeile(erstellt="2026-11-22T23:30:00Z", geaendert=…)` mit erstem Tag 23.11. → `woche == 1`, `als_csv` enthält `"23.11.2026 00:30"`.
  - `test_exportzeilen_sortierung`: Woche 2 Anna, Woche 1 Ben, Woche 1 Anna, vor dem ersten Tag Ben → Reihenfolge: vor dem ersten Tag, W1 Anna, W1 Ben, W2 Anna. Ohne Projektstart: alle `woche is None`, nach Name sortiert.
  - `test_exportzeilen_gleicher_zeitpunkt_antworten`: zwei Antworten derselben Runde, gleicher Zeitpunkt, `frage_reihenfolge` 2 und 1 → Reihenfolge 1, 2.
  - `test_exportzeilen_gleicher_zeitpunkt_gemischt` (Review Focus 1): Antwort und Tagebucheintrag (`quelle="tagebuch"`, `runde_freischaltdatum=None`, `frage_reihenfolge=None`) derselben Person mit gleichem `erstellt` → keine Ausnahme, zwei Zeilen.
  - `test_als_csv_format`: beginnt mit `b"\xef\xbb\xbf"`; nach dem BOM dekodiert und mit `csv.reader(io.StringIO(…, newline=""), delimiter=";")` eingelesen: Kopf == `list(SPALTEN)`, Werte mit `"`, `;`, Umlauten und `"Zeile 1\nZeile 2"` kommen unverändert zurück; Anzahl `b"\r\n"` == Anzahl Datensätze (Umbrüche in Zellen nur `\n`); kein `"sep="` am Anfang.
  - `test_als_csv_keine_formel`: Antwort `"=1+1"`, Anzeigename `"@Anna"` → nach dem Einlesen beginnt keine Zelle mit `=`, `+`, `-`, `@`.
  - `test_als_csv_werte_pro_art`: Runde (Skala, `skalawert=4`, `frage="Frage B"`) → `"angeleitet"`, `"Runde"`, Rundentitel, `"Frage B"`, Antwort leer, `"4"`; Tagebuch frei → `"freiwillig"`, `"Tagebuch"`, Runde und Frage leer; Leitfrage → Frage = mitgespeicherter Text; Impuls → Art `"Impuls"`; gesprochen (`tagebuch_art="aufnahme"`, `text=None`, `aufnahme_id=7`) → Antwort leer, Aufnahme = Rückgabe von `aufnahme`.
  - `test_als_csv_geaendert`: unverändert → Spalte «Geändert» leer; `geaendert="2026-11-25T09:15:00Z"` → `"25.11.2026 10:15"`.
- [ ] **Step 2:** `uv run pytest tests/test_export.py -v` → FAIL (Modul fehlt).
- [ ] **Step 3:** `app/export.py` implementieren.
- [ ] **Step 4:** `uv run pytest tests/test_export.py -v` → PASS, Lint sauber.
- [ ] **Step 5:** Commit `feat: Tabelle der Eintraege fuer Excel (#18)`.

### Task 2: Gesamtexport als Strom (`app/export_zip.py`)

Spec: «Gesamtexport (ZIP)» (Inhalt, Grösse und Speicher, Ablauf und Konsistenz), Klärungen «Gesamtexport».

**Files:**
- Create: `app/export_zip.py`, `tests/test_export_zip.py`

**Interfaces:**
- Consumes: Task 1 (`Exportzeile`, `exportzeilen`), `app.aufnahmen.aufnahme_pfad`.
- Produces (`app/export_zip.py`):
  - `STUECK = 64 * 1024`, `TABELLE_IM_ZIP = "eintraege.csv"`, `DATEI_FEHLT = "Datei fehlt"`.
  - `person_ascii(anzeigename: str, konto_id: int) -> str`: ä/ö/ü/Ä/Ö/Ü/ß → ae/oe/ue/Ae/Oe/Ue/ss, dann NFKD ohne Kombinationszeichen, klein, `[^a-z0-9]+` → `-`, `-` am Rand weg, höchstens 30 Zeichen (danach nochmals `-` am Rand weg); leer → `f"lehrperson-{konto_id}"`.
  - `name_im_zip(e: Exportzeile, endung: str) -> str`: `"aufnahmen/" + "_".join(teile) + endung`, Teile: Person, `f"W{woche:02d}"` (nur mit Woche), `f"{erstellt:%Y-%m-%d}"`, `f"{erstellt:%H%M}"`, `e.zeile.art`, `str(e.zeile.aufnahme_id)`.
  - `@dataclass(frozen=True) class ZipDatei: aufnahme_id: int; quelle: Path; name: str; zeitpunkt: datetime`.
  - `zip_dateien(exportzeilen: list[Exportzeile], verzeichnis: Path) -> list[ZipDatei]`: nur Zeilen mit `aufnahme_id`; Pfad über `aufnahme_pfad(verzeichnis, zeile.aufnahme_dateiname)`, bei `None` keine `ZipDatei`; Endung `quelle.suffix`; kein Dateizugriff.
  - `zip_strom(dateien: list[ZipDatei], tabelle: Callable[[dict[int, str]], bytes]) -> Iterator[bytes]`: `zipfile.ZipFile` auf ein Objekt mit nur `write`/`flush`; pro Datei `open(quelle, "rb")` (`FileNotFoundError` → überspringen), `ZipInfo(name, zeitpunkt.timetuple()[:6])`, `compress_type = ZIP_STORED`, `file_size = os.fstat(…).st_size`, `external_attr = (stat.S_IFREG | 0o644) << 16`, Kopieren in Stücken von `STUECK` über `zf.open(info, "w")`, nach jedem Stück die angefallenen Bytes ausgeben; danach `TABELLE_IM_ZIP` = `tabelle({aufnahme_id: name})` mit `ZIP_DEFLATED`, ebenfalls in Stücken; zuletzt das zentrale Verzeichnis. Anderer `OSError` → `logging.getLogger(__name__).warning("Gesamtexport abgebrochen")`, weiterwerfen.

- [ ] **Step 1: Failing tests** `tests/test_export_zip.py` (Exportzeilen über `exportzeilen([zeile(…)], date(2026, 11, 23))`):
  - `test_person_ascii`: `"Zoë Müller"` → `"zoe-mueller"`; `"ÄRGER Straße"` → `"aerger-strasse"`; `"../../x"` → `"x"`; `"***"` mit `konto_id=7` → `"lehrperson-7"`; `"a" * 60` → Länge 30.
  - `test_name_im_zip`: Antwort von «Anna Beispiel», `erstellt="2026-11-30T17:40:00Z"`, `aufnahme_id=17`, Endung `.webm` → `"aufnahmen/anna-beispiel_W02_2026-11-30_1840_runde_17.webm"`; ohne Projektstart → `"aufnahmen/anna-beispiel_2026-11-30_1840_runde_17.webm"`.
  - `test_name_im_zip_feindlich` (Review Focus 3, parametrisiert `"../../x"`, `"=HYPERLINK(1)"`, `"<script>"`, `"a/b\\c"`, `"x" * 60`): `re.fullmatch(r"aufnahmen/[a-z0-9_.-]+", name)`, genau ein `/`, kein `..`.
  - `test_zip_dateien(tmp_path)`: Zeile ohne Aufnahme → nicht enthalten; Zeile mit `aufnahme_dateiname = "0" * 32 + ".m4a"` → `quelle == tmp_path / ("0" * 32 + ".m4a")`, Name endet auf `.m4a`, `zeitpunkt` in Zürich.
  - `test_zip_dateien_name_ohne_muster` (Review Focus 2): `aufnahme_dateiname="../x.webm"` → keine `ZipDatei`.
  - `test_zip_strom(tmp_path)`: zwei Dateien (3 MB Zufallsdaten und 10 Bytes) und eine `ZipDatei` ohne Datei; `tabelle` = Funktion, die ihr Argument merkt und `b"kopf\r\n"` liefert. `b"".join(strom)` → `zipfile.ZipFile(BytesIO(…)).testzip() is None`; `namelist()` == die zwei Namen, dann `"eintraege.csv"` (letzte); Inhalte bytegleich; gemerktes Argument enthält nur die zwei vorhandenen `aufnahme_id`s.
  - `test_zip_strom_fehlende_datei` (Review Focus 2): nur eine fehlende Datei → ZIP gültig, enthält nur `eintraege.csv`, Argument `{}`.
  - `test_zip_strom_stueckgroesse(tmp_path)`: 3 MB-Datei → `max(len(s) for s in strom) <= STUECK + 1024`.
  - `test_zip_strom_metadaten(tmp_path)`: Aufnahmen `compress_type == ZIP_STORED`, Tabelle `ZIP_DEFLATED`; `date_time == (2026, 11, 30, 18, 40, 0)` für `erstellt="2026-11-30T17:40:00Z"`; `external_attr >> 16 == stat.S_IFREG | 0o644`.
  - `test_zip_strom_lesefehler(tmp_path, monkeypatch, caplog)`: `open` für die Quelle wirft `PermissionError` → `pytest.raises(PermissionError)` beim Durchlaufen; Log enthält «Gesamtexport abgebrochen», nicht den Dateinamen.
- [ ] **Step 2:** `uv run pytest tests/test_export_zip.py -v` → FAIL.
- [ ] **Step 3:** `app/export_zip.py` implementieren.
- [ ] **Step 4:** PASS, Lint sauber.
- [ ] **Step 5:** Commit `feat: Gesamtexport als gestreamtes ZIP (#18)`.

### Task 3: Zahlen der Seite (`app/auswertung.py`)

Spec: «Seite ‹Einträge›» (Punkte 3 und 4), «Was ‹Runden beantwortet› heisst», Klärungen «Seite ‹Einträge›».

**Files:**
- Create: `app/auswertung.py`, `tests/test_auswertung.py`

**Interfaces:**
- Consumes: `konten.lehrpersonen`, `eintraege.rundenstand`, `eintraege.anzahl_tagebucheintraege`, `eintraege.Eintrag`, `sichtbar.sichtbare_runden`, `aufnahmen.aufnahme_pfad`, Task 1 (`woche_von`).
- Produces (`app/auswertung.py`):
  - `@dataclass(frozen=True) class Personenkarte: konto_id: int; anzeigename: str; runden: int; beantwortet: int; angefangen: int; tagebucheintraege: int; zuletzt: date | None; stand: dict[int, Stand]` (`runden` = sichtbare Runden mit Fragen; `stand` = `rundenstand` der Person, für «3 von 4 Fragen beantwortet» in der Liste).
  - `personenkarten(db, heute: date, zeilen: list[Zeile]) -> list[Personenkarte]`: Reihenfolge wie `lehrpersonen(db)`; `zuletzt` = `zeit.lokal(max(geaendert)).date()` der Zeilen dieser Person.
  - `@dataclass(frozen=True) class Karte: eintrag: Eintrag; woche: int | None` und `karten(eintraege: list[Eintrag], projektstart: date | None) -> list[Karte]` (Woche aus `eintrag.erstellt` über `woche_von`).
  - `@dataclass(frozen=True) class Exportstand: zeilen: int; aufnahmen: int; bytes: int` und `exportstand(zeilen: list[Zeile], verzeichnis: Path) -> Exportstand` (`aufnahmen` = Zeilen mit `aufnahme_id`; `bytes` = Summe `stat().st_size` der vorhandenen Dateien über `aufnahme_pfad`, fehlende und `None` zählen 0).
  - `groesse_text(anzahl_bytes: int) -> str`: `< 1_000_000` → `"weniger als 1 MB"`, sonst `f"etwa {round(anzahl_bytes / 1_000_000)} MB"`.

- [ ] **Step 1: Failing tests** `tests/test_auswertung.py` (Daten über `testdaten`, Zeilen über `alle_zeilen(db)`):
  - `test_personenkarten_runden(db, lehrperson)`: Runde A (23.11., 2 Fragen, beide beantwortet), Runde B (23.11., 2 Fragen, eine beantwortet), Runde C (23.11., ohne Fragen), Runde D (07.12., 1 Frage, beantwortet); `heute = date(2026, 11, 24)` → `runden == 2`, `beantwortet == 1`, `angefangen == 1`.
  - `test_personenkarten_keine_runde_offen(db, lehrperson)`: nur Runde C sichtbar → `runden == 0`.
  - `test_personenkarten_tagebuch_und_zuletzt(db, lehrperson, zweite_lehrperson, einstellungen)`: Anna mit Einträgen frei, impuls, aufnahme, alle per `setze_zeit` am 23.11., einer mit `setze_zeit(…, "2026-11-23T08:00:00Z", "2026-11-24T23:30:00Z")` → `tagebucheintraege == 3`, `zuletzt == date(2026, 11, 25)`; Ben → `tagebucheintraege == 0`, `zuletzt is None`; Reihenfolge Anna, Ben.
  - `test_karten_woche`: zwei `Eintrag`e (über `gruppiere([zeile(…)])`) am 24.11. und 01.12., Projektstart 23.11. → Wochen 1 und 2; ohne Projektstart `None`.
  - `test_exportstand(tmp_path)`: drei Zeilen, zwei mit Aufnahme (eine Datei 1500 Bytes vorhanden, eine fehlt), eine ohne → `Exportstand(3, 2, 1500)`; Name ohne Muster zählt 0 Bytes.
  - `test_groesse_text`: `0` → `"weniger als 1 MB"`, `999_999` → `"weniger als 1 MB"`, `1_000_000` → `"etwa 1 MB"`, `18_400_000` → `"etwa 18 MB"`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS, Lint.
- [ ] **Step 5:** Commit `feat: Zahlen fuer die Ansicht der Eintraege (#18)`.

### Task 4: Seite «Einträge»: Personen, Export-Karte, Filter, Links in der Verwaltung

Spec: «Adressen», «Seite ‹Einträge›» (Punkte 1–5), «Sicherheit und Datenschutz» (Zugriff), Klärungen «Seite ‹Einträge›».

**Files:**
- Create: `app/templates/verwaltung/eintraege/uebersicht.html`, `tests/test_verwaltung_eintraege.py`
- Modify: `app/routen/verwaltung_eintraege.py`, `app/templates/verwaltung/start.html` (nur Platz `#18`), `app/templates/verwaltung/rahmen.html` (nur Platz `#18`), `app/static/css/style.css` (nur Abschnitt #18), `tests/test_geruest.py` (nur falls Vorbereitung Punkt 11 zutrifft)

**Interfaces:**
- Consumes: Task 3 (`personenkarten`, `karten`, `exportstand`, `groesse_text`), `alle_zeilen`, `gruppiere`, `lies_projektstart`, `zeit.woche`, `hole_heute`, `hole_db`, `braucht_auftraggeberin`.
- Produces (`app/routen/verwaltung_eintraege.py`): `router = APIRouter(prefix="/verwaltung/eintraege", dependencies=[Depends(braucht_auftraggeberin)])`, `DB`, `HEUTE = Annotated[date, Depends(hole_heute)]`, `LehrpersonFilter = Annotated[int | None, Query(ge=1, le=2**63 - 1)]`, Route `GET ""` (`uebersicht(request, db, heute, lehrperson: LehrpersonFilter = None)`); unbekannte bzw. nicht als Lehrperson gelistete `id` → `HTTPException(404)`. Kontext: `woche` (Seite), `personen`, `gewaehlt` (`Personenkarte | None`), `karten`, `staende` (`{konto_id: personenkarte.stand}`), `stand` (`Exportstand`), `groesse`. Task 5 rendert `karten`, Task 6 ergänzt die Download-Routen.
- Template: `uebersicht.html` erweitert `verwaltung/rahmen.html`; Personen-Karten als Links `?lehrperson={id}#eintraege` mit `ist-aktiv` und `aria-current="page"`; Export-Karte `id="export"` mit Links `/verwaltung/eintraege/tabelle.csv` und `/verwaltung/eintraege/gesamtexport.zip`, Sätzen und `hinweis` aus der Spec plus dem Satz zu den Links aus den Klärungen; `h2 id="eintraege"`; `nav.chips` mit `aria-label="Nach Lehrperson filtern"`, «Alle» → `/verwaltung/eintraege#eintraege`. Liste vorerst nur «Noch keine Einträge.» bzw. ein `{% for karte in karten %}`-Gerüst ohne Inhalt (Task 5).
- `start.html`: den `<li class="karte karte--ruhend">`-Block «Einträge» unter `{# #18: Link Einträge #}` durch `<li><a class="karte karte--link" href="/verwaltung/eintraege">` mit «Einträge» und gedämpftem Satz «Einträge lesen, Aufnahmen anhören, Tabelle und Gesamtexport herunterladen.» ersetzen. `rahmen.html`: Zeile `<a href="/verwaltung/eintraege">Einträge</a>` direkt unter `{# #18: Navigation Einträge #}`. Kommentare und Trennzeile bleiben.
- CSS (Abschnitt #18): `.verwaltungsnavigation { flex-wrap: wrap; }`, `.karte--person strong { overflow-wrap: anywhere; }`, Abstand der Export-Knöpfe.
- `tests/test_geruest.py` (nur falls nötig): `test_leere_router` prüft nur noch `isinstance(modul.router, APIRouter)`; `test_verwaltung_unveraendert` prüft nur noch, dass «Einträge» und «Vorschau» vorkommen. Im Pull Request erwähnen (Datei von #16, gleiche Änderung brauchen #17 und #19).

- [ ] **Step 1: Failing tests** `tests/test_verwaltung_eintraege.py` (`als_leitung`, `heute_ist(date(2026, 11, 24))`, `setze_projektstart(db, "2026-11-23")`):
  - `test_uebersicht_personen(client, auftraggeberin, lehrperson, zweite_lehrperson, db, heute_ist, einstellungen)`: Daten wie `test_personenkarten_runden` und drei Tagebucheinträge (frei, impuls, aufnahme) für Anna, alle Zeitpunkte am 23.11., einer mit `geaendert` am 24.11. 18:00 UTC → 200; «Woche 1»; `<h1>Einträge</h1>`; «Runden 1 von 2»; «1 angefangen»; «3 Tagebucheinträge»; «zuletzt Di 24.11.»; Ben: «Runden 0 von 2», «noch nichts»; Link auf `?lehrperson={anna}#eintraege` (relativ oder absolut, Test prüft `lehrperson={anna}#eintraege`).
  - `test_uebersicht_einzahl(…)`: ein Tagebucheintrag → «1 Tagebucheintrag».
  - `test_uebersicht_ohne_runde(…)`: keine sichtbare Runde → «Noch keine Runde offen».
  - `test_uebersicht_ohne_zugaenge(client, auftraggeberin)` (Review Focus 5): «Noch keine Zugänge.», Link `/verwaltung/zugaenge`, «Jetzt: 0 Zeilen, keine Aufnahmen.», beide Download-Links, kein `class="chips"`; ohne Projektstart kein «Woche».
  - `test_export_karte(…, einstellungen)`: zwei Antworten, eine davon mit Aufnahme (`testdaten.lege_aufnahme_an`) → «Jetzt: 2 Zeilen, 1 Aufnahme (weniger als 1 MB).»; Knopf-Texte «Tabelle herunterladen (Excel)», «Gesamtexport herunterladen (ZIP)»; Hinweis enthält «nicht über private Cloud-Dienste teilen».
  - `test_filter(…)`: `?lehrperson={anna}` → Personen-Karte und Chip von Anna mit `ist-aktiv` und `aria-current="page"`, «Einträge von Anna Beispiel»; ohne Filter Chip «Alle» aktiv.
  - `test_filter_404` (parametrisiert `"abc"`, `"0"`, `"-1"`, `"99999999999999999999"`, `""`, `"999"`, id der Auftraggeberin): `GET /verwaltung/eintraege?lehrperson=…` → 404 mit «Nicht gefunden».
  - `test_uebersicht_escapt_namen(…)` (Review Focus 3): Zugang mit Anzeigename `<b>X</b>` (per `UPDATE konten`) → `&lt;b&gt;X&lt;/b&gt;` in der Seite, kein `<b>X`.
  - `test_zugriff(client, lehrperson)`: `GET /verwaltung/eintraege` ohne Anmeldung → 303 auf `/`; als Lehrperson → 403 (Downloads: Task 6).
  - `test_verwaltung_links(client, auftraggeberin)`: `/verwaltung` enthält `href="/verwaltung/eintraege"` in Karte und Navigation, «Vorschau» weiterhin; die Template-Dateien enthalten `{# #18:`, Trennzeile, `{# #19:` in dieser Reihenfolge.
  - `test_kein_inline(…)`: Seite enthält weder `style=` noch `<script` noch ` on` + Buchstaben + `=` in einem Tag.
- [ ] **Step 2:** `uv run pytest tests/test_verwaltung_eintraege.py -v` → FAIL.
- [ ] **Step 3:** implementieren (Router, Template, Plätze, CSS; ggf. `tests/test_geruest.py`).
- [ ] **Step 4:** `uv run pytest -v` → PASS (inklusive Routen-Inventar und `tests/test_geruest.py`), Lint. `make dev`, Seite in 390 px ansehen.
- [ ] **Step 5:** Commit `feat: Seite Eintraege mit Uebersicht pro Lehrperson und Filter (#18)`.

### Task 5: Liste der Einträge

Spec: «Seite ‹Einträge›» (Punkt 6), «Karte eines Eintrags», Klärungen (Runden-Karte «zuletzt gespeichert», Einbindung `_aufnahme.html`, Bezeichnungen).

**Files:**
- Create: `app/templates/verwaltung/eintraege/_eintrag.html`, `tests/test_verwaltung_eintraege_liste.py`
- Modify: `app/templates/verwaltung/eintraege/uebersicht.html`, `app/static/css/style.css` (nur Abschnitt #18)

**Interfaces:**
- Consumes: Task 4 (Kontext `karten`, `gewaehlt`, `personen` mit `stand`), `_aufnahme.html`, Filter `zeitpunkt`, `dauer`.
- Produces: `_eintrag.html` bekommt `karte` (`Karte`), `stand` (bei Runde `staende[konto_id][runde_id]`, sonst `None`) und `mit_name` (bool, falsch im gefilterten Zustand); `article class="karte karte--eintrag"`. Kopf: Marke, gedämpft `[Anzeigename · ]Woche N · {{ eintrag.erstellt | zeitpunkt }}`, dazu bei Runde «· zuletzt gespeichert …», bei Tagebuch «· geändert …», jeweils nur wenn `geaendert != erstellt`. Inhalt nach Spec; Aufnahme über `{% with aufnahme=zeile, url="/verwaltung/aufnahmen/" ~ zeile.aufnahme_id %}{% include "_aufnahme.html" %}{% endwith %}`.

- [ ] **Step 1: Failing tests** `tests/test_verwaltung_eintraege_liste.py` (`als_leitung`, `heute_ist(date(2026, 12, 2))`, erster Tag 23.11.):
  - `test_runde_eine_karte(…)`: Runde «Runde Eins» mit Freitext «Frage A» (Reihenfolge 1) und Skala «Frage B» (2); Antworten «Text A» und `4`, Skala zuerst angelegt → eine Karte mit «Runde Eins», «2 von 2 Fragen beantwortet»; «Frage A» vor «Text A» vor «Frage B» vor «4 von 5» im HTML.
  - `test_kopfzeile(…)`: Antwort `erstellt` 2026-11-30T17:40:00Z → «Anna Beispiel · Woche 2 · Mo 30.11.2026, 18:40»; zweite Antwort derselben Runde am 01.12. 06:15 UTC → «zuletzt gespeichert Di 01.12.2026, 07:15», kein «geändert»; Tagebucheintrag mit geändertem `geaendert` → «geändert …»; unverändert → weder «geändert» noch «zuletzt gespeichert».
  - `test_ohne_woche(…)`: ohne Projektstart → kein «Woche» in der Kopfzeile.
  - `test_tagebuch_arten(…)`: frei, Leitfrage, Impuls → «Freier Eintrag», «Zur Leitfrage» mit dem Leitfragetext, «Zum Impuls» mit Marke «Impuls»; nach `UPDATE impulse SET text = 'Neu'` steht weiterhin der alte Impulstext.
  - `test_aufnahme(…, einstellungen)`: Tagebuch `art="aufnahme"` (Dauer 5, ohne Text) → «Gesprochener Eintrag», `<audio`, `preload="none"`, `src="/verwaltung/aufnahmen/{aid}"`, «5 Sek.»; Antwort nur mit Aufnahme → `<audio` in der Runden-Karte, kein leerer `.antwort__text`.
  - `test_escapt_unformatiert(…)`: Text `"<script>x</script> **fett**\nZeile 2"` → `&lt;script&gt;`, `**fett**`, kein `<strong>`, `"\nZeile 2"` im HTML innerhalb von `antwort__text`.
  - `test_nicht_freigeschaltete_runde(…)`: Runde mit Antwort, danach `UPDATE runden SET freischaltdatum = '2026-12-31'` → Antwort erscheint in der Liste.
  - `test_filter_liste(…, zweite_lehrperson)`: Texte «TextAnna», «TextBen» → `?lehrperson={anna}` enthält «TextAnna», nicht «TextBen», und in den Kopfzeilen kein «Anna Beispiel ·»; ohne Filter beide.
  - `test_reihenfolge(…)`: Einträge am 24.11., 30.11., 01.12. → neueste zuerst.
  - `test_leer(…)`: Zugänge ohne Einträge → «Noch keine Einträge.»
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS, Lint. Seite in 390 px mit einem langen Text ansehen.
- [ ] **Step 5:** Commit `feat: Eintraege lesen und Aufnahmen anhoeren (#18)`.

### Task 6: Downloads Tabelle und Gesamtexport

Spec: «Tabelle (CSV)» (Datei), «Gesamtexport (ZIP)» (Ablauf und Konsistenz), «`app/routen/verwaltung_eintraege.py`», Klärungen «Gesamtexport».

**Files:**
- Create: `tests/test_verwaltung_export.py`
- Modify: `app/routen/verwaltung_eintraege.py`

**Interfaces:**
- Consumes: Tasks 1–2 (`exportzeilen`, `als_csv`, `zip_dateien`, `zip_strom`, `DATEI_FEHLT`), `alle_zeilen`, `lies_projektstart`.
- Produces: `GET "/tabelle.csv"` → `Response(als_csv(…), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="reflexion-tabelle-{heute.isoformat()}.csv"'})`, Spalte «Aufnahme» = `f"{str(request.base_url).rstrip('/')}/verwaltung/aufnahmen/{z.aufnahme_id}"` bzw. `""`. `GET "/gesamtexport.zip"` → alles lesen, dann `StreamingResponse(zip_strom(dateien, lambda enthalten: als_csv(ez, …)), media_type="application/zip", headers={…"reflexion-gesamtexport-….zip"})`; Spalte «Aufnahme» = `enthalten.get(id, DATEI_FEHLT)` bzw. `""`. Der Generator bekommt keine Datenbankverbindung.

- [ ] **Step 1: Failing tests** `tests/test_verwaltung_export.py` (`als_leitung`, `heute_ist(date(2026, 12, 18))`, erster Tag 23.11.; Daten: Runde mit 2 Antworten, eine davon mit Aufnahme; Tagebuch frei mit `"Zeile 1\r\nZeile 2 äöü"`; Tagebuch `aufnahme`):
  - `test_tabelle_kopfzeilen(…)`: 200, `content-type == "text/csv; charset=utf-8"`, `content-disposition == 'attachment; filename="reflexion-tabelle-2026-12-18.csv"'`, `cache-control == "no-store"`.
  - `test_tabelle_inhalt(…)`: Datensätze == Antworten + Tagebucheinträge + 1 (= 5); Spalte «Aufnahme» der beiden Zeilen mit Aufnahme == `f"http://testserver/verwaltung/aufnahmen/{aid}"`, sonst leer; Text mit `"Zeile 1\nZeile 2 äöü"` kommt beim Einlesen unverändert zurück.
  - `test_gesamtexport_kopfzeilen(…)`: 200, `content-type == "application/zip"`, `content-disposition` mit `reflexion-gesamtexport-2026-12-18.zip`, `cache-control == "no-store"`.
  - `test_gesamtexport_inhalt(…)`: ZIP öffnen, `testzip() is None`; zwei Dateien unter `aufnahmen/`, bytegleich zu den Testdateien; `eintraege.csv` ist die letzte Datei, ihre Spalte «Aufnahme» nennt genau diese zwei Namen; Datensätze wie in der Tabelle.
  - `test_gesamtexport_datei_geloescht(…)` (Review Focus 2): eine Testdatei vorher von Hand gelöscht → 200, ZIP gültig, eine Datei unter `aufnahmen/`, in `eintraege.csv` einmal «Datei fehlt».
  - `test_downloads_ohne_eintraege(client, auftraggeberin)` (Review Focus 5): Tabelle = BOM + Kopfzeile + `\r\n`; ZIP enthält nur `eintraege.csv`.
  - `test_downloads_zugriff(client, lehrperson)`: ohne Anmeldung beide → 303 auf `/`; als Lehrperson beide → 403.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` PASS (Routen-Inventar deckt beide Adressen ab), Lint.
- [ ] **Step 5:** Commit `feat: Tabelle und Gesamtexport herunterladen (#18)`.

### Task 7: E2E-Ablauf, Doku, Belege

Spec: «Prüfung und Nachweis» (E2E, Von Hand), Klärungen «Prüfung».

**Files:**
- Modify: `tests/e2e-pilot.mjs` (nur Funktion `ablaufEintraege`), `README.md` («Stand»)

**Interfaces:**
- Consumes: `legeZugangAn`, `PW_AUFTRAGGEBERIN`, Helfer des E2E-Skripts; lokale Hilfsfunktion `anmeldenAls(benutzername, passwort)` innerhalb von `ablaufEintraege`.

- [ ] **Step 1:** `ablaufEintraege()` in 390 px hell, auf jeder Seite `keinUeberlauf` und `keineFehlerSeit`:
  1. `cdp("Network.clearBrowserCookies")`; als Auftraggeberin anmelden; Zugang «Ida Überlangernachnamebeispielperson» (`lp.e2e.export`) über `legeZugangAn`; abmelden; als Ida anmelden, freien Tagebucheintrag `"Erste Zeile\nZweite Zeile"` speichern; abmelden; als Auftraggeberin anmelden.
  2. `/verwaltung`: Karte «Einträge» ist ein Link, Navigation enthält «Einträge»; `keinUeberlauf` (Navigation mit allen Links).
  3. Karte «Einträge» tippen → `pfad() === "/verwaltung/eintraege"`; Karte von Ida zeigt «1 Tagebucheintrag»; Karte tippen → Chip von Ida mit `aria-current`, Liste ohne Einträge anderer Personen; «Alle» → wieder alle.
  4. Karte von Idas Eintrag: `getComputedStyle(el).whiteSpace === "pre-wrap"` und `innerText` enthält einen Zeilenumbruch zwischen «Erste Zeile» und «Zweite Zeile».
  5. Im Seitenkontext `fetch` auf beide Downloads: Status 200; erste drei Bytes der Tabelle `EF BB BF`; ZIP beginnt mit `PK`.
  6. Gibt es ein `audio` auf der Seite: `fetch(audio.src)` → 200, `content-type` beginnt mit `audio/`.
  7. Dunkel (390 px) und 1280 px: Seite `keinUeberlauf`.
- [ ] **Step 2:** Screenshots `40-eintraege`, `41-eintraege-dunkel`, `42-eintraege-desktop`, `43-eintraege-gefiltert`, `44-export-karte`.
- [ ] **Step 3:** `make e2e` → «… bestanden, 0 fehlgeschlagen». Screenshots ansehen: Personen-Karten zweispaltig, langer Name bricht um, Export-Knöpfe tippbar, dunkel lesbar.
- [ ] **Step 4:** README: «Stand» um «Ansicht der Auftraggeberin: Einträge lesen, Tabelle und Gesamtexport» ergänzen.
- [ ] **Step 5 (von Hand, Belege in den Pull Request, nur Platzhalter-Inhalte):** Tabelle aus der lokalen App mit Testeinträgen (Umlaute, «», mehrzeilig, `=1+1`, `- Punkt`) per Doppelklick in Microsoft Excel öffnen, Screenshot (**Akzeptanzkriterium Excel**). ZIP im Finder entpacken, Tabelle öffnen, Namen mit dem Ordner vergleichen, `unzip -t`.
- [ ] **Step 6:** `make lint test e2e` grün. Commit `test: E2E-Ablauf Eintraege und Export, Doku (#18)`.

## Nach dem Merge (Orchestrator)

- fly.io nach dem Deploy (Testkonten, keine Platzhalter): Seite in 390 px öffnen, Gesamtexport laden und `unzip -t`; Link aus der Tabelle beginnt mit `https://reflexionsinstrument.fly.dev/verwaltung/aufnahmen/` (prüft `--proxy-headers`), abgemeldet → Login, angemeldet → Wiedergabe (**Akzeptanzkriterium Links**, braucht #17).
- Ist #17 schon auf `main`: Test «Link aus der Tabelle spielt nach Anmeldung ab» ergänzen (Spec «Prüfung und Nachweis», letzter pytest-Punkt): Link aus `tabelle.csv` als Auftraggeberin → 200 mit dem Inhalt der Testdatei; ohne Anmeldung → 303. Sonst ergänzt ihn #17 beim eigenen Merge.
- Offene Frage an die Auftraggeberin (Windows oder Mac) in die Testanleitung (#9) übernehmen.
