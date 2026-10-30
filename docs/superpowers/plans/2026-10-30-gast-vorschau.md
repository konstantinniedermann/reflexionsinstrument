# Gast-Ansicht und Vorschau — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Auftraggeberin sieht in der Vorschau an einem gewählten Tag, was eine Lehrperson sieht (auch vor dem Datum einer Runde). Gäste sehen über «Ansehen ohne Konto» die schon freigeschalteten Inhalte. In beiden Ansichten wird nichts gespeichert, nachweislich.

**Architecture:** Keine eigenen Seiten. `app/routen/ohne_speichern.py` hängt die gemeinsamen Seiten von #16 (`VORLAGEN`, `kontext_*`) an einen Router, mit lesender Datenbankverbindung (`PRAGMA query_only`). Ein POST prüft wie bei der Lehrperson und zeigt die Seite mit den Eingaben. `gast.py` (`/gast`, ohne Anmeldung) und `verwaltung_vorschau.py` (`/verwaltung/vorschau`, Tag im Pfad) unterscheiden sich nur im `Ansicht`-Objekt und in der Meldung.

**Tech Stack:** Python 3.13, FastAPI 0.162, Starlette 1.10, Jinja2, sqlite3, pytest, Node-E2E über CDP. Kein JavaScript in der App.

**Spec:** `docs/superpowers/specs/2026-10-30-gast-vorschau-design.md`, verbindlich mit dem Schlussabschnitt «Klärungen nach dem Builder-Check (Claude)». Dazu die Bausteine aus `docs/superpowers/specs/2026-10-30-lehrpersonen-ansicht-design.md` («Gemeinsame Darstellung», «Gemeinsame Bausteine», «Übergabe an #19»). Texte der Oberfläche stehen im Design; der Plan wiederholt nur, was Tests exakt prüfen.

## Vorbereitung (vor Task 1, Orchestrator)

- Branch `feat/19-gast-vorschau` von `main`, nachdem #16 gemergt ist.
- **Schnittstellen aus #16 prüfen** (weicht etwas ab, betroffene Task anpassen und die Abweichung in den Klärungen des Designs nachführen):
  1. `app/ansicht.py`: `Ansicht(modus, stichtag, basis, konto_id, band=None, ausgang=None)`, `.speichert`, `.zeigt_eintraege`, `.url(pfad)`; `fuer_gast(heute, band, ausgang)` (`basis="/gast"`), `fuer_vorschau(stichtag, band, ausgang)` (`basis=f"/verwaltung/vorschau/{stichtag.isoformat()}"`).
  2. `app/seiten_lehrperson.py`: `kontext_start(db, ansicht)`, `kontext_info(db, ansicht)`, `kontext_runde(db, ansicht, runde_id, eingaben=None, fehler=None, meldung=None)`, `kontext_tagebuch_wahl(db, ansicht)`, `kontext_tagebuch_neu(db, ansicht, art, bezug_id=None, text=None, fehler=None, meldung=None)` (`art` ∈ `frei`, `impuls`, `leitfragen`; 404 bei unsichtbarem bzw. unbekanntem Bezug); `VORLAGEN` mit den Schlüsseln `start`, `info`, `runde`, `tagebuch_wahl`, `tagebuch_neu`.
  3. `app/sichtbar.py`: `sichtbare_runde(db, runde_id, stichtag)`. `app/eintraege.py`: `lies_runden_eingaben(fragen, formular)`, `lies_tagebuchtext(text, pflicht=True)`, beide werfen `eingaben.InhaltFehler(feld, meldung)`. `app/inhalte.py`: `fragen(db, runde_id)`, `runden(db)`, `lies_projektstart(db)`.
  4. Templates von #16: `csrf_feld` in jedem Formular, auch im Gast-Modus; Formular-`action` über `ansicht.url`; `ansicht.band | formatiert` mit `role="note"`; `ansicht.ausgang` als Link im Kopf.
  5. `app/routen/gast.py`, `app/routen/verwaltung_vorschau.py`: je `router = APIRouter()`, leer, in `erstelle_app` ohne `prefix` eingebunden. `app/groesse.py` begrenzt Anfragen auf 1 MiB.
  6. `tests/testdaten.py`: `lege_runde_an(db, titel, freischaltdatum, fragen, fallbeispiel) -> (rid, [fids])`, `lege_impuls_an`, `lege_leitfrage_an`, `lege_antwort_an`, `lege_eintrag_an`, `lege_aufnahme_an(db, konto_id, verzeichnis, dauer_sekunden=5)`, `abzug(db)`. `tests/conftest.py`: Fixture `heute_ist(client)`; Helfer `anmelden`, `csrf_von(client, pfad="/")`, `als_leitung`, `als_lehrperson`.
  7. `app/templates/verwaltung/start.html` und `rahmen.html`: Kommentarzeilen `{# #19: Link Vorschau #}` bzw. `{# #19: Navigation Vorschau #}` mit der Trennzeile davor. `app/static/css/style.css`: Abschnitt `/* Pilot: Gast und Vorschau (#19) */` … `/* Ende #19 */`. `tests/e2e-pilot.mjs`: leere Funktion `ablaufGast`, schon aufgerufen.
  8. **`tests/test_geruest.py` von #16 muss nach #19 weiter gelten** (Bedarf an #16): kein Test verlangt `gast.router.routes == []` oder `verwaltung_vorschau.router.routes == []`, und `/verwaltung` wird nicht auf «zweimal folgt» geprüft. Fehlt das, gibt der Orchestrator es an #16 zurück. #19 ändert `test_geruest.py` nicht.

## Global Constraints

- Keine neuen Dependencies, keine Migration, keine Änderung an `app/main.py`, an Templates von #16 (`app/templates/lehrperson/…`), an `app/ansicht.py`, `seiten_lehrperson.py`, `sichtbar.py`, `eintraege.py`, `texte.py`, `tests/conftest.py`, `tests/testdaten.py`, `tests/test_geruest.py`, `README.md`.
- Verwaltung nur an den vorbereiteten Plätzen: in `start.html` und `rahmen.html` den Block bzw. die Zeile **unter** `{# #19: … #}` ersetzen; Kommentarzeile und Trennzeile bleiben. In den Templates der Eingabemaske nur die drei Zeilen `{# #19: Vorschau-Link #}` ersetzen.
- CSS nur im Abschnitt `/* Pilot: Gast und Vorschau (#19) */`. E2E nur in der Funktion `ablaufGast`.
- Kein Inline-JavaScript, kein `style=`, keine `on…=`-Attribute. Kein JavaScript für Gast und Vorschau.
- Gast- und Vorschau-Routen holen die Datenbank nur über `hole_db_lesend`. Sie rufen nie eine Funktion auf, die schreibt, und nie `aktuelles_konto` (Gast).
- Sichtbarkeit nur über `kontext_*` und `sichtbar.py`, nie eigenes SQL auf `freischaltdatum` oder `sichtbar_ab`. Datum in Gast-Routen nur über `Depends(hole_heute)`.
- Jede POST-Route `dependencies=[Depends(pruefe_csrf)]`. Pfad-IDs `Id` aus `app/typen.py`, Formularfelder aus `await request.form()`.
- Bezeichner, Kommentare und Texte auf Deutsch, ohne ß; Anrede «du», keine Emojis. Repo öffentlich: Testdaten erfunden und neutral.
- Commits: Präfix `feat:`/`test:`/`docs:`/`fix:`, `(#19)` am Ende der ersten Zeile, Umlaute in der Commit-Zeile ausgeschrieben, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy9PjCyPCUAHE1BBLBG`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber. Der Ruff-Hook entfernt ungenutzte Imports zwischen Edits, deshalb Import und Verwendung im selben Edit schreiben.

## Review Focus

1. **Lehrperson mit abgelaufener Anmeldung tippt als Gast einen langen Eintrag:** Der Text steht nach «Speichern» noch im Feld (200), auch mit 20 000 Zeichen und vielen Umlauten (nicht 413). In der Datenbank landet nichts. (Task 4 `test_gast_langer_text_bleibt_stehen`)
2. **Formular, das veraltet ist oder einen Tag zu früh abgeschickt wird:** POST auf eine Runde oder einen Impuls, die am Stichtag nicht sichtbar sind, ergibt 404, nie 500 (lesende Verbindung) und nie 400. (Task 2 `test_post_runde_nicht_sichtbar_404`, Task 4 `test_gast_nicht_freigeschaltet`)
3. **Angemeldete Person öffnet `/gast`:** Die Sitzung bleibt unberührt (kein `Set-Cookie: sitzung`), kein Name auf der Seite, danach weiterhin angemeldet. (Task 4 `test_gast_sitzung_unberuehrt`)
4. **Datum der Runde nachträglich geändert:** «Diese Runde ansehen» folgt immer dem aktuellen Freischaltdatum. (Task 3 `test_links_in_verwaltung`)
5. **Unerwartete Datumsformen in Adresse und Abfrage** (`2026-02-30`, Zeilenumbruch am Ende, 50 Ziffern, Jahr ausserhalb 2020–2099): 404 bzw. die Auswahlseite, nie 500. (Task 1 `test_vorschau_ungueltiges_datum`, Task 3 `test_auswahl_weiterleitungen`)

---

### Task 1: Lesende Verbindung, gemeinsame Seiten, Vorschau an einem Tag (GET)

Spec: «Darstellung über die Bausteine aus #16», «Nur lesende Datenbankverbindung», «Vorschau: Tag wählen», «Band der Vorschau», Klärungen «Gemeinsamer Code», «Lesende Verbindung», «Datum der Vorschau», «Band ohne Woche».

**Files:**
- Create: `app/routen/ohne_speichern.py`, `tests/test_ohne_speichern.py`, `tests/test_vorschau.py`
- Modify: `app/routen/verwaltung_vorschau.py`

**Interfaces:**
- Produces (`app/routen/ohne_speichern.py`):
  - `def hole_db_lesend(db: Annotated[sqlite3.Connection, Depends(hole_db)]) -> sqlite3.Connection` (führt `PRAGMA query_only = ON` aus, gibt `db` zurück); `DB_LESEND = Annotated[sqlite3.Connection, Depends(hole_db_lesend)]`.
  - `MELDUNG_GAST = "Nicht gespeichert. In der Ansicht ohne Konto wird nichts gespeichert."`, `MELDUNG_VORSCHAU = "Nicht gespeichert. In der Vorschau wird nichts gespeichert."`.
  - `def registriere_seiten(router: APIRouter, hole_ansicht: Callable[..., Ansicht], meldung: str) -> None`. In dieser Task nur die GET-Routen: `""` (`start`), `"/info"`, `"/runden/{runde_id}"`, `"/tagebuch/neu"` (`tagebuch_wahl`), `"/tagebuch/neu/frei"`, `"/tagebuch/neu/impuls/{impuls_id}"`, `"/tagebuch/neu/leitfrage/{leitfrage_id}"` (`tagebuch_neu` mit `art` `frei`, `impuls`, `leitfragen`). Jede Route ist `templates.TemplateResponse(request, VORLAGEN[…], kontext_…(db, ansicht, …))` mit `ansicht: Annotated[Ansicht, Depends(hole_ansicht)]` und `db: DB_LESEND`.
- Produces (`app/routen/verwaltung_vorschau.py`):
  - `router = APIRouter(prefix="/verwaltung/vorschau", dependencies=[Depends(braucht_auftraggeberin)])`, `AUSGANG = ("Vorschau beenden", "/verwaltung/vorschau")`.
  - `def band_vorschau(stichtag: date, projektstart: date | None, offen: list[str]) -> str`: `"Vorschau: So sieht es eine Lehrperson am {datum_kurz(stichtag)}[ (Woche N)]. Es wird nichts gespeichert."`, bei `offen` zusätzlich `"\nNoch Vorschläge statt deiner Texte: " + ", ".join(offen) + "."`.
  - `def hole_ansicht_vorschau(am: str, db: DB_LESEND) -> Ansicht`: `lies_datum(am)` und `ist_plausibel`, sonst `HTTPException(404)`; `offen` = `bezeichnung` jedes Eintrags aus `REGISTER`, dessen `lies_textstand(db, k).bestaetigt` falsch ist; `fuer_vorschau(stichtag, band_vorschau(…), AUSGANG)`.
  - Unter-Router `seiten = APIRouter(prefix="/{am}")`, `registriere_seiten(seiten, hole_ansicht_vorschau, MELDUNG_VORSCHAU)`, danach `router.include_router(seiten)`.

- [ ] **Step 1: Failing tests** `tests/test_ohne_speichern.py`:
  - `test_hole_db_lesend_verbietet_schreiben(einstellungen, client)`: `conn = verbinde(einstellungen.db_pfad)`; `hole_db_lesend(conn)`; `SELECT COUNT(*) FROM runden` geht; `INSERT INTO einstellungen (schluessel, wert) VALUES ('x', 'y')` → `sqlite3.OperationalError`; Zeile fehlt danach (neue Verbindung).
  - `test_seiten_nutzen_lesende_verbindung(einstellungen)`: alle `APIRoute` aus `iter_route_contexts(erstelle_app(einstellungen).routes)`, deren Pfad mit `/gast` oder `/verwaltung/vorschau` beginnt; die Liste ist nicht leer; im Abhängigkeitsbaum (`route.dependant`, rekursiv über `.dependencies`, `.call`) jeder Route steht `hole_db_lesend`.
- [ ] **Step 2: Failing tests** `tests/test_vorschau.py` (als Auftraggeberin über `als_leitung`, Daten über `testdaten`, erster Tag per `INSERT INTO einstellungen (schluessel, wert) VALUES ('projektstart', '2026-11-23')`, `heute_ist(date(2026, 11, 16))`):
  - `test_band_vorschau`: `band_vorschau(date(2026, 11, 30), date(2026, 11, 23), []) == "Vorschau: So sieht es eine Lehrperson am Mo 30.11.2026 (Woche 2). Es wird nichts gespeichert."`; mit `projektstart=None` und mit `date(2026, 12, 1)` kein `"(Woche"`; mit `["Begrüssung", "Hinweis im Tagebuch"]` endet er auf `"\nNoch Vorschläge statt deiner Texte: Begrüssung, Hinweis im Tagebuch."`.
  - `test_vorschau_start_am_tag`: «Runde Eins» 23.11., «Runde Zwei» 07.12. → `GET /verwaltung/vorschau/2026-11-30`: 200, «Woche 2», «Runde Eins», «Nächste Runde ab Mo 07.12.», «Runde Zwei» nicht im Text, «Willkommen»; `…/2026-12-07`: beide Titel, «Woche 3».
  - `test_vorschau_aktueller_impuls`: «Impuls A» 23.11., «Impuls B» 07.12. → am 30.11. «Impuls A», nicht «Impuls B»; am 07.12. «Impuls B».
  - `test_vorschau_kuenftige_runde`: Runde am 07.12. mit Fallbeispiel «Fall Zwei» und «Frage A» → `…/2026-12-07/runden/{rid}` 200 mit beiden; `…/2026-12-06/runden/{rid}` → 404.
  - `test_vorschau_seiten`: am 07.12. `…/info`, `…/tagebuch/neu`, `…/tagebuch/neu/frei`, `…/tagebuch/neu/impuls/{iid}`, `…/tagebuch/neu/leitfrage/{lid}` → 200; Impuls vom 14.12. → 404; Leitfrage `999` → 404.
  - `test_vorschau_ungueltiges_datum` (parametrisiert `"2026-13-01"`, `"2026-02-30"`, `"abc"`, `"20261130"`, `"2026-11-30%0A"`, `"1" * 50`, `"2019-12-31"`, `"2100-01-01"`): `GET /verwaltung/vorschau/{x}` und `…/{x}/info` → 404.
  - `test_vorschau_links_tragen_tag`: auf `…/2026-11-30` und `…/2026-11-30/runden/{rid}` ist jedes `href`/`action` (Regex `(?:href|action)="([^"]*)"`) entweder `/verwaltung/vorschau`, `/abmelden`, beginnt mit `/static/` oder mit `/verwaltung/vorschau/2026-11-30`; keines beginnt mit `/lehrperson` oder `/gast`; das Formular der Runde hat `action="/verwaltung/vorschau/2026-11-30/runden/{rid}"`.
  - `test_vorschau_band_und_ausgang`: Seite enthält «Vorschau: So sieht es eine Lehrperson am Mo 30.11.2026 (Woche 2).», «Noch Vorschläge statt deiner Texte: Begrüssung, Hinweis im Tagebuch, Wer sieht was» und einen Link `href="/verwaltung/vorschau"` mit «Vorschau beenden»; nach `texte.speichere_text(db, k, "Text")` für alle `REGISTER`-Schlüssel fehlt «Noch Vorschläge».
  - `test_vorschau_nur_auftraggeberin(client, lehrperson, …)`: ohne Anmeldung `…/2026-11-30` → 303 auf `/`; als Lehrperson → 403.
- [ ] **Step 3:** `uv run pytest tests/test_ohne_speichern.py tests/test_vorschau.py -v` → FAIL.
- [ ] **Step 4:** implementieren.
- [ ] **Step 5:** `uv run pytest -v` → PASS (auch das Routen-Inventar: Vorschau-Pfade beginnen mit `/verwaltung`, `{am}` wird zu `1`, die Anmeldeprüfung läuft vor dem Datum), Lint.
- [ ] **Step 6:** Commit `feat: Vorschau an einem gewaehlten Tag, lesende Verbindung (#19)`.

### Task 2: Formulare prüfen, nichts speichern (POST)

Spec: «Formulare: POST auf eine Route, die nichts speichert», Klärungen «Reihenfolge bei POST», «Antwort beim Gast-POST».

**Files:**
- Modify: `app/routen/ohne_speichern.py`, `tests/test_vorschau.py`

**Interfaces:**
- Consumes: Task 1 (`registriere_seiten`, `DB_LESEND`, `MELDUNG_VORSCHAU`), #16 (`sichtbare_runde`, `inhalte.fragen`, `lies_runden_eingaben`, `lies_tagebuchtext`, `InhaltFehler`).
- Produces: in `registriere_seiten` vier `async` POST-Routen mit `dependencies=[Depends(pruefe_csrf)]`: `"/runden/{runde_id}"`, `"/tagebuch/neu/frei"`, `"/tagebuch/neu/impuls/{impuls_id}"`, `"/tagebuch/neu/leitfrage/{leitfrage_id}"`. Ablauf Runde: `sichtbare_runde(db, runde_id, ansicht.stichtag)` → sonst 404; `formular = dict(await request.form())`; `lies_runden_eingaben(fragen(db, runde_id), formular)`; Erfolg → `kontext_runde(…, eingaben=formular, meldung=meldung)`, 200; `InhaltFehler e` → `kontext_runde(…, eingaben=formular, fehler={e.feld: e.meldung})`, 400. Tagebuch: `text = formular.get("text", "")`; `lies_tagebuchtext(text)`; Erfolg → `kontext_tagebuch_neu(…, text=text, meldung=meldung)`, 200; Fehler → `…, text=text, fehler={e.feld: e.meldung}`, 400 (der 404 für den Bezug kommt aus `kontext_tagebuch_neu`). `anker` wird ignoriert.

- [ ] **Step 1: Failing tests** `tests/test_vorschau.py` (Runde `rid` am 07.12. mit `f1` Freitext, `f2` Skala; `csrf = csrf_von(client, f"/verwaltung/vorschau/2026-12-07/runden/{rid}")`; vorher `testdaten.abzug(db)`):
  - `test_post_runde_speichert_nichts`: `antwort_{f1}="Mein Text"`, `antwort_{f2}="4"` → 200, `MELDUNG_VORSCHAU` in einem Element mit `role="status"`, «Mein Text» im `textarea`, Radio `value="4"` mit `checked`; `abzug` unverändert.
  - `test_post_runde_ungueltig_400`: `antwort_{f2}="7"` → 400, «Bitte einen Wert von 1 bis 5 wählen.», `MELDUNG_VORSCHAU` nicht im Text; `antwort_{f1}="x" * 20_001` → 400 mit «höchstens 20 000 Zeichen»; `abzug` unverändert.
  - `test_post_runde_nicht_sichtbar_404` (Review Focus 2): dieselbe Runde unter `…/2026-12-06/…` → 404; unbekannte Runde `999` → 404; `abzug` unverändert.
  - `test_post_ohne_csrf_403`: ohne `csrf` auf Runde `999` → 403 «Formular abgelaufen».
  - `test_post_tagebuch`: `…/tagebuch/neu/frei` mit `text="Notiz"` → 200, Meldung, «Notiz» im Feld; `text=" "` → 400 «Der Eintrag ist noch leer.»; Impuls vom 14.12. mit `text="x"` und mit `text=""` → je 404; Leitfrage `999` → 404; `abzug` unverändert.
  - `test_post_escapt`: `text="<script>x</script> **f**"` → `&lt;script&gt;x&lt;/script&gt;` und `**f**` im Text, kein `<script>x`, kein `<strong>f`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` PASS (Routen-Inventar: Vorschau-POSTs ohne CSRF 403, ohne Anmeldung 303), Lint.
- [ ] **Step 5:** Commit `feat: Formulare in der Vorschau pruefen ohne zu speichern (#19)`.

### Task 3: Auswahlseite und Links aus der Verwaltung

Spec: «Auswahlseite `/verwaltung/vorschau`», «Standardtag», «Vorschau-Links in der Eingabemaske», Klärungen «Abfrage auf der Auswahlseite», «Liste der Tage», «Navigation der Verwaltung».

**Files:**
- Create: `app/templates/verwaltung/vorschau.html`
- Modify: `app/routen/verwaltung_vorschau.py`, `app/templates/verwaltung/start.html`, `…/rahmen.html`, `…/inhalte/uebersicht.html`, `…/inhalte/info.html`, `…/inhalte/runde.html`, `app/static/css/style.css`, `tests/test_vorschau.py`

**Interfaces:**
- Produces (`app/routen/verwaltung_vorschau.py`):
  - `def standardtag(heute: date, projektstart: date | None) -> date` (der spätere der beiden; ohne erster Tag `heute`).
  - `@dataclass(frozen=True) class VorschauTag: datum: date; ist_heute: bool; woche: int | None; titel: list[str]`.
  - `def vorschau_tage(runden: Sequence[Mapping[str, Any]], heute: date, projektstart: date | None) -> list[VorschauTag]` (liest `titel`, `freischaltdatum`; Regeln aus der Klärung «Liste der Tage»).
  - `ZIELE = {"info": "/info"}`; `GET ""` mit `am: str = ""`, `ziel: str = ""` (Query), `heute` über `hole_heute`, `db: DB_LESEND`: Weiterleitungen nach der Klärung, sonst `verwaltung/vorschau.html` mit `tage`.
- Template: Inhalt nach Spec; Karten-Text `"Heute, {datum}"` bzw. `"Woche N, ab {datum}"` / `"Ab {datum}"`, danach `": " + titel | join(" · ")`, falls Titel; Formular `method="get" action="/verwaltung/vorschau"` mit `<input type="date" name="am" required min="2020-01-01" max="2099-12-31">`.
- Links: `start.html` Karte `<a class="karte karte--link" href="/verwaltung/vorschau">` mit «Vorschau» und Unterzeile «So sieht es eine Lehrperson an einem bestimmten Tag.»; `rahmen.html` `<a href="/verwaltung/vorschau">Vorschau</a>`; Eingabemaske nach der Tabelle der Spec, Runde mit `href="/verwaltung/vorschau/{{ runde.freischaltdatum }}/runden/{{ runde.id }}"`.
- CSS (eigener Abschnitt): `.verwaltungsnavigation { flex-wrap: wrap; }`, Gestaltung der Auswahlseite nur mit eigenen Klassen.

- [ ] **Step 1: Failing tests** `tests/test_vorschau.py`:
  - `test_standardtag`: `(16.11., 23.11.)` → 23.11.; `(01.12., 23.11.)` → 01.12.; `(16.11., None)` → 16.11.
  - `test_vorschau_tage`: Runden D 16.11., A 23.11., B 23.11., C 30.11., E 09.11.; heute 16.11.; erster Tag 23.11. → `[VorschauTag(09.11., False, None, ["E"]), VorschauTag(16.11., True, None, ["D"]), VorschauTag(23.11., False, 1, ["A", "B"]), VorschauTag(30.11., False, 2, ["C"])]`; ohne Runden → `[VorschauTag(16.11., True, None, [])]`.
  - `test_auswahlseite`: `h1` «Vorschau»; Link `href="/verwaltung/vorschau/2026-11-16"` mit «Heute, Mo 16.11.2026»; Link `…/2026-11-23` mit «Woche 1, ab Mo 23.11.2026: Runde Eins · Runde Zwei»; `name="am"` mit `required`; Link `href="/gast"`; «Diese Ansicht ist öffentlich»; Link `href="/verwaltung"` mit «‹ Verwaltung».
  - `test_auswahl_weiterleitungen` (Review Focus 5): `?am=2026-11-30` → 303 `/verwaltung/vorschau/2026-11-30`; `?am=2026-11-30&ziel=info` → `…/2026-11-30/info`; `?ziel=info` → `…/2026-11-23/info` (heute 16.11., erster Tag 23.11.); `?ziel=x`, `?am=abc`, `?am=2026-02-30`, `?am=2019-01-01`, `?am=` → 200 mit «Vorschau».
  - `test_links_in_verwaltung` (Review Focus 4): auf `/verwaltung` tragen die Karte «Vorschau» (`a.karte--link`) und die Navigation (`nav.verwaltungsnavigation`) je `href="/verwaltung/vorschau"`; `/verwaltung/inhalte` enthält einen Link `href="/verwaltung/vorschau"` mit «So sieht es eine Lehrperson»; `/verwaltung/inhalte/info` `href="/verwaltung/vorschau?ziel=info"`; `/verwaltung/inhalte/runden/{rid}` `href="/verwaltung/vorschau/2026-12-07/runden/{rid}"` mit «Diese Runde ansehen»; nach `UPDATE runden SET freischaltdatum = '2026-12-14'` zeigt der Link auf `…/2026-12-14/runden/{rid}`.
  - `test_kommentarzeilen_bleiben`: `start.html` und `rahmen.html` enthalten weiterhin `{# #19:` und die Trennzeile.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** `uv run pytest -v` PASS, Lint. `make dev`, Verwaltung und Auswahlseite in 390 px ansehen.
- [ ] **Step 5:** Commit `feat: Auswahlseite der Vorschau und Links aus der Verwaltung (#19)`.

### Task 4: Gast-Ansicht mit Nachweisen

Spec: «Gast», «Nur freigeschaltete Inhalte, keine Einträge», «Sitzung und Cookies im Gast-Modus», «Sicherheit und Datenschutz», «Routen-Inventar», «Prüfung und Nachweis» (Gast).

**Files:**
- Create: `tests/test_gast.py`
- Modify: `app/routen/gast.py`, `tests/test_routen_inventar.py`

**Interfaces:**
- Consumes: Task 1–2 (`registriere_seiten`, `DB_LESEND`, `MELDUNG_GAST`).
- Produces (`app/routen/gast.py`): `router = APIRouter(prefix="/gast")` (ohne `dependencies`), `AUSGANG = ("Anmelden", "/")`, `def hole_ansicht_gast(db: DB_LESEND, heute: Annotated[date, Depends(hole_heute)]) -> Ansicht` (`fuer_gast(heute, lies_text(db, "hinweis_gast"), AUSGANG)`), `registriere_seiten(router, hole_ansicht_gast, MELDUNG_GAST)`.
- Produces (`tests/test_routen_inventar.py`): `GAST_GET`, `GAST_POST`, `OEFFENTLICH`, `OHNE_SITZUNG` und der Kommentar wörtlich aus der Spec «Routen-Inventar»; neuer Test `test_gast_liste_deckt_sich_mit_den_routen`.

- [ ] **Step 1: Failing tests** `tests/test_gast.py`. Fixture `inhalte(db, einstellungen, lehrperson, heute_ist)` gibt ein Dict zurück: `heute_ist(date(2026, 11, 24))`; Runde «Runde Offen» 23.11. (Fallbeispiel «Fall Offen», `f1` Freitext, `f2` Skala), «Runde Geheim» 30.11.; Impulse «Impuls Offen» 23.11., «Impuls Geheim» 30.11.; Leitfrage «Leitfrage Eins»; Infoblock-Abschnitt «Abschnitt Eins» (SQL); von der Lehrperson Antwort «Antwort Geheim» auf `f1`, Einträge `frei` («Eintrag Geheim»), `impuls`, `leitfragen`, `aufnahme` mit `testdaten.lege_aufnahme_an(db, …, einstellungen.aufnahmen_verzeichnis)`. Die Liste `GAST_SEITEN` enthält alle sieben GET-Adressen mit den IDs aus `inhalte`.
  - `test_gast_seiten_ohne_anmeldung`: jede Seite 200; enthält «Ansicht ohne Speichern.» (Vorschlag von `hinweis_gast`) und einen Link `href="/"` mit «Anmelden»; `/gast` enthält «Willkommen», «Runde Offen», «Impuls Offen».
  - `test_gast_nicht_freigeschaltet` (**Akzeptanzkriterium**, Review Focus 2): «Runde Geheim» weder in `/gast` noch auf einer anderen Gast-Seite, aber «Nächste Runde ab Mo 30.11.»; `GET` und `POST` (gültiges `csrf`, `antwort_…`) `/gast/runden/{geheim}` → 404; «Impuls Geheim» fehlt auf `/gast` und `/gast/tagebuch/neu`; `GET`/`POST …/neu/impuls/{geheim}` → 404; nach `heute_ist(date(2026, 11, 30))` `GET /gast/runden/{geheim}` → 200.
  - `test_gast_zeigt_keine_eintraege`: auf keiner Gast-Seite «Antwort Geheim», «Eintrag Geheim», «Anna Beispiel», `/aufnahmen/`, «Abmelden», `data-entwurf`; das `textarea` von `f1` auf `/gast/runden/{offen}` ist leer.
  - `test_gast_kein_weg_zu_eintraegen` (**Akzeptanzkriterium**): Breitensuche ab `/gast` über alle `href`/`action` (Regex aus Task 1), die mit `/gast` beginnen. Jeder gefundene Wert ist `/`, beginnt mit `/gast` oder `/static/` und enthält weder `/lehrperson` noch `/verwaltung`, `/eintraege` oder `/aufnahmen`. Besucht sind mindestens `/gast`, `/gast/info`, `/gast/runden/{offen}`, `/gast/tagebuch/neu`, `/gast/tagebuch/neu/frei`. `GET /gast/eintraege`, `/gast/tagebuch/1`, `/gast/tagebuch/1/loeschen`, `/gast/aufnahmen/1` → 404.
  - `test_gast_speichern_verworfen`: POST `/gast/runden/{offen}` mit `csrf_von(client, "/gast")`, `antwort_{f1}="Mein Text"`, `antwort_{f2}="3"` → 200, `MELDUNG_GAST` mit `role="status"`, «Mein Text» im Feld, Radio 3 `checked`; `antwort_{f2}="7"` → 400; `<script>` im Text erscheint escapt; `/gast/tagebuch/neu/leitfrage/{lid}` mit `text="Notiz"` → 200 mit Meldung.
  - `test_gast_langer_text_bleibt_stehen` (Review Focus 1): `/gast/tagebuch/neu/frei` mit `text=("Schöne Grüsse, äöü. " * 1000)` → 200, `MELDUNG_GAST`, «Schöne Grüsse» im `textarea`; `abzug` unverändert.
  - `test_gast_datenbank_unveraendert` (**Akzeptanzkriterium**): `vorher = testdaten.abzug(db)`, `ordner = sorted(p.name for p in einstellungen.aufnahmen_verzeichnis.iterdir())`. Durchgang ohne Anmeldung: alle `GAST_SEITEN`; jeder der vier POSTs mit gültigen Werten, mit ungültigen (Skala `7`, Text `"x" * 20_001`), ohne `csrf`; POST auf «Runde Geheim» und «Impuls Geheim». Danach `abzug` und Ordner gleich. Zweiter Durchgang nach `anmelden(…lehrperson…)`, mit neuem `vorher` nach dem Anmelden, gleiche Prüfung.
  - `test_gast_sitzung_unberuehrt` (Review Focus 3): `anmelden(client, lehrperson…)`; `GET /gast` → in `antwort.headers.get_list("set-cookie")` kein Eintrag, der mit `sitzung=` beginnt; «Anna Beispiel» nicht im Text; danach `GET /lehrperson` → 200.
- [ ] **Step 2: Failing tests** `tests/test_routen_inventar.py`: Mengen und Kommentar aus der Spec übernehmen. `test_gast_liste_deckt_sich_mit_den_routen(einstellungen)`: `{p for p in inventar(einstellungen, "GET") if p.startswith("/gast")} == GAST_GET`, ebenso POST mit `GAST_POST`.
- [ ] **Step 3:** FAIL. **Step 4:** implementieren. **Step 5:** `uv run pytest -v` PASS (alle Inventar-Tests, insbesondere `test_post_routen_brauchen_csrf` mit den Gast-POSTs ohne Sitzung), Lint.
- [ ] **Step 6:** Commit `feat: Gast-Ansicht ohne Konto, nur lesend (#19)`.

### Task 5: Knopf auf der Login-Seite, Suchmaschinen, Datenschutz-Doku

Spec: «Knopf «Ansehen ohne Konto» auf der Login-Seite», «Suchmaschinen», «Sicherheit und Datenschutz» (Doku), Klärungen «`app/texte.py` bleibt unverändert», «Neue Zeile in `docs/datenschutz.md`».

**Files:**
- Modify: `app/templates/anmelden.html` (nur `{% block gast %}`), `app/sicherheit.py`, `tests/test_sicherheit.py`, `docs/datenschutz.md`, `app/static/css/style.css`, `tests/test_gast.py`

**Interfaces:**
- Produces: `sicherheits_header(…)` enthält `"X-Robots-Tag": "noindex, nofollow"`. Login-Karte nach Spec (Link `class="knopf knopf--zweit" href="/gast"`).
- Doku: in «Prüfung der Datensparsamkeit» direkt **nach «Kein Tracking»** die Zeile `| Gast-Ansicht speichert nichts | Kein Login, kein eigenes Cookie, Datenbank nur lesend; Eingaben werden geprüft und verworfen | Test test_gast_datenbank_unveraendert |` (Testname in Backticks). Bei `hinweis_gast` lautet «Wo er erscheint»: «Gast-Ansicht («Ansehen ohne Konto», #19): als Band oben auf jeder Seite».

- [ ] **Step 1: Failing tests:**
  - `tests/test_gast.py::test_login_zeigt_gast_knopf(client)`: `GET /` enthält `href="/gast"`, «Ansehen ohne Konto», «Ohne Anmeldung. Es wird nichts gespeichert.»
  - `tests/test_sicherheit.py::test_robots_header(client)`: `/`, `/gast`, `/gibt-es-nicht` → `x-robots-tag == "noindex, nofollow"`.
  - `tests/test_gast.py::test_datenschutz_nennt_gast_ansicht`: `docs/datenschutz.md` enthält «Gast-Ansicht speichert nichts» und `test_gast_datenbank_unveraendert`; die Zeile von `hinweis_gast` enthält nicht mehr «als Meldung statt einer Bestätigung».
- [ ] **Step 2:** FAIL. **Step 3:** implementieren (CSS für die Gast-Karte im eigenen Abschnitt). **Step 4:** `uv run pytest -v` PASS, Lint, `uv run ruff format --check docs/`.
- [ ] **Step 5:** Commit `feat: Knopf Ansehen ohne Konto, noindex, Datenschutz-Doku (#19)`.

### Task 6: E2E-Ablauf Gast und Vorschau, Design nachführen

Spec: «Prüfung und Nachweis» (E2E), Klärung «E2E-Ausgangslage».

**Files:**
- Modify: `tests/e2e-pilot.mjs` (nur Funktion `ablaufGast`), `docs/superpowers/specs/2026-10-30-gast-vorschau-design.md` (Abweichungen in den Klärungen nachführen)

**Interfaces:**
- Consumes: Platzhalter aus `tests/platzhalter/inhalte.json` (frische Datenbank: Runden 1–4 an heute + 0/7/14/21, Titel aus der Datei lesen), Helfer des Skripts (`muss`, `pruefe`, `oeffne`, `tippe`, `sende`, `klick`, `text`, `js`, `pfad`, `ueberschrift`, `keinUeberlauf`, `merke`, `keineFehlerSeit`, `screenshot`, `handy`, `desktop`, `farbschema`, `cdp`). Heute in Zürich: `new Intl.DateTimeFormat("sv-SE", { timeZone: "Europe/Zurich" }).format(new Date())`, Tage dazu über `Date.UTC`.

- [ ] **Step 1:** `ablaufGast()`:
  0. `cdp("Network.clearBrowserCookies")`; als Auftraggeberin anmelden (`projektleitung`, `PW_AUFTRAGGEBERIN`), auf `/verwaltung/inhalte/allgemein` den ersten Tag auf heute setzen und speichern (`tippe("#projektstart", heute)`), abmelden.
  1. 390 px hell: Login-Seite, Link «Ansehen ohne Konto» sichtbar; `sende("a[href='/gast']")` → `pfad() === "/gast"`.
  2. Gast-Start: Band mit «Ansicht ohne Speichern», «Willkommen», Titel von Runde 1, «Nächste Runde ab», Titel von Runde 2 nicht in `text()`; Navigation mit drei Einträgen (`.tabs a` Anzahl 3); kein «Abmelden».
  3. Runde 1: erste Frage tippen, «Speichern» → «Nicht gespeichert.» sichtbar, Text steht im Feld.
  4. Tagebuch → «Frei schreiben», Text tippen, «Speichern» → Meldung; Infoblock öffnen.
  5. `/gast/runden/2` → `ueberschrift() === "Nicht gefunden"` (**Akzeptanzkriterium**; `keineFehlerSeit` mit `["status of 404"]`).
  6. «Anmelden» im Kopf → `pfad() === "/"`.
  7. Als Auftraggeberin: `/verwaltung` → Karte «Vorschau» → Auswahlseite; Karte mit dem Datum von Runde 3 → Titel von Runde 3 sichtbar, Band mit «Woche 3» und dem Datum. Eingabemaske, Runde 4 (`/verwaltung/inhalte/runden/4`) → «Diese Runde ansehen» → Fragen von Runde 4 sichtbar. «Vorschau beenden» → `pfad() === "/verwaltung/vorschau"`. Abmelden.
  8. Login dunkel (390 px) und Login, Gast-Start, Auswahlseite in 1280 px. Jede besuchte Seite `keinUeberlauf`, jeder Schritt `keineFehlerSeit`.
- [ ] **Step 2:** Screenshots `70-gast-login`, `71-gast-login-dunkel`, `72-gast-login-desktop`, `73-gast-start`, `74-gast-runde-nicht-gespeichert`, `75-gast-nicht-gefunden`, `76-vorschau-auswahl`, `77-vorschau-woche-3`, `78-vorschau-kuenftige-runde`.
- [ ] **Step 3:** `make e2e` → «… bestanden, 0 fehlgeschlagen». Screenshots ansehen: Band lesbar, Gast-Karte auf der Login-Seite zweitrangig, dunkel lesbar, Verwaltungsnavigation ohne Überlauf.
- [ ] **Step 4:** `make lint test e2e` grün. Commit `test: E2E-Ablauf Gast und Vorschau (#19)`.

## Nach dem Merge (Orchestrator)

- Merge-Reihenfolge mit #18 beliebig: `verwaltung/start.html` und `rahmen.html` ändern beide nur an ihren vorbereiteten Plätzen. Nach dem Merge aller drei einmal `make e2e`: Die Verwaltungsnavigation mit fünf Links darf auf 390 px nicht überlaufen (`flex-wrap` aus Task 3).
- README «Stand» um «Gast-Ansicht ohne Konto und Vorschau» ergänzen (zusammen mit #17 und #18, siehe Klärung «README»).
- fly.io nach Spec: Deploy, `/gast` in 390 px öffnen, Band sichtbar; `curl -I https://<app>/gast` zeigt `x-robots-tag: noindex, nofollow` und kein `set-cookie: sitzung`; als Auftraggeberin die Vorschau einmal öffnen. Keine Platzhalter laden. Screenshots aus dem E2E in den Pull Request.
- Hinweis an die Auftraggeberin (Koschi verschickt ihn): Der Link `…/gast` lässt sich an die Dozentin weitergeben. Er zeigt nur, was schon freigeschaltet ist.
