# Sprachaufnahmen — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lehrpersonen sprechen Tagebucheinträge im Browser ein (aufnehmen, anhören, neu aufnehmen, speichern), die Auftraggeberin hört sie an, nur Berechtigte erreichen eine Aufnahme; als Soll lassen sich Antworten auf Freitext-Fragen einsprechen, ersetzen und löschen.

**Architecture:** Datei- und Datenlogik ohne FastAPI in `app/aufnahmen.py` (erweitert den Grundstock von #16): Format aus den ersten Bytes, zufälliger Name, Schreiben über `.teil` und `os.replace`, Aufnahme-Zeile und Eintrag bzw. Antwort in einer Transaktion, Waisen aufräumen. Routen in `app/routen/aufnahmen.py` mit zwei Unter-Routern (`/lehrperson`, `/verwaltung`); die Upload-Routen deklarieren keine Formular-Parameter, `begrenze_upload` prüft die Grösse vor dem Parsen. Im Browser ein Skript `app/static/js/aufnahme.js` (MediaRecorder, Hochladen per `fetch`), eingebunden nur auf den zwei Aufnahme-Seiten.

**Tech Stack:** Python 3.13, FastAPI 0.162, Starlette 1.10 (`FileResponse` mit Range, `request.form(max_files, max_fields)`), Jinja2, sqlite3, pytest, Node-E2E über CDP mit künstlichem Mikrofon, JavaScript ohne Build und ohne Bibliothek.

**Spec:** `docs/superpowers/specs/2026-10-30-sprachaufnahmen-design.md`. Der Schlussabschnitt «Klärungen nach dem Builder-Check (Claude)» geht den Abschnitten davor vor. Texte der Oberfläche, Meldungen und Abläufe stehen im Design; der Plan nennt nur Werte, die Tests brauchen.

## Vorbereitung (vor Task 1, Orchestrator)

- Branch `feat/17-sprachaufnahmen` von `main`, nachdem #16 gemergt ist. Design und Plan liegen schon auf `main` (`docs/17-19-plaene`).
- **Schnittstellen aus #16 prüfen** (weicht etwas ab, die betroffene Task anpassen und im Design unter «Klärungen» nachführen):
  1. `app/groesse.py`: `GRENZE_UPLOAD = 16 * 1024 * 1024`, `UPLOAD_PFADE` mit `/lehrperson/tagebuch/neu/aufnahme` und `/lehrperson/runden/\d{1,19}/fragen/\d{1,19}/aufnahme`, `ZuGross` (Starlette-`HTTPException`, 413). `app/main.py`: `FEHLERTEXTE[413]` mit Titel «Zu gross»; Router `aufnahmen` ohne `prefix` eingebunden.
  2. `app/aufnahmen.py`: `DATEINAME`, `aufnahme_pfad(verzeichnis, dateiname) -> Path | None`, `loesche_dateien(verzeichnis, dateinamen) -> None` (loggt ohne Namen), `aufnahmen_von_eintraegen`.
  3. `app/eintraege.py`: `lies_tagebuchtext(text, pflicht=True)`, `lege_tagebucheintrag_an(db, konto_id, art, text, *, impuls=None, leitfrage=None, aufnahme_id=None, jetzt=None) -> int` (nutzt die Transaktion des Aufrufers), `loesche_tagebucheintrag(db, konto_id, eintrag_id, aufnahmen_verzeichnis) -> bool`, `antworten_der_runde(db, konto_id, runde_id) -> dict[int, Row]`. **Prüfen, ob die Zeilen `aufnahme_id` und `aufnahme_dauer_sekunden` enthalten** und ob `kontext_runde` sie dem Template gibt (Bedarf an #16); sonst gilt der Rückfall aus den Klärungen (Player ohne Dauer).
  4. `app/sichtbar.py`: `sichtbare_runde(db, runde_id, stichtag) -> Row | None`. `app/inhalte.py`: `fragen(db, runde_id)` mit Spalten `id`, `typ`, `text`.
  5. `app/ansicht.py`: `Ansicht`, `hole_ansicht_lehrperson`, `fuer_gast(heute, band, ausgang)`. `app/seiten_lehrperson.py`: `kontext_tagebuch_wahl`, `kontext_runde`, `VORLAGEN`. `app/routen/lehrperson.py`: `ERLEDIGT` mit `gespeichert` und `aufnahme_geloescht`; `POST /lehrperson/runden/{id}` mit `anker=aufnahme-{frage_id}`.
  6. `app/zeit.py`: `zeitstempel() -> str`. `app/vorlagen.py`: Filter `dauer`.
  7. Templates: `lehrperson/_rahmen.html` (Kontext `ansicht`, `bereich`; Name der Variablen für die Meldung oben notieren), `_aufnahme.html` (`aufnahme`, `url`), `lehrperson/loeschen.html` (`frage_text`, `aktion`, `zurueck`). Plätze `{# #17: Frei sprechen #}` in `tagebuch_wahl.html` (Markup der Nachbarkarte «Frei schreiben» notieren), `{# #17: Antwort einsprechen #}` in `runde.html` (Namen der Schleifenvariablen für Frage und Antwort notieren), `{# #17: Aufnahme ersetzen oder löschen #}` in `tagebuch_eintrag.html`.
  8. `tests/testdaten.py`: `lege_runde_an`, `lege_antwort_an`, `lege_eintrag_an`, `lege_aufnahme_an` (64 Bytes, beginnt mit `b"\x1aE\xdf\xa3"`, `audio/webm`), `abzug`. `tests/conftest.py`: `einstellungen`, `client`, `db`, `lehrperson`, `zweite_lehrperson`, `auftraggeberin`, `heute_ist`, Helfer `anmelden`, `csrf_von`, `als_lehrperson`, `als_leitung`. Fixture `seiten_client` aus `tests/test_ansicht.py` als Vorbild für den Gast-Test.
  9. `tests/e2e-pilot.mjs`: `ablaufAufnahmen()` leer und aufgerufen; Chrome-Schalter `--use-fake-ui-for-media-stream`, `--use-fake-device-for-media-stream`; Helfer `legeZugangAn`, `warte`, `warteBis`, Konstante `DATEN`.
  10. `app/static/css/style.css`: Abschnitt `/* Pilot: Aufnahmen (#17) */` … `/* Ende #17 */`; Klassen `.karte--ruhend`, `.hinweis`, `.knopf--zweit`, `.knopf--klein`.

## Global Constraints

- Keine neuen Dependencies, keine Migration. Erlaubt: Standardbibliothek, `fastapi`, `starlette`, `jinja2`, `markupsafe`. Kein JavaScript-Paket, kein Build. Braucht etwas eine Dependency: anhalten und Koschi fragen.
- Bezeichner, Kommentare und Texte auf Deutsch, ohne ß, in Bezeichnern Umlaute ausgeschrieben. Oberfläche nach der Begriffstabelle des Designs, Anrede «du», keine Emojis (kein Mikrofon-Emoji), nie «Datensatz», «ID», «Upload».
- Kein Inline-JavaScript, kein `style=`, keine `on…=`-Attribute. Ein Skript `app/static/js/aufnahme.js`, nur auf den beiden Aufnahme-Seiten. Texte stehen im Template (`data-meldung="…"`, `hidden`), nicht im Skript.
- Dateien von #16 nur an den markierten Plätzen (`tagebuch_wahl.html`, `runde.html`, `tagebuch_eintrag.html`). Nicht angefasst: `app/main.py`, `groesse.py`, `eintraege.py`, `sichtbar.py`, `ansicht.py`, `seiten_lehrperson.py`, `zeit.py`, `vorlagen.py`, `sicherheit.py`, `routen/lehrperson.py`, `_aufnahme.html`, `_rahmen.html`, `basis.html`, `conftest.py`, `testdaten.py`.
- CSS nur im Abschnitt `/* Pilot: Aufnahmen (#17) */`; E2E nur in `ablaufAufnahmen()`.
- Pfad-IDs immer `Id` aus `app/typen.py`. Upload-Routen ohne `Form()`/`File()`-Parameter, `dependencies=[Depends(begrenze_upload), Depends(pruefe_csrf)]` in dieser Reihenfolge; übrige POST-Routen `Depends(pruefe_csrf)`; nach Erfolg 303.
- Jede Abfrage auf `aufnahmen`, `antworten`, `tagebucheintraege` einer Lehrperson filtert in SQL nach `konto_id`. Fremd, unbekannt, ungültige ID, fehlende Datei: 404, nicht unterscheidbar, nichts geändert. Runde und Frage nur über `sichtbare_runde` und `inhalte.fragen` (Frage gehört zur Runde, Typ `freitext`).
- Dateinamen nur `secrets.token_hex(16)` plus Endung aus `erkenne_format`; jeder Dateizugriff über `aufnahme_pfad` (Ausnahme: `raeume_waisen` mit eigenem Muster). Nie Name oder `Content-Type` aus der Anfrage verwenden.
- Logs nur als Ereignis ohne Inhalt, Dateinamen, Benutzernamen oder Konto-IDs: «Aufnahme abgelehnt: Speicherplatz knapp», «Aufnahme-Datei liess sich nicht loeschen» (aus #16).
- Konstanten in `app/aufnahmen.py`: `MAX_DAUER_SEKUNDEN = 600`, `TOLERANZ_SEKUNDEN = 10`, `MAX_BYTES = 15 * 1024 * 1024`, `MAX_ANFRAGE_BYTES = groesse.GRENZE_UPLOAD`, `RESERVE_BYTES = 50 * 1024 * 1024`, `WAISEN_ALTER_SEKUNDEN = 3600`, `BLOCK_BYTES = 1024 * 1024`.
- Tippflächen mindestens `2.75rem` hoch; 390 px und 1280 px ohne horizontales Scrollen; hell und dunkel lesbar.
- Repo öffentlich: Testdaten erfunden und neutral, Testdateien nur aus erfundenen Bytes.
- Commits: Präfix `feat:`/`test:`/`docs:`/`fix:`/`refactor:`, `(#17)` am Ende der ersten Zeile, Umlaute in der Commit-Zeile ausgeschrieben, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy9PjCyPCUAHE1BBLBG`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber (Routen-Inventar inklusive). Der Ruff-Hook entfernt ungenutzte Imports zwischen Edits, deshalb Import und Verwendung im selben Edit schreiben.

## Review Focus

1. **Fremde Aufnahme über die direkte Adresse:** Eine zweite Lehrperson erhält für jede Aufnahme der ersten 404 ohne ein Byte der Datei, auch mit `Range`; ein manipulierter Dateiname in der Datenbank trifft nie eine Datei ausserhalb des Ordners. (Task 2 `test_fremde_aufnahme_404`, `test_dateiname_manipuliert_404`)
2. **Grosse oder unangemeldete Anfrage wird nie geparst:** Mehr als 16 MiB und eine Anfrage ohne Anmeldung enden mit 413 bzw. 303, ohne dass `Request.form` läuft. (Task 3 `test_zu_gross_ohne_parsen`, `test_ohne_anmeldung_ohne_parsen`)
3. **Abgewiesene oder abgebrochene Speicherung hinterlässt nichts:** Ungültige Felder, zu langer Text, voller Speicher, Fehler beim Anlegen des Eintrags: keine Datei (auch keine `.teil`), keine Zeile. (Task 1 `test_schreibe_datei_abgewiesen`, Task 3 `test_upload_ungueltig`, `test_fehler_nach_schreiben_raeumt_auf`)
4. **Aufräumen trifft nur Waisen:** Eine junge Datei (Upload läuft gerade), eine verknüpfte Datei, ein Link und jede Datei ohne passenden Namen bleiben liegen. (Task 1 `test_raeume_waisen`)
5. **Antwort einsprechen verliert keinen Text:** Ersetzen und Löschen der Aufnahme lassen den getippten Text stehen; Ersetzen entfernt die alte Datei; eine fremde Lehrperson kann nichts löschen. (Task 5 `test_ersetzen_loescht_alte_datei`, `test_loeschen_text_bleibt`, Task 6 `test_aufnahme_loeschen_fremd_404`, E2E Schritt 6)

---

### Task 1: Format, Datei schreiben, Waisen

Spec: «Format je Browser» (Server), «Grenzen für Länge und Grösse», «Ablage», Klärungen «Reihenfolge der Prüfungen», «`dauer_sekunden`», «Waisen nur mit passendem Namen».

**Files:**
- Modify: `app/aufnahmen.py`
- Create: `tests/test_aufnahmen.py`

**Interfaces:**
- Consumes: #16 `DATEINAME`, `aufnahme_pfad`, `loesche_dateien`; `groesse.GRENZE_UPLOAD`.
- Produces:
  - Konstanten aus «Global Constraints».
  - `class AufnahmeFehler(Exception)` mit `status: int` und `meldung: str`; Standardmeldung für 400: «Diese Aufnahme liess sich nicht speichern. Bitte neu aufnehmen.»
  - `class Datei(NamedTuple)`: `name: str`, `mime_typ: str`, `groesse: int`.
  - `erkenne_format(anfang: bytes) -> tuple[str, str] | None`: `(mime_typ, endung)` nach der Tabelle im Design (`ftyp` in Bytes 4–7 → `("audio/mp4", ".m4a")`, EBML → `("audio/webm", ".webm")`, `OggS` → `("audio/ogg", ".ogg")`).
  - `lies_dauer(wert: str) -> int | None`: `""` → `None`; `re.fullmatch(r"[0-9]{1,6}", wert)` und `<= MAX_DAUER_SEKUNDEN + TOLERANZ_SEKUNDEN` → `int`; sonst `AufnahmeFehler(400, …)`.
  - `schreibe_datei(quelle: BinaryIO, verzeichnis: Path) -> Datei`: Grösse über `seek(0, os.SEEK_END)` (0 → 400, `> MAX_BYTES` → 413), Reserve über `shutil.disk_usage(verzeichnis).free - groesse < RESERVE_BYTES` (→ Log «Aufnahme abgelehnt: Speicherplatz knapp», 503), Format aus `quelle.read(12)` (→ 400), dann in `BLOCK_BYTES`-Stücken nach `{name}.teil` (`os.open` mit `0o600`), `os.replace` auf `name`. Jeder Fehler beim Schreiben entfernt die `.teil`-Datei und wird weitergegeben.
  - `WAISE = re.compile(r"[0-9a-f]{32}\.(webm|m4a|ogg)(\.teil)?")` und `raeume_waisen(db, verzeichnis: Path, jetzt: float | None = None) -> int`: `os.scandir`, nur `entry.is_file(follow_symlinks=False)` mit `WAISE.fullmatch(entry.name)`, Name nicht in `SELECT dateiname FROM aufnahmen`, `st_mtime < jetzt - WAISEN_ALTER_SEKUNDEN` (`jetzt` Standard `time.time()`); Fehler beim Löschen wie `loesche_dateien` loggen. Rückgabe: Anzahl gelöschter Dateien.

- [ ] **Step 1: Failing tests** `tests/test_aufnahmen.py` (Konstanten `WEBM = b"\x1aE\xdf\xa3" + bytes(60)`, `MP4 = b"\x00\x00\x00\x18ftypM4A " + bytes(52)`, `OGG = b"OggS" + bytes(60)` oben in der Datei; Task 3 und 5 importieren sie nicht, sondern definieren eigene, damit die Testdateien unabhängig bleiben):
  - `test_erkenne_format` (parametrisiert): `WEBM` → `("audio/webm", ".webm")`, `MP4` → `("audio/mp4", ".m4a")`, `OGG` → `("audio/ogg", ".ogg")`; `b""`, `b"\x1aE\xdf"`, `b"<html><script>"`, `b"ID3\x04\x00"`, `b"RIFF\x00\x00\x00\x00WAVE"`, `b"\x89PNG\r\n\x1a\n"` → `None`.
  - `test_lies_dauer`: `""` → `None`, `"0"` → `0`, `"42"` → `42`, `"610"` → `610`; `"abc"`, `"-1"`, `"611"`, `"99999999999999999999"`, `" 5"`, `"5.0"`, `"٣"` → `AufnahmeFehler` mit `status == 400`.
  - `test_schreibe_datei(tmp_path)`: `schreibe_datei(BytesIO(MP4), tmp_path)` → `DATEINAME.fullmatch(d.name)`, Endung `.m4a`, `d.mime_typ == "audio/mp4"`, `d.groesse == len(MP4)`; Datei hat genau diese Bytes und `stat.S_IMODE(...) == 0o600`; einzige Datei im Ordner. Zweimal aufgerufen → zwei verschiedene Namen.
  - `test_schreibe_datei_abgewiesen(tmp_path, monkeypatch)`: leer → 400; `b"<html>" + bytes(60)` → 400; `monkeypatch.setattr(aufnahmen, "MAX_BYTES", 100)`, `WEBM + bytes(100)` → 413; danach `list(tmp_path.iterdir()) == []`.
  - `test_speicher_knapp(tmp_path, monkeypatch, caplog)`: `shutil.disk_usage` liefert `free = RESERVE_BYTES + len(WEBM) - 1` → 503, Ordner leer, genau ein Log-Eintrag «Aufnahme abgelehnt: Speicherplatz knapp».
  - `test_fehler_beim_umbenennen(tmp_path, monkeypatch)`: `os.replace` wirft `OSError` → `OSError` weitergegeben, Ordner leer (keine `.teil`).
  - `test_raeume_waisen(db, lehrperson, tmp_path)`: Dateien anlegen und per `os.utime` auf «vor zwei Stunden» setzen: `verknuepft` (gültiger Name, Zeile in `aufnahmen`), `waise` (gültiger Name), `teil` (gültiger Name + `.teil`), `notiz.txt`, `reflexion.db`, Ordner mit gültigem Namen, symbolischer Link mit gültigem Namen auf eine Datei ausserhalb von `tmp_path / "ordner"`; dazu `jung` (gültiger Name, jetzt geschrieben). `raeume_waisen(db, ordner)` → `2`; weg sind nur `waise` und `teil`; das Ziel des Links existiert noch.
- [ ] **Step 2:** `uv run pytest tests/test_aufnahmen.py -v` → FAIL (Namen fehlen).
- [ ] **Step 3:** implementieren (Signaturen oben).
- [ ] **Step 4:** `uv run pytest -v` → PASS (auch die Grundstock-Tests von #16), Lint sauber.
- [ ] **Step 5:** Commit `feat: Format erkennen, Aufnahme-Datei schreiben, Waisen aufraeumen (#17)`.

### Task 2: Aufnahmen abspielen (Lehrperson und Auftraggeberin)

Spec: «Ausliefern und Abspielen», «Sicherheit und Datenschutz» (Zugriff), «Adressen».

**Files:**
- Modify: `app/aufnahmen.py`, `app/routen/aufnahmen.py`
- Create: `tests/test_aufnahmen_routen.py`

**Interfaces:**
- Consumes: Task 1 (nichts ausser `aufnahme_pfad` aus #16), `testdaten.lege_aufnahme_an`.
- Produces (`app/aufnahmen.py`): `eigene_aufnahme(db, konto_id: int, aufnahme_id: int) -> sqlite3.Row | None` (`WHERE id = ? AND konto_id = ?`), `aufnahme(db, aufnahme_id: int) -> sqlite3.Row | None`.
- Produces (`app/routen/aufnahmen.py`): `lehrperson = APIRouter(prefix="/lehrperson", dependencies=[Depends(braucht_lehrperson)])`, `verwaltung = APIRouter(prefix="/verwaltung", dependencies=[Depends(braucht_auftraggeberin)])`, `DB`, `_verzeichnis(request) -> Path`, `_ausliefern(request, zeile: Row | None) -> FileResponse` (404 bei `None`, Pfad `None` oder `not pfad.is_file()`; sonst `FileResponse(pfad, media_type=zeile["mime_typ"], filename=f"aufnahme-{id}{suffix}", content_disposition_type="inline", headers={"Cross-Origin-Resource-Policy": "same-origin"})`). Routen `GET /lehrperson/aufnahmen/{aufnahme_id}` und `GET /verwaltung/aufnahmen/{aufnahme_id}` (`Id`). Am Modulende `router.include_router(lehrperson)` und `router.include_router(verwaltung)`; alle Routen dieser Datei werden **vor** diesen zwei Zeilen definiert (spätere Tasks fügen ihre Routen darüber ein).

- [ ] **Step 1: Failing tests** `tests/test_aufnahmen_routen.py` (Fixture `aufnahme_der_ersten(db, lehrperson, einstellungen)` → `(aid, pfad)` über `testdaten.lege_aufnahme_an`):
  - `test_eigene_aufnahme_abspielen`: als Lehrperson `GET /lehrperson/aufnahmen/{aid}` → 200; `content-type == "audio/webm"`; `content-disposition == f'inline; filename="aufnahme-{aid}.webm"'`; `accept-ranges == "bytes"`; `cache-control == "no-store"`; `x-content-type-options == "nosniff"`; `cross-origin-resource-policy == "same-origin"`; Body gleich Dateiinhalt.
  - `test_range`: `Range: bytes=0-3` → 206, `content-range == "bytes 0-3/64"`, 4 Bytes; `Range: bytes=64-` → 416.
  - `test_fremde_aufnahme_404` (**Akzeptanzkriterium**, Review Focus 1): als `zweite_lehrperson` ohne und mit `Range: bytes=0-3` → 404, `b"\x1aE\xdf\xa3"` nicht im Body, «Nicht gefunden» im Text.
  - `test_ungueltige_ids` (parametrisiert `999`, `abc`, `0`, `-1`, `99999999999999999999`) → 404 auf beiden Adressen (Lehrperson bzw. Auftraggeberin angemeldet).
  - `test_datei_fehlt_404`: Datei löschen → 404 (kein 500).
  - `test_dateiname_manipuliert_404`: `UPDATE aufnahmen SET dateiname = '../reflexion.db'` → 404 auf beiden Adressen.
  - `test_auftraggeberin_hoert_alle`: Aufnahmen beider Lehrpersonen → je 200 mit dem Dateiinhalt; `content-type` aus der Zeile.
  - `test_rollen_getrennt`: Lehrperson auf `/verwaltung/aufnahmen/{aid}` → 403; Auftraggeberin auf `/lehrperson/aufnahmen/{aid}` → 403; ohne Anmeldung beide → 303 auf `/`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` → PASS (Routen-Inventar deckt die zwei GET-Routen ab), Lint.
- [ ] **Step 5:** Commit `feat: Aufnahmen abspielen fuer Lehrperson und Auftraggeberin (#17)`.

### Task 3: Tagebuch-Aufnahme speichern (Server, Seite ohne JavaScript)

Spec: «Hochladen», «Grenzen», «Grösse vor dem Parsen ohne Middleware» (mit Klärung «Grössengrenze»), «Ablage», «Seite ‹Frei sprechen›», Klärungen «Fehler beim Hochladen», «Fehler nach dem Schreiben», «Rahmen der Seiten».

**Files:**
- Modify: `app/aufnahmen.py`, `app/routen/aufnahmen.py`
- Create: `app/templates/lehrperson/aufnahme_tagebuch.html`, `app/templates/lehrperson/_aufnehmen.html`, `tests/test_aufnahme_hochladen.py`

**Interfaces:**
- Consumes: Task 1 (`schreibe_datei`, `lies_dauer`, `raeume_waisen`, `AufnahmeFehler`, `Datei`), #16 `eintraege.lies_tagebuchtext`, `eintraege.lege_tagebucheintrag_an`, `transaktion`, `zeit.zeitstempel`, `hole_ansicht_lehrperson`, `texte.lies_text`, `groesse.ZuGross`.
- Produces (`app/aufnahmen.py`): `lege_aufnahme_an(db, konto_id: int, datei: Datei, dauer_sekunden: int | None) -> int` (nur `INSERT`, Transaktion des Aufrufers); `aufnahme_als_tagebucheintrag(db, konto_id: int, datei: Datei, dauer_sekunden: int | None, text: str | None, jetzt: str | None = None) -> int` (in `transaktion(db)`: `lege_aufnahme_an`, dann `eintraege.lege_tagebucheintrag_an(db, konto_id, "aufnahme", text, aufnahme_id=…, jetzt=…)` über das Modul; Rückgabe `eintrag_id`).
- Produces (`app/routen/aufnahmen.py`):
  - `async def begrenze_upload(request: Request) -> None`: `content-length` fehlt → `HTTPException(411)`; nicht `[0-9]+` oder `> aufnahmen.MAX_ANFRAGE_BYTES` → `raise ZuGross()`; dann `await request.form(max_files=1, max_fields=5)`.
  - `async def _lies_aufnahme(request) -> tuple[UploadFile, int | None, str]`: aus `await request.form()` Datei (`isinstance(..., UploadFile)`, sonst `AufnahmeFehler(400)`), `lies_dauer`, Text (`""`, wenn nicht vorhanden; Nicht-`str` → 400).
  - `GET`/`POST /lehrperson/tagebuch/neu/aufnahme`. POST: `_lies_aufnahme` → `lies_tagebuchtext(text, pflicht=False)` (`InhaltFehler` → 400 mit dessen Meldung) → `schreibe_datei(datei.file, verzeichnis)` → `aufnahme_als_tagebucheintrag` (bei Ausnahme `loesche_dateien(verzeichnis, [d.name])`, dann weiterwerfen) → `raeume_waisen` → 303 auf `/lehrperson/tagebuch/{eintrag_id}?erledigt=gespeichert`. `AufnahmeFehler` 400 → Seite mit `meldung` und Status 400; 413/503 → `HTTPException(status)`.
  - `_seite_tagebuch(request, db, ansicht, meldung=None, status=200)`: Kontext `ansicht`, `bereich="tagebuch"`, `hinweis_tagebuch`, `hinweis_aufnahme` (`lies_text`), `max_dauer=MAX_DAUER_SEKUNDEN`, `max_bytes=MAX_BYTES`, `aktion="/lehrperson/tagebuch/neu/aufnahme"`, `zurueck`, `schreiben="/lehrperson/tagebuch/neu/frei"`, Meldung unter dem Namen, den `_rahmen.html` erwartet (Vorbereitung 7).
- Templates (Texte aus «Seite ‹Frei sprechen›»): `aufnahme_tagebuch.html` erweitert `lehrperson/_rahmen.html`; Formular `method="post" enctype="multipart/form-data"` mit `csrf_feld(request)`, `<input type="hidden" name="dauer_sekunden">`, `{% include "lehrperson/_aufnehmen.html" %}`, `<details>` «Etwas dazuschreiben (freiwillig)» mit `<textarea name="text" rows="3" maxlength="20000">`. `_aufnehmen.html` in dieser Task nur mit dem Rückfall: Satz «Dieser Browser kann hier nicht aufnehmen. Du kannst deinen Eintrag schreiben oder eine Aufnahme aus einer anderen App hochladen.», `<input type="file" name="aufnahme" accept="audio/*">`, Knopf «Speichern» (`data-aktion="speichern"`), Link «Stattdessen schreiben» auf `schreiben`.

- [ ] **Step 1: Failing tests** `tests/test_aufnahme_hochladen.py` (eigene Konstanten `WEBM`, `MP4`; Helfer `sende(client, dateien, **felder)` postet `files=` und `data=` mit gültigem `csrf` aus `csrf_von(client, "/lehrperson/tagebuch/neu/aufnahme")`; Lehrperson per `als_lehrperson`):
  - `test_seite(client, lehrperson, db)`: 200; `<h1>` mit «Frei sprechen»; `lies_text(db, "hinweis_tagebuch")` und `lies_text(db, "hinweis_aufnahme")` (formatiert) im Text; `enctype="multipart/form-data"`, `name="aufnahme"`, `accept="audio/*"`, `maxlength="20000"`, `name="dauer_sekunden"`, `class="inhalt bereich--tagebuch"`; kein `style=`, kein `<script>` ohne `src`, kein ` on…=` in einem Tag.
  - `test_upload_ok`: Datei als `("bild.html", MP4, "text/html")`, `dauer_sekunden="42"`, `text=" Notiz\r\nzwei "` → 303, `location` passt auf `^/lehrperson/tagebuch/(\d+)\?erledigt=gespeichert$`; Zeile in `aufnahmen`: `konto_id` der Lehrperson, `mime_typ == "audio/mp4"`, `groesse_bytes == len(MP4)`, `dauer_sekunden == 42`, Name endet auf `.m4a`; Datei mit denselben Bytes im Aufnahmen-Ordner; Eintrag `art == "aufnahme"`, `text == "Notiz\nzwei"`, `aufnahme_id` = diese Zeile, `erstellt == geaendert`. `GET location` zeigt «Gespeichert.» und `<audio` mit `src="/lehrperson/aufnahmen/{aid}"`.
  - `test_upload_ohne_text_und_dauer`: nur Datei → 303, `text IS NULL`, `dauer_sekunden IS NULL`.
  - `test_upload_ungueltig` (Review Focus 3, parametrisiert): kein Dateifeld; leere Datei; `aufnahme` als Textfeld (`data={"aufnahme": "x"}`); `b"ID3\x04" + bytes(60)`; `dauer_sekunden` `"abc"`, `"-1"`, `"611"`, `"99999999999999999999"`; `text="x" * 20_001` → je 400; `testdaten.abzug(db)` unverändert; Aufnahmen-Ordner leer (auch keine `.teil`). Beim zu langen Text steht «höchstens 20 000 Zeichen» im Text, bei den anderen «Diese Aufnahme liess sich nicht speichern.».
  - `test_zu_gross_ohne_parsen(client, lehrperson, monkeypatch)` (Review Focus 2): `monkeypatch.setattr(starlette.requests.Request, "form", …)` mit einer Funktion, die `AssertionError("geparst")` wirft; `POST` mit `content=b"x" * (MAX_ANFRAGE_BYTES + 1)`, `content-type: multipart/form-data; boundary=x` → 413, «Zu gross» im Text.
  - `test_ohne_anmeldung_ohne_parsen(client, monkeypatch)`: gleicher Patch, ohne Anmeldung `POST` mit gültiger Datei → 303, `location == "/"`.
  - `test_ohne_content_length_411`: `content=` Generator mit zwei Stücken → 411, Ordner leer.
  - `test_datei_zu_gross(monkeypatch)`: `monkeypatch.setattr(aufnahmen, "MAX_BYTES", 1000)`, `WEBM + bytes(1000)` → 413, Ordner leer.
  - `test_ohne_csrf_403`: gültige Datei ohne `csrf` → 403 «Formular abgelaufen», Ordner leer.
  - `test_speicher_knapp_503(monkeypatch)`: `shutil.disk_usage` mit `free=0` → 503, Ordner leer, keine Zeile.
  - `test_fehler_nach_schreiben_raeumt_auf(monkeypatch)` (Review Focus 3): `monkeypatch.setattr(eintraege, "lege_tagebucheintrag_an", …)` wirft `RuntimeError` → `pytest.raises(RuntimeError)` um den POST; keine Zeile in `aufnahmen`, Ordner leer.
  - `test_waisen_nach_upload`: vorher Datei `"a" * 32 + ".webm"` ohne Zeile, `os.utime` zwei Stunden zurück → nach erfolgreichem Upload weg; die neue Datei ist da.
  - `test_upload_routen_ohne_body_parameter(einstellungen)`: für jede Route aus `iter_route_contexts(erstelle_app(einstellungen).routes)` mit `POST` und einem Pfad, der auf ein Muster aus `groesse.UPLOAD_PFADE` passt (`{…}` durch `1` ersetzt): `ctx.original_route.dependant` rekursiv über `.dependencies` ohne `body_params`; mindestens eine solche Route gefunden.
  - `test_eintrag_loeschen_mit_echter_datei`: Upload, dann `POST /lehrperson/tagebuch/{eid}/loeschen` (#16) → Datei weg, Zeile weg, `GET /lehrperson/aufnahmen/{aid}` → 404.
  - `test_auftraggeberin_403`: als Auftraggeberin `GET` → 403.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` → PASS (Routen-Inventar: `POST` mit `data={}` erreicht `pruefe_csrf` → 403), Lint.
- [ ] **Step 5:** Commit `feat: Tagebuch-Aufnahme speichern mit Grenzen vor dem Parsen (#17)`.

### Task 4: Aufnehmen im Browser und Wahl «Frei sprechen»

Spec: «Aufnehmen im Browser», «Format je Browser» (Browser), «Hochladen: ein POST mit `fetch`», «Mikrofon verweigert und andere Fehler», «Gast und Vorschau», Klärungen «Ohne JavaScript», «Wahl-Karte», «E2E».

**Files:**
- Create: `app/static/js/aufnahme.js`
- Modify: `app/templates/lehrperson/_aufnehmen.html`, `app/templates/lehrperson/aufnahme_tagebuch.html`, `app/templates/lehrperson/tagebuch_wahl.html` (nur Platz `{# #17: Frei sprechen #}`), `app/templates/lehrperson/tagebuch_eintrag.html` (nur die Kommentarzeile `{# #17: … #}` entfernen), `app/static/css/style.css` (Abschnitt #17), `tests/test_aufnahme_hochladen.py`, `tests/e2e-pilot.mjs` (`ablaufAufnahmen`)

**Interfaces:**
- Consumes: Task 3 (Seite, Kontext `max_dauer`, `max_bytes`, `schreiben`), #16 `kontext_tagebuch_wahl`, `fuer_gast`, `VORLAGEN`.
- Produces (Markup in `_aufnehmen.html`, vom Skript gelesen): Wurzel `<div class="aufnehmen" data-aufnehmen data-max-dauer="{{ max_dauer }}" data-max-bytes="{{ max_bytes }}">`; Teil «Bereit/Nimmt auf/Fertig» mit `hidden` (Skript blendet ein); Knöpfe `data-aktion="start"` «Aufnahme starten», `"stopp"` «Stopp», `"neu"` «Neu aufnehmen» (`knopf--zweit`), `"speichern"` «Speichern» (Submit); Zeit `data-zeit` («0:00 / 10:00»); Statuszeile `role="status" data-status`; Player `<audio controls data-vorhoeren hidden>`; Rückfall-Block `data-rueckfall` (Satz und Dateifeld aus Task 3, ohne JavaScript sichtbar); Meldungen `data-meldung="…"` mit `hidden` für `verweigert` (mit `<details>` «So gibst du das Mikrofon frei»), `kein-mikrofon`, `besetzt`, `nicht-unterstuetzt`, `angehalten`, `noch-eine-minute`, `hoechstdauer`, `zu-gross`, `keine-verbindung`, `abgemeldet`, `abgelaufen`, `ungueltig`, `serverfehler`, `wird-gespeichert`. Jede Fehlermeldung mit Link «Stattdessen schreiben» auf `schreiben`. Optional `data-anker` am Formular (Task 6).
- Skript (Verhalten nach Design, Aufteilung frei): erkennt beim Laden `navigator.mediaDevices?.getUserMedia` und `window.MediaRecorder`; ohne → Meldung `nicht-unterstuetzt`, Rückfall bleibt. Mit → Rückfall verstecken, Start einblenden. Formatwahl in der Reihenfolge des Designs über `MediaRecorder.isTypeSupported`; `audioBitsPerSecond: 64000`, `start(1000)`; nach Stopp `track.stop()`; Zeit über `performance.now()`, Meldung `noch-eine-minute` ab 540 s, Stopp und `hoechstdauer` bei `data-max-dauer`; `visibilitychange` → `hidden` oder `error` am Recorder → Stopp und `angehalten`; Wake Lock, falls vorhanden; Fehlernamen nach der Tabelle «Mikrofon verweigert». Speichern: `submit` abfangen, `blob.size > data-max-bytes` → `zu-gross`; `FormData(form)`, Datei als `aufnahme` mit Name `aufnahme.m4a|.webm|.ogg` nach Typ, `dauer_sekunden` = aufgerundete Sekunden; Knöpfe gesperrt, `wird-gespeichert`; Auswertung nach der Tabelle «Auswertung der Antwort» (`new URL(antwort.url).pathname === "/"` → `abgemeldet`); bei Erfolg `location.assign(antwort.url + (form.dataset.anker ? "#" + form.dataset.anker : ""))`. «Neu aufnehmen» ruft `URL.revokeObjectURL`.
- Wahl-Karte: bei `ansicht.speichert` Link-Karte wie «Frei schreiben» auf `ansicht.url("/tagebuch/neu/aufnahme")`, Titel «Frei sprechen», Unterzeile «Eintrag einsprechen, zum Beispiel direkt nach dem Unterricht.»; sonst `<li class="karte karte--ruhend">` ohne Link mit Unterzeile «In dieser Ansicht nicht verfügbar.».

- [ ] **Step 1: Failing tests** in `tests/test_aufnahme_hochladen.py`:
  - `test_aufnehmen_markup`: Seite enthält `data-max-dauer="600"`, `data-max-bytes="15728640"`, `src="/static/js/aufnahme.js"` mit `defer`, alle 14 `data-meldung`-Werte oben, `data-aktion="start"` innerhalb eines Elements mit `hidden`, «Das Mikrofon ist nicht freigegeben.», «So gibst du das Mikrofon frei», `href="/lehrperson/tagebuch/neu/frei"` mit «Stattdessen schreiben»; weiterhin kein Inline-Skript, kein `style=`.
  - `test_skript_nur_auf_aufnahme_seiten`: `aufnahme.js` nicht in `GET /lehrperson`, `/lehrperson/tagebuch/neu`, `/lehrperson/tagebuch/neu/frei`.
  - `test_wahl_frei_sprechen`: `GET /lehrperson/tagebuch/neu` enthält `href="/lehrperson/tagebuch/neu/aufnahme"`, «Frei sprechen», «Eintrag einsprechen, zum Beispiel direkt nach dem Unterricht.».
  - `test_wahl_gast_ohne_link(einstellungen, db)`: eigene Fixture nach Vorbild `seiten_client` (Route `GET /test-gast/wahl` rendert `VORLAGEN["tagebuch_wahl"]` mit `kontext_tagebuch_wahl(db, fuer_gast(date(2026, 11, 24), "Band", ("Anmelden", "/")))`) → «Frei sprechen», «In dieser Ansicht nicht verfügbar.», `karte--ruhend`; `"/aufnahme"` kommt im HTML nicht vor.
  - `test_eintrag_ohne_platzhalter`: `tagebuch_eintrag.html` enthält kein `#17:`.
- [ ] **Step 2:** FAIL. **Step 3:** Markup, Skript und CSS implementieren (Aufnahmeknopf gross und ruhig, Zeit gut lesbar, Player `width: 100%`). `node --check app/static/js/aufnahme.js`.
- [ ] **Step 4:** `uv run pytest -v` → PASS, Lint.
- [ ] **Step 5: E2E** `ablaufAufnahmen()`, erster Teil (Design «E2E» Schritte 1–5), in 390 px hell; je Seite `keinUeberlauf` und `keineFehlerSeit`:
  - Auftraggeberin legt `lp.e2e.aufnahme1` («Ada Aufnahme») und `lp.e2e.aufnahme2` («Ben Beispiel») an (`legeZugangAn`), Passwörter merken; als erste anmelden.
  - Wahl → `muss` Link «Frei sprechen» → Seite mit beiden Hinweisen, `[data-aktion="start"]` sichtbar, Rückfall versteckt.
  - **Mikrofon verweigert:** `cdp("Browser.setPermission", { permission: { name: "microphone" }, setting: "denied", origin: basis })`, Start → `[data-meldung="verweigert"]` sichtbar (`!hidden`), `<details>` öffnen, Link «Stattdessen schreiben» → `pfad() === "/lehrperson/tagebuch/neu/frei"`. Erscheint die Meldung nicht, `navigator.mediaDevices.getUserMedia` per `js()` durch eine Funktion ersetzen, die mit `new DOMException("x", "NotAllowedError")` scheitert, und erneut prüfen. Danach `setting: "granted"`. Screenshot `40-aufnahme-verweigert`.
  - Dateien in `${DATEN}aufnahmen/` zählen. Start → nach 1 s Zeit ≠ «0:00 / 10:00» (Screenshot `41-aufnahme-laeuft`) → nach 3 s Stopp → `warteBis` Player mit `src` `blob:`, nach `load()` `readyState >= 1` (Screenshot `42-aufnahme-fertig`). «Neu aufnehmen» → Player versteckt, Start sichtbar. 2 s aufnehmen, Stopp, `sende('[data-aktion="speichern"]')` → Pfad `/lehrperson/tagebuch/\d+`, «Gespeichert.», `<audio` mit `src` `/lehrperson/aufnahmen/\d+` (Screenshot `43-aufnahme-eintrag`).
  - Im Browser `fetch(src, { headers: { Range: "bytes=0-1" } })` → 206, `content-type` beginnt mit `audio/` (Format ausgeben); genau **eine** neue Datei im Ordner, Name passt auf `^[0-9a-f]{32}\.(webm|m4a|ogg)$`.
  - «Meine Einträge» zeigt «Gesprochener Eintrag» und «Sek.» (Dauer).
- [ ] **Step 6:** `make e2e` → «… bestanden, 0 fehlgeschlagen»; Screenshots ansehen (Knöpfe tippbar, Meldung lesbar, kein Überlauf).
- [ ] **Step 7:** Commit `feat: Aufnehmen im Browser und Wahl Frei sprechen (#17)`.

### Task 5: Aufnahme an einer Antwort (Fachlogik, Soll)

Spec: «Antworten auf Runden-Fragen (Soll)» (Speichern, Aufnahme löschen), Konvention «Zeile existiert genau dann, wenn Inhalt» (#16), Klärung «Antwort-Aufnahme in eigener Transaktion». Fällt bei Zeitnot zusammen mit Task 6 weg.

**Files:**
- Modify: `app/aufnahmen.py`
- Create: `tests/test_aufnahmen_antwort.py`

**Interfaces:**
- Consumes: Task 1 (`Datei`), Task 3 (`lege_aufnahme_an`), #16 `loesche_dateien`, `transaktion`, `zeit.zeitstempel`.
- Produces:
  - `aufnahme_der_antwort(db, konto_id: int, frage_id: int) -> sqlite3.Row | None`: Zeile aus `aufnahmen` (`id`, `dateiname`, `dauer_sekunden`) zur Antwort dieses Kontos, sonst `None`.
  - `haenge_an_antwort(db, konto_id: int, frage_id: int, datei: Datei, dauer_sekunden: int | None, verzeichnis: Path, jetzt: str | None = None) -> None`: `db.in_transaction` → `RuntimeError`; in `transaktion`: `lege_aufnahme_an`; gibt es die Antwort (`frage_id`, `konto_id`): alte `aufnahme_id` merken, `UPDATE antworten SET aufnahme_id = neu, geaendert = jetzt`, dann `DELETE FROM aufnahmen WHERE id = alt AND konto_id = ?`; sonst `INSERT antworten (frage_id, konto_id, aufnahme_id, erstellt, geaendert)` mit `erstellt = geaendert = jetzt`. Nach dem `COMMIT` `loesche_dateien(verzeichnis, [alter_name])`.
  - `loesche_aufnahme_der_antwort(db, konto_id: int, frage_id: int, verzeichnis: Path, jetzt: str | None = None) -> bool`: `RuntimeError` in laufender Transaktion; ohne Antwort mit Aufnahme → `False`, nichts geändert; sonst `aufnahme_id = NULL`, `geaendert = jetzt`, Antwortzeile löschen, wenn `text` und `skalawert` `NULL` sind, Zeile in `aufnahmen` löschen; nach dem `COMMIT` die Datei; `True`.
  - Prüfen, ob Frage und Runde sichtbar sind, ist Sache der Route (Task 6).

- [ ] **Step 1: Failing tests** `tests/test_aufnahmen_antwort.py` (Runde mit `f1` Freitext über `testdaten.lege_runde_an`; `datei` über `aufnahmen.schreibe_datei(BytesIO(WEBM), verzeichnis)`; `jetzt` fest):
  - `test_neue_antwort_nur_aufnahme`: Zeile mit `text IS NULL`, `skalawert IS NULL`, `aufnahme_id` gesetzt, `erstellt == geaendert == jetzt`; `aufnahme_der_antwort` liefert `dauer_sekunden`.
  - `test_textantwort_erhaelt_aufnahme`: `testdaten.lege_antwort_an(…, text="Getippt")`, `erstellt`/`geaendert` per `UPDATE` auf `2026-11-01T00:00:00Z` → nach `haenge_an_antwort(…, jetzt="2026-11-24T10:00:00Z")` Text «Getippt», `geaendert` neu, `erstellt` alt.
  - `test_ersetzen_loescht_alte_datei` (Review Focus 5): zweimal anhängen → genau eine Zeile in `aufnahmen` für dieses Konto, alte Datei weg, neue da und verknüpft, Text unverändert.
  - `test_loeschen_text_bleibt` (Review Focus 5): Antwort mit Text und Aufnahme → `True`; Text da, `aufnahme_id IS NULL`, Datei und `aufnahmen`-Zeile weg.
  - `test_loeschen_nur_aufnahme_loescht_zeile`: Antwort nur mit Aufnahme → Antwortzeile weg.
  - `test_loeschen_ohne_aufnahme`: Antwort nur mit Text → `False`, `testdaten.abzug` unverändert.
  - `test_fremde_antwort_unberuehrt(…, zweite_lehrperson)`: zweite hat Antwort mit Aufnahme auf `f1`; erste hängt an und löscht → Antwort, Zeile und Datei der zweiten unverändert.
  - `test_in_laufender_transaktion`: beide Funktionen in `transaktion(db)` → `RuntimeError`.
  - `test_datenbankfehler_alte_aufnahme_bleibt(monkeypatch)`: bestehende Antwort mit Aufnahme; `UPDATE` scheitern lassen (z. B. `lege_aufnahme_an` gepatcht, wirft) → Ausnahme; alte Zeile und Datei unverändert.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS, Lint.
- [ ] **Step 5:** Commit `feat: Aufnahme an einer Antwort anhaengen, ersetzen, loeschen (#17)`.

### Task 6: Antwort einsprechen (Routen, Seite, Platz in der Runde, Soll)

Spec: «Adressen» (Soll-Zeilen), «Antworten auf Runden-Fragen (Soll)», «Gast und Vorschau», Klärungen «Anker nach dem Speichern», «Bestätigung», «Platz in `runde.html`».

**Files:**
- Modify: `app/routen/aufnahmen.py`, `app/templates/lehrperson/runde.html` (nur Platz `{# #17: Antwort einsprechen #}`), `app/static/css/style.css` (Abschnitt #17), `tests/test_aufnahmen_antwort.py`
- Create: `app/templates/lehrperson/aufnahme_antwort.html`

**Interfaces:**
- Consumes: Task 5, Task 3 (`begrenze_upload`, `_lies_aufnahme`, Fehlerbehandlung), Task 4 (`_aufnehmen.html`, `aufnahme.js`, `data-anker`), #16 `sichtbare_runde`, `inhalte.fragen`, `lehrperson/loeschen.html`, `_aufnahme.html`.
- Produces: `_freitext_frage(db, ansicht, runde_id, frage_id) -> tuple[Row, Row]` (Runde über `sichtbare_runde(db, runde_id, ansicht.stichtag)`, Frage aus `inhalte.fragen(db, runde_id)` mit passender `id` und `typ == "freitext"`; sonst `HTTPException(404)`), aufgerufen in **jeder** der vier Routen vor jedem Schreiben. Routen:
  - `GET`/`POST /lehrperson/runden/{runde_id}/fragen/{frage_id}/aufnahme` (POST mit `begrenze_upload`, `pruefe_csrf`): Speichern über `schreibe_datei` und `haenge_an_antwort` (bei Ausnahme neue Datei löschen), `raeume_waisen`, 303 auf `/lehrperson/runden/{runde_id}?erledigt=gespeichert#frage-{frage_id}`. Seite: `bereich="runden"`, Fragetext als reiner Text, beide Hinweise, «Deine geschriebene Antwort bleibt erhalten.», bei bestehender Aufnahme zusätzlich «Die neue Aufnahme ersetzt die bisherige.», «‹ Zurück zur Runde» auf `/lehrperson/runden/{runde_id}#frage-{frage_id}`, Formular mit `data-anker="frage-{frage_id}"`, `schreiben` = Rücklink zur Frage. Kein Textfeld.
  - `GET`/`POST /lehrperson/runden/{runde_id}/fragen/{frage_id}/aufnahme/loeschen`: Bestätigung über `lehrperson/loeschen.html` mit `frage_text` «Die Aufnahme zu dieser Frage löschen? Deine geschriebene Antwort bleibt.»; POST → `loesche_aufnahme_der_antwort`, `False` → 404; sonst 303 auf `/lehrperson/runden/{runde_id}?erledigt=aufnahme_geloescht#frage-{frage_id}`. GET ohne Aufnahme → 404.
- Platz in `runde.html` (innerhalb von `{% if ansicht.speichert %}`, nur Freitext): mit Aufnahme `{% include "_aufnahme.html" %}` mit `url="/lehrperson/aufnahmen/" ~ aufnahme_id` (Rückfall ohne `aufnahme_dauer_sekunden` siehe Vorbereitung 3), Links «Aufnahme ersetzen» und «Aufnahme löschen»; sonst `<button type="submit" name="anker" value="aufnahme-{frage_id}" class="knopf knopf--klein knopf--zweit">Antwort einsprechen</button>`.

- [ ] **Step 1: Failing tests** in `tests/test_aufnahmen_antwort.py` (Runde `rid` am 23.11. mit `f1` Freitext, `f2` Skala; `heute_ist(date(2026, 11, 24))`; Lehrperson angemeldet):
  - `test_antwort_seite`: `GET …/fragen/{f1}/aufnahme` → 200, Fragetext, «Deine geschriebene Antwort bleibt erhalten.», kein «ersetzt die bisherige», `data-anker="frage-{f1}"`, `href="/lehrperson/runden/{rid}#frage-{f1}"`, `class="inhalt bereich--runden"`, `aufnahme.js` eingebunden.
  - `test_antwort_hochladen`: Text «Getippt» vorher gespeichert; POST mit `WEBM`, `dauer_sekunden="3"` → 303, `location == f"/lehrperson/runden/{rid}?erledigt=gespeichert#frage-{f1}"`; Text bleibt; Seite zeigt danach «Die neue Aufnahme ersetzt die bisherige.».
  - `test_antwort_404` (parametrisiert: Skala-Frage `f2`; Frage einer anderen sichtbaren Runde; Runde am 30.11. bei `heute_ist(29.11.)`; Frage `999`): `GET` und `POST` (gültige Datei, `csrf`) auf `…/aufnahme`, `GET`/`POST …/aufnahme/loeschen` → 404; `testdaten.abzug` und Aufnahmen-Ordner unverändert.
  - `test_aufnahme_loeschen_route`: Bestätigung mit dem Satz oben, «Endgültig löschen», «Abbrechen»; POST → 303 auf `…?erledigt=aufnahme_geloescht#frage-{f1}`; Seite der Runde zeigt «Die Aufnahme wurde gelöscht.», Text noch im Feld; Datei weg.
  - `test_aufnahme_loeschen_fremd_404` (Review Focus 5): erste hat Aufnahme an `f1`; als `zweite_lehrperson` `GET`/`POST …/aufnahme/loeschen` → 404; Aufnahme der ersten (Zeile, Datei) unverändert.
  - `test_runde_platz`: ohne Aufnahme `name="anker" value="aufnahme-{f1}"` mit «Antwort einsprechen», nicht für `f2`; mit Aufnahme `<audio` mit `src="/lehrperson/aufnahmen/{aid}"` und `preload="none"`, Links `…/fragen/{f1}/aufnahme` («Aufnahme ersetzen») und `…/fragen/{f1}/aufnahme/loeschen` («Aufnahme löschen»), kein `value="aufnahme-{f1}"`.
  - `test_runde_gast_ohne_platz(einstellungen, db, lehrperson)`: Fixture wie in Task 4, `VORLAGEN["runde"]` mit `kontext_runde(db, fuer_gast(…), rid)`, Antwort mit Aufnahme der Lehrperson in der Datenbank → weder «Antwort einsprechen» noch `/aufnahme` noch `<audio` im HTML.
  - `test_speichern_und_einsprechen`: `POST /lehrperson/runden/{rid}` mit `antwort_{f1}="Neu"`, `anker=aufnahme-{f1}` → 303 auf `…/fragen/{f1}/aufnahme` (Logik #16), Seite dort 200.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` → PASS (Routen-Inventar deckt die vier neuen Routen ab), Lint.
- [ ] **Step 5:** Commit `feat: Antwort einsprechen, ersetzen und loeschen (#17)`.

### Task 7: E2E vollständig, Doku

Spec: «E2E» Schritte 6–10, «Sicherheit und Datenschutz» (neue Zeilen), «Akzeptanzkriterien», Klärungen «E2E», «Test ‹Link aus der Tabelle›».

**Files:**
- Modify: `tests/e2e-pilot.mjs` (`ablaufAufnahmen`), `docs/datenschutz.md`, `README.md`, ggf. `tests/test_aufnahmen_routen.py`

- [ ] **Step 1: E2E** `ablaufAufnahmen()` fortsetzen, je Seite `keinUeberlauf` und `keineFehlerSeit` (bei 404-Schritten mit `["status of 404"]`):
  - Runde 1 (nur wenn Tasks 5–6 gebaut): Text in die erste Freitext-Frage tippen, `sende('[value^="aufnahme-"]')` → Pfad endet auf `/aufnahme`; 2 s aufnehmen, speichern → `location.hash === "#frage-…"`, «Gespeichert.», Player an der Frage, getippter Text im Feld (Screenshot `44-aufnahme-frage`). «Aufnahme löschen» → Bestätigung → «Die Aufnahme wurde gelöscht.», kein Player, Text da.
  - Zweite Lehrperson: `fetch` auf die Adresse der Aufnahme der ersten → 404 (**Akzeptanzkriterium**).
  - Auftraggeberin: `fetch("/verwaltung/aufnahmen/{id}")` → 200, `content-type` beginnt mit `audio/`.
  - Erste Lehrperson löscht den gesprochenen Eintrag über die Bestätigung → `fetch` auf die alte Adresse 404; Datei nicht mehr in `${DATEN}aufnahmen/`.
  - Dunkel (390 px): Seite «Frei sprechen» im Zustand «Fertig» (Screenshot `45-aufnahme-dunkel`); 1280 px: Eintrag mit Player (Screenshot `46-aufnahme-desktop`). Wahl-Seite (Screenshot `47-aufnahme-wahl`).
- [ ] **Step 2:** `make e2e` → «… bestanden, 0 fehlgeschlagen»; Screenshots ansehen.
- [ ] **Step 3:** `docs/datenschutz.md`, Tabelle «Welche Daten entstehen»: die zwei Zeilen aus dem Design («Zwischendatei beim Hochladen einer Aufnahme …», «Noch nicht gespeicherte Aufnahme …»), nicht direkt neben der Zeile von #19; Zeile «Sprachaufnahmen» um «Dauer in Sekunden (`aufnahmen.dauer_sekunden`)» ergänzen. Prüfpunkt Metadaten bleibt offen bis nach dem Merge. `README.md`: «Stand» um «Sprachaufnahmen im Tagebuch (und bei Fragen)» ergänzen. `uv run ruff format --check docs/`.
- [ ] **Step 4:** Ist #18 schon auf `main`: Rebase, dann in `tests/test_aufnahmen_routen.py` `test_link_aus_tabelle_spielt_ab` (Aufnahme der Lehrperson, als Auftraggeberin `GET /verwaltung/eintraege/tabelle.csv`, Link der Spalte «Aufnahme» ohne `http://testserver` aufrufen → 200, Body gleich der Datei; ohne Anmeldung → 303).
- [ ] **Step 5:** `make lint test e2e` grün. Commit `test: E2E-Ablauf der Aufnahmen, Doku (#17)`.
- [ ] **Step 6:** Pull Request mit Screenshots, Tabelle der manuellen Prüfliste (Design «Manuelle Prüfliste», alle Felder ☐) und dem Satz, dass das Issue erst mit ausgefüllter Prüfliste geschlossen wird.

## Nach dem Merge (Orchestrator)

- Deploy auf fly.io. Mit Testkonten (keine echten Inhalte) die manuelle Prüfliste aus dem Design auf iPhone (Safari), Android (Chrome) und am Computer abarbeiten, Ergebnis als Tabelle in den Pull Request; zuerst Schritt 4 auf dem iPhone (Abspielen und Spulen mit `no-store`). Spielt Safari nicht ab: Ausweichlösung `Cache-Control` nach den Klärungen, erst nach dem Merge von #19, als eigener kleiner Pull Request.
- Metadaten: je eine Datei von iPhone, Android und Computer per `fly ssh console` (als `appuser`) prüfen (`strings … | grep -i -E "gps|lat|lon|iphone|model|serial"`, bei MP4 Boxen `udta`/`meta`), Ergebnis in `docs/datenschutz.md`, Tabelle «Prüfung der Datensparsamkeit» (Zeile «Aufnahmen ohne Zusatzangaben»), eigener Commit `docs: Metadaten der Aufnahmen geprueft (#17)`.
- Einmalig: eine Aufnahme bis 10:00 laufen lassen → stoppt selbst, Speichern klappt.
- Testkonten löschen (nimmt ihre Aufnahmen mit), Ordner `/data/aufnahmen/` danach leer bzw. nur echte Aufnahmen.
- Für den Testlauf der Auftraggeberin (bis Fr 20.11.): Schritte 1–4 und 6 auf einem Schulgerät im Schul-WLAN; Wiedergabe ihrer Geräte nach Design. Klappt das Mikrofon dort nicht: Befund für Koschi und die Auftraggeberin.
- Issue #17 erst schliessen, wenn die Prüfliste ausgefüllt ist; sonst offen lassen und die fehlenden Geräte im Issue nennen.
