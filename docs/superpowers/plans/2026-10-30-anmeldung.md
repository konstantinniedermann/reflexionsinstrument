# Anmeldung, Rollen und Konten — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Login mit Benutzername und Passwort, Rollen Lehrperson/Auftraggeberin, widerrufbare Sitzungen, CSRF-Schutz, Bremse gegen Durchprobieren, Zugangsverwaltung für die Auftraggeberin und ein Kommando für das erste Konto.

**Architecture:** Fachlogik in kleinen Modulen (`konten`, `anmeldeschutz`, `sitzung`, `csrf`, `cookies`), Routen pro Bereich unter `app/routen/`, eingebunden in `erstelle_app`. Cookies setzt eine reine ASGI-Middleware aus Werten, die Dependencies in `request.state` ablegen. Ein Routen-Inventar-Test erzwingt Anmeldung und CSRF für alle künftigen Routen.

**Tech Stack:** Python 3.13, FastAPI, Jinja2, sqlite3, bcrypt 5, itsdangerous, python-multipart, pytest, Node-E2E über CDP.

**Spec:** `docs/superpowers/specs/2026-10-30-anmeldung-design.md` — vor jeder Task lesen; Werte (Fristen, Grenzen, Texte) stehen dort.

## Global Constraints

- Keine neuen Dependencies. Nur Standardbibliothek plus `bcrypt`, `itsdangerous`, `python-multipart`, `fastapi`, `jinja2`.
- Bezeichner, Kommentare, Texte auf Deutsch, ohne ß; in Bezeichnern Umlaute ausgeschrieben (`ue`, `ae`, `oe`). Oberfläche: «Zugang» statt «Konto», Anrede «du», keine technischen Begriffe.
- Kein Inline-JavaScript, kein Inline-CSS (`style=`), keine externen Ressourcen. Neue CSS-Regeln nur am Ende von `app/static/css/style.css` im Abschnitt `/* Pilot: Anmeldung und Verwaltung */`.
- Keine Migration in diesem Issue (Nummer 002 gehört #15, 003 #16).
- Commits: Präfix `feat:`/`test:`/`docs:`/`refactor:`/`fix:`, `(#14)` am Ende der ersten Zeile, Trailer genau:
  `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>` und `Claude-Session: https://claude.ai/code/session_01PepCy8wrhdWVtdWcGb3tyj`
- Nach jeder Task: `uv run ruff check && uv run ruff format --check && uv run pytest` sauber. Ein Ruff-Hook entfernt ungenutzte Imports zwischen Edits: Import und Verwendung im selben Edit schreiben.
- Repo öffentlich: keine echten Namen, Schulen, Orte; Testdaten erfunden (`lp.anna`, `projektleitung`).

## Review Focus

1. **Wiederverwendete Konto-ID:** Konto mit höchster `id` löschen, neues anlegen → das alte Cookie meldet nicht an. (Task 1 `test_neues_konto_startet_mit_zufaelliger_version`, Task 3 `test_altes_cookie_nach_neuanlage_mit_gleicher_id_ungueltig`)
2. **Passwort mit Umlauten oder über 72 Bytes:** `ä` zählt als 2 Bytes; 37 × `ä` wird beim Anlegen abgelehnt, beim Anmelden ist es einfach falsch, nie ein 500. (Task 1 `test_passwort_zu_lang_in_bytes`, Task 4 `test_anmelden_mit_ueberlangem_passwort`)
3. **Erster Besuch ohne Cookies:** Die Login-Seite rendert sofort ein gültiges CSRF-Feld, und das Absenden aus genau dieser Seite funktioniert. (Task 3 `test_erste_seite_hat_gueltiges_csrf`)
4. **Benutzername mit Leerzeichen und Grossbuchstaben** beim Anmelden (` Lp.Anna `) meldet an; beim Anlegen wird er normalisiert. (Task 1, Task 4)
5. **Abgelaufene Sitzung beim Absenden eines Formulars:** POST mit gültigem CSRF, aber ohne Anmeldung → 303 auf `/`, kein 500. (Task 5 `test_post_ohne_anmeldung_leitet_um`)

---

### Task 1: Konten und Kommando

**Files:**
- Create: `app/konten.py`, `app/kommandos.py`, `tests/test_konten.py`, `tests/test_kommandos.py`
- Modify: `tests/conftest.py` (Fixture `schnelles_bcrypt`, autouse)

**Interfaces:**
- Produces (`app/konten.py`):
  - `BCRYPT_RUNDEN: int = 12`
  - `@dataclass(frozen=True) class Konto`: `id: int`, `anzeigename: str`, `benutzername: str`, `rolle: str`, `sitzungsversion: int`; `classmethod aus_zeile(zeile: sqlite3.Row) -> Konto`.
  - `class EingabeFehler(ValueError)` mit Attribut `feld: str` (`"anzeigename"`, `"benutzername"`, `"passwort"`) und Meldung als Text.
  - `normalisiere_benutzername(text: str) -> str` (trim, lower)
  - `pruefe_neues_passwort(passwort: str) -> None` (wirft `EingabeFehler`; min 8 Zeichen, max 72 Bytes UTF-8)
  - `hash_passwort(passwort: str) -> str`, `passwort_stimmt(passwort: str, passwort_hash: str | None) -> bool` (None → Prüfung gegen festen Dummy-Hash, Ergebnis False; > 72 Bytes → False ohne Exception)
  - `passwort_vorschlag() -> str` (Muster `^[a-z]{4}-[a-z]{4}-[a-z]{4}-\d{2}$`, Konsonant-Vokal-Paare, ohne `l`/`i`/`o`-Verwechsler-Problem: Konsonanten `bdfgkmnprstvz`, Vokale `aeu`)
  - `lege_konto_an(db, anzeigename: str, benutzername: str, passwort: str, rolle: str = "lehrperson") -> Konto` (validiert alles, Startversion `secrets.randbelow(2**31) + 1`, doppelter Name → `EingabeFehler("benutzername", "Diesen Benutzernamen gibt es schon.")`)
  - `finde_konto(db, konto_id: int) -> Konto | None`, `finde_hash(db, benutzername: str) -> tuple[Konto, str] | None`
  - `lehrpersonen(db) -> list[sqlite3.Row]` (id, anzeigename, benutzername, erstellt; sortiert nach Anzeigename)
  - `setze_passwort(db, konto_id: int, passwort: str) -> None` (validiert, Hash setzen, `sitzungsversion = sitzungsversion + 1`)
  - `zaehle_daten(db, konto_id: int) -> dict[str, int]` mit Schlüsseln `antworten`, `tagebucheintraege`, `aufnahmen`
  - `loesche_konto(db, konto_id: int, aufnahmen_verzeichnis: Path) -> None` (erst Dateien per `Path(name).name` im Ordner, fehlende ignorieren; dann `DELETE FROM konten`, in einer Transaktion)
- Produces (`app/kommandos.py`): `main(argv: list[str] | None = None, eingabe: TextIO | None = None) -> int`; Unterbefehle `auftraggeberin-anlegen --benutzername --anzeigename`, `passwort-setzen --benutzername`. Passwort: `getpass` zweimal, wenn `sys.stdin.isatty()`, sonst erste Zeile von `eingabe`/stdin. Datenbank aus `DATEN_VERZEICHNIS` (Standard `.daten`), Verzeichnis anlegen, `migriere` vorher. Exit 0/1, Meldung auf stdout bzw. stderr. `if __name__ == "__main__": raise SystemExit(main())`.

- [ ] **Step 1: Failing tests** `tests/test_konten.py` (DB über `verbinde`+`migriere` in `tmp_path`):
  - `test_konto_anlegen_normalisiert_benutzername`: `" Lp.Anna "` → `benutzername == "lp.anna"`, `rolle == "lehrperson"`.
  - `test_benutzername_ungueltig`: `"ab"`, `"anna maria"`, `"anna_x"`, 41 Zeichen → `EingabeFehler` mit `feld == "benutzername"`.
  - `test_benutzername_doppelt`: zweimal `lp.anna` (einmal `LP.ANNA`) → `EingabeFehler`, Meldung «Diesen Benutzernamen gibt es schon.»
  - `test_passwort_zu_kurz` (7 Zeichen) und `test_passwort_zu_lang_in_bytes` (`"ä" * 37`, 74 Bytes) → `EingabeFehler` mit `feld == "passwort"`; `"ä" * 36` geht.
  - `test_anzeigename_leer_oder_zu_lang` (`"  "`, 61 Zeichen).
  - `test_passwort_stimmt`: richtig True, falsch False, `"x" * 100` False ohne Exception, `passwort_hash=None` False.
  - `test_neues_konto_startet_mit_zufaelliger_version`: Konto anlegen, löschen, neu anlegen → gleiche `id`, andere `sitzungsversion` (mit `monkeypatch` auf `secrets.randbelow` deterministisch prüfen oder 2 Werte vergleichen und `!= 1` assert).
  - `test_setze_passwort_erhoeht_version_und_wechselt_hash`.
  - `test_loesche_konto_entfernt_dateien_und_zeilen`: Aufnahme-Zeile + Datei `abc.webm` im Ordner, plus Tagebucheintrag → nach Löschen: Datei weg, Zeilen weg; Datei eines anderen Kontos bleibt. Dateiname `../x` in der DB löscht nichts ausserhalb des Ordners.
  - `test_zaehle_daten`.
  - `test_passwort_vorschlag_format`: 20 Vorschläge passen auf das Muster und bestehen `pruefe_neues_passwort`.
- [ ] **Step 2:** `uv run pytest tests/test_konten.py -v` → FAIL (ImportError).
- [ ] **Step 3:** `app/konten.py` implementieren; in `tests/conftest.py` autouse-Fixture `schnelles_bcrypt(monkeypatch)` setzt `app.konten.BCRYPT_RUNDEN = 4`.
- [ ] **Step 4:** Failing tests `tests/test_kommandos.py` mit `monkeypatch.setenv("DATEN_VERZEICHNIS", ...)` und `io.StringIO("geheim123\n")`: `test_auftraggeberin_anlegen` (Exit 0, Rolle `auftraggeberin`, Passwort stimmt), `test_doppelter_benutzername_exit_1`, `test_passwort_setzen_erhoeht_version`, `test_passwort_setzen_unbekannt_exit_1`, `test_leeres_passwort_exit_1`.
- [ ] **Step 5:** `app/kommandos.py` implementieren; `uv run pytest -v` → PASS; Lint sauber.
- [ ] **Step 6:** Commit `feat: Konten mit Passwort-Hash und Kommando fuer das erste Konto (#14)`.

### Task 2: Schutz gegen Durchprobieren

**Files:**
- Create: `app/anmeldeschutz.py`, `tests/test_anmeldeschutz.py`

**Interfaces:**
- Produces: `class Anmeldeschutz(uhr: Callable[[], float] = time.monotonic, fenster: float = 900, max_pro_name: int = 5, max_pro_adresse: int = 20, max_schluessel: int = 10_000)` mit
  - `gesperrt(benutzername: str, adresse: str) -> bool`
  - `fehlversuch(benutzername: str, adresse: str) -> None`
  - `erfolg(benutzername: str) -> None` (löscht nur die Fehlversuche des Namens)
  Namen werden intern mit `normalisiere_benutzername` (Task 1) verglichen. Gleitendes Fenster: pro Schlüssel eine `deque` von Zeitpunkten; ältere als `fenster` werden beim Zugriff entfernt. Bei mehr als `max_schluessel` Schlüsseln wird der Schlüssel mit dem ältesten letzten Versuch verworfen. Schlüssel mit Präfix (`"n:"`/`"a:"`) in einem Dict.

- [ ] **Step 1: Failing tests** mit einer Uhr-Klasse (`jetzt = [0.0]`):
  - `test_fuenf_fehlversuche_sperren_namen`: 4× → nicht gesperrt; 5× → gesperrt; andere Adresse → weiterhin gesperrt.
  - `test_sperre_endet_nach_fenster`: nach `uhr += 901` nicht mehr gesperrt.
  - `test_gleitendes_fenster`: Versuche bei t=0,…; nach 600 s 4 neue → gesperrt erst, wenn 5 im Fenster liegen.
  - `test_zwanzig_fehlversuche_pro_adresse`: 20 verschiedene Namen, gleiche Adresse → Adresse gesperrt für neuen Namen.
  - `test_erfolg_loescht_namen_nicht_adresse`.
  - `test_name_unabhaengig_von_schreibweise` (`"LP.Anna "` und `"lp.anna"`).
  - `test_speicher_begrenzt`: `max_schluessel=10`, 50 Adressen → `len(intern) <= 10`.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren. **Step 4:** PASS, Lint.
- [ ] **Step 5:** Commit `feat: Begrenzung der Fehlversuche pro Benutzername und Adresse (#14)`.

### Task 3: Sitzung, CSRF, Cookies, Fehlerseiten, Kopfzeilen

**Files:**
- Create: `app/cookies.py`, `app/csrf.py`, `app/sitzung.py`, `app/templates/fehler.html`, `tests/test_sitzung.py`, `tests/test_csrf.py`
- Modify: `app/main.py` (Middleware, Exception-Handler, `app.state.anmeldeschutz = Anmeldeschutz()`), `app/vorlagen.py` (Global `csrf_feld`), `app/sicherheit.py` (`Cache-Control: no-store` ausser Pfade ab `/static/`), `app/templates/basis.html` (Kopf mit Titel, Anzeigename, Abmelden-Formular; Blöcke `navigation`, `kopf_rechts`), `tests/test_sicherheit.py`

**Interfaces:**
- Produces (`app/cookies.py`):
  - `setze_cookie(request, name: str, wert: str, max_age: int | None) -> None` und `loesche_cookie(request, name: str) -> None` — legen einen fertigen `Set-Cookie`-Wert in `request.state.cookies_ausstehend` (Liste) ab. Attribute immer `HttpOnly; SameSite=Lax; Path=/`, `Secure` wenn `request.app.state.einstellungen.produktion`. Erzeugung mit `http.cookies.SimpleCookie` oder `Response.set_cookie` auf einer Hilfs-Response, Header kopieren.
  - `class CookieMiddleware` (reine ASGI wie `SicherheitsHeaderMiddleware`): vor dem Aufruf fehlt `csrf` im Request-Cookie → neuen Wert `secrets.token_urlsafe(32)` erzeugen, in `scope["state"]["csrf_wert"]` legen und als ausstehendes Cookie (Max-Age 30 Tage) vormerken; sonst den vorhandenen Wert in `csrf_wert`. Bei `http.response.start` alle `scope["state"]["cookies_ausstehend"]` als `set-cookie`-Header anhängen.
  - `CSRF_MAX_AGE = 30 * 24 * 3600`
- Produces (`app/csrf.py`):
  - `csrf_token(request) -> str` (HMAC-SHA256 über `"csrf:" + request.state.csrf_wert` mit `geheimer_schluessel`, hex)
  - `csrf_feld(request) -> markupsafe.Markup` (`<input type="hidden" name="csrf" value="…">`)
  - `async def pruefe_csrf(request) -> None` — FastAPI-Dependency; liest `await request.form()`, vergleicht mit `hmac.compare_digest`, sonst `raise KeinZugriff("Das Formular ist abgelaufen. Bitte die Seite neu laden.")`
  - `erneuere_csrf(request) -> None` — neuen Wert erzeugen, `request.state.csrf_wert` setzen, Cookie vormerken.
- Produces (`app/sitzung.py`):
  - `class NichtAngemeldet(Exception)`, `class KeinZugriff(Exception)` (Text optional; Standard «Diese Seite ist für deinen Zugang nicht freigegeben.»)
  - `DAUER_LANG = 30 * 24 * 3600`, `DAUER_KURZ = 12 * 3600`, `VERLAENGERN_AB = 24 * 3600`
  - `anmelden(request, konto: Konto, dauerhaft: bool) -> None` (Cookie `sitzung` signiert mit `URLSafeTimedSerializer(schluessel, salt="sitzung")`, Inhalt `{"k","v","d"}`, `max_age` DAUER_LANG oder None; ruft `erneuere_csrf`)
  - `abmelden(request) -> None` (Cookie löschen, `erneuere_csrf`)
  - `aktuelles_konto(request, db=Depends(hole_db)) -> Konto | None` (prüft Signatur mit `max_age` je nach `d`, Konto, Version; bei Ungültigkeit `loesche_cookie`; bei `d` und Alter > `VERLAENGERN_AB` neu setzen — Alter über `loads(..., return_timestamp=True)`; Ergebnis in `request.state.konto`)
  - `braucht_lehrperson(konto=Depends(aktuelles_konto)) -> Konto`, `braucht_auftraggeberin(...) -> Konto` (None → `NichtAngemeldet`, falsche Rolle → `KeinZugriff`)
  - `STARTSEITE = {"lehrperson": "/lehrperson", "auftraggeberin": "/verwaltung"}`
- `main.py`: Handler `NichtAngemeldet` → `RedirectResponse("/", 303)`; `KeinZugriff` → `fehler.html` mit 403; `StarletteHTTPException` 404 → `fehler.html` mit 404 («Diese Seite gibt es nicht.»), andere Codes Standardverhalten. Reihenfolge der Middleware: `CookieMiddleware` innen, `SicherheitsHeaderMiddleware` aussen.
- `basis.html`: `request.state.konto` (falls gesetzt) zeigt Anzeigename und Abmelden-Knopf (`<form method="post" action="/abmelden">{{ csrf_feld(request) }}…</form>`). Templates greifen mit `request.state.konto|default(none)` zu (State-Attribut kann fehlen → im Template über eine kleine Hilfsfunktion oder `getattr` in einem Jinja-Global `konto_von(request)`).

- [ ] **Step 1: Failing tests** `tests/test_csrf.py` (mit einer Test-App aus `erstelle_app(einstellungen)` plus zusätzlichen Test-Routen `GET /t/formular` (rendert `csrf_feld`) und `POST /t/senden` mit `Depends(pruefe_csrf)`):
  - `test_erste_seite_hat_gueltiges_csrf`: frischer Client ohne Cookies → `GET /t/formular` setzt Cookie `csrf`; Token aus HTML + Cookie → `POST /t/senden` 200.
  - `test_post_ohne_token_403`, `test_post_mit_falschem_token_403`, `test_token_eines_anderen_cookies_403`.
  - `test_csrf_cookie_attribute`: HttpOnly, SameSite=Lax, Max-Age, `Secure` nur bei `produktion=True` (Einstellungen mit Schlüssel ≥ 32 Zeichen).
- [ ] **Step 2: Failing tests** `tests/test_sitzung.py` (Test-Routen `POST /t/anmelden/{id}?dauerhaft=1` ruft `anmelden`, `GET /t/lp` mit `braucht_lehrperson`, `GET /t/ag` mit `braucht_auftraggeberin`; Uhr: `monkeypatch` auf `itsdangerous.timed.time.time`, damit Alter simuliert wird; Konten über `app.konten.lege_konto_an`):
  - `test_ohne_cookie_umleitung_auf_start` (303, `location == "/"`), `test_falsche_rolle_403` (beide Richtungen, Fehlerseite enthält «Kein Zugriff»).
  - `test_sitzungscookie_attribute`: dauerhaft → `Max-Age=2592000`; nicht dauerhaft → kein `Max-Age`; HttpOnly, SameSite=Lax; `Secure` nur in Produktion.
  - `test_manipuliertes_cookie_ungueltig`, `test_kurze_sitzung_nach_12h_ungueltig`, `test_lange_sitzung_nach_30_tagen_ungueltig`, `test_lange_sitzung_nach_2_tagen_wird_verlaengert` (Antwort enthält neues `sitzung`-Cookie).
  - `test_versionswechsel_beendet_sitzung` (`setze_passwort` → 303), `test_geloeschtes_konto_beendet_sitzung`.
  - `test_altes_cookie_nach_neuanlage_mit_gleicher_id_ungueltig`.
  - `test_ungueltiges_cookie_wird_geloescht` (Set-Cookie `sitzung=""` mit `Max-Age=0` o. ä.).
- [ ] **Step 3:** Ergänze `tests/test_sicherheit.py`: `test_no_store_auf_seiten` (`/` und 404-Seite haben `Cache-Control: no-store`), `test_static_ohne_no_store`; `test_404_ist_html_fehlerseite` («Diese Seite gibt es nicht.», Header vorhanden).
- [ ] **Step 4:** FAIL. **Step 5:** implementieren. **Step 6:** `uv run pytest -v` PASS (bestehende Tests aus #13 bleiben grün), Lint.
- [ ] **Step 7:** Commit `feat: Sitzung, CSRF-Schutz, Fehlerseiten und no-store (#14)`.

### Task 4: Login, Abmelden, Startseite der Lehrperson, Routen-Inventar

**Files:**
- Create: `app/routen/anmeldung.py`, `app/routen/lehrperson.py`, `app/templates/anmelden.html`, `app/templates/lehrperson/start.html`, `tests/test_anmeldung.py`, `tests/test_routen_inventar.py`
- Modify: `app/routen/allgemein.py` (Route `/` entfernen, nur `/healthz`), `app/main.py` (Router einbinden), `app/templates/start.html` löschen, `tests/test_app.py` (Startseiten-Tests auf Login-Seite umstellen), `tests/conftest.py` (Fixtures), `app/static/css/style.css` (falls nötig)

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces (`tests/conftest.py`): Fixtures `lehrperson(client) -> dict` (`{"id", "benutzername": "lp.anna", "passwort": "anna-pass-1"}`, Anzeigename «Anna Beispiel»), `zweite_lehrperson` (`lp.ben`), `auftraggeberin` (`projektleitung`, «Projektleitung»); Hilfsfunktionen `csrf_von(client, pfad="/") -> str` (liest `name="csrf" value="…"` per Regex aus dem HTML) und `anmelden(client, benutzername, passwort, dauerhaft=True) -> Response` (ohne Redirect-Folgen). Die Konto-Fixtures schreiben direkt über `verbinde(einstellungen.db_pfad)` + `lege_konto_an`.
- Produces (Routen): `GET /` (Login oder 303 auf `STARTSEITE[rolle]`), `POST /anmelden` (Felder `benutzername`, `passwort`, `dauerhaft` = Checkbox `"1"`), `POST /abmelden`, `GET /lehrperson`.
- Client-Adresse: `Fly-Client-IP` nur wenn `einstellungen.produktion`, sonst `request.client.host` (Hilfsfunktion `client_adresse(request) -> str` in `app/routen/anmeldung.py`).
- Ablauf `POST /anmelden`: CSRF → gesperrt? (429, ohne bcrypt) → `finde_hash` → `passwort_stimmt` (bei unbekanntem Namen mit `None`) → Fehler: `fehlversuch`, 400 mit Meldung, Benutzername bleibt im Feld → Erfolg: `erfolg`, `anmelden`, 303.

- [ ] **Step 1: Failing tests** `tests/test_anmeldung.py`:
  - `test_login_seite`: `GET /` 200, enthält «Anmelden», Felder `benutzername`, `passwort`, Checkbox `dauerhaft` mit `checked`.
  - `test_anmelden_lehrperson` → 303 `/lehrperson`; `GET /lehrperson` zeigt «Anna Beispiel»; `GET /` jetzt 303 `/lehrperson`.
  - `test_anmelden_auftraggeberin` → 303 `/verwaltung` (Route folgt in Task 5; hier nur Location prüfen).
  - `test_anmelden_falsch` (falsches Passwort, unbekannter Name): 400, «Benutzername oder Passwort stimmt nicht.», kein `sitzung`-Cookie, eingegebener Benutzername im Feld.
  - `test_anmelden_mit_ueberlangem_passwort`: `"ä" * 50` → 400, nicht 500.
  - `test_anmelden_schreibweise_egal` (` LP.Anna `).
  - `test_sperre_nach_fuenf_fehlversuchen`: 5× falsch, dann richtig → 429, «Zu viele Fehlversuche».
  - `test_fly_client_ip_nur_in_produktion`: Produktions-App (Schlüssel ≥ 32 Zeichen), 20 Fehlversuche mit `Fly-Client-IP: 1.2.3.4` auf verschiedene Namen → nächster Versuch mit derselben IP 429, mit `Fly-Client-IP: 5.6.7.8` nicht; in Entwicklung wird der Header ignoriert (alle zählen auf `testclient`).
  - `test_abmelden`: danach `GET /lehrperson` → 303 `/`; `csrf`-Cookie wurde erneuert.
  - `test_anmelden_erneuert_csrf`.
- [ ] **Step 2: Failing tests** `tests/test_routen_inventar.py`:
  - Sammle `app.routes` (nur `APIRoute`), Pfadparameter durch `1` ersetzen. `OEFFENTLICH = {"/", "/healthz"}` (Kommentar: #19 ergänzt `/gast…`; neue Ausnahmen nur mit Begründung).
  - `test_get_routen_brauchen_anmeldung`: jede GET-Route ausser `OEFFENTLICH` → 303 mit `location == "/"` (ohne Redirect-Folgen).
  - `test_post_routen_brauchen_csrf`: jede POST-Route ohne `csrf`-Feld → 403 (auch angemeldet als Auftraggeberin und als Lehrperson).
  - `test_post_ohne_anmeldung_leitet_um`: jede POST-Route ausser `/anmelden` mit gültigem CSRF, ohne Anmeldung → 303 `/`.
  - `test_lehrperson_erreicht_keine_verwaltung`: angemeldet als Lehrperson, jede GET-Route mit Präfix `/verwaltung` → 403; umgekehrt Auftraggeberin auf `/lehrperson…` → 403.
  - `test_inventar_nicht_leer`: mindestens `/lehrperson` und `/anmelden` sind enthalten (Schutz gegen einen leeren, immer grünen Test).
- [ ] **Step 3:** FAIL. **Step 4:** implementieren (Login-Seite nach Spec, Abschnitt «Seitenrahmen und Gestaltung», inkl. `{% block gast %}{% endblock %}`; Lehrperson-Start «Hallo, {{ anzeigename }}» plus Satz, dass die Runden und das Tagebuch bald hier erscheinen).
- [ ] **Step 5:** `uv run pytest -v` PASS, Lint. **Step 6:** Commit `feat: Login-Seite, Abmelden und Startseite der Lehrperson (#14)`.

### Task 5: Zugänge verwalten

**Files:**
- Create: `app/routen/verwaltung.py`, `app/templates/verwaltung/start.html`, `app/templates/verwaltung/zugaenge.html`, `app/templates/verwaltung/passwort.html`, `app/templates/verwaltung/loeschen.html`, `app/templates/verwaltung/zugang_bestaetigt.html` (zeigt Passwort einmal), `tests/test_verwaltung.py`
- Modify: `app/main.py`, `app/static/css/style.css` (falls nötig)

**Interfaces:**
- Consumes: `braucht_auftraggeberin`, `pruefe_csrf`, `konten.*`.
- Produces: Routen laut Spec-Tabelle «Adressen». Router mit `prefix="/verwaltung"` und `dependencies=[Depends(braucht_auftraggeberin)]`; POST-Routen zusätzlich `Depends(pruefe_csrf)` vor dem Konto. Hilfsfunktion `_lehrperson_oder_404(db, konto_id) -> Konto` (Rolle ≠ lehrperson oder unbekannt → `HTTPException(404)`). Bestätigungen `?erledigt=geloescht` aus festem Dict `BESTAETIGUNGEN`.

- [ ] **Step 1: Failing tests** `tests/test_verwaltung.py`:
  - `test_uebersicht` (Link auf `/verwaltung/zugaenge`), `test_liste_zeigt_nur_lehrpersonen` (eigenes Konto nicht gelistet).
  - `test_formular_hat_passwort_vorschlag` (Feld `passwort` vorausgefüllt, passt aufs Muster aus Task 1).
  - `test_zugang_anlegen`: 200, Seite zeigt Benutzername und Passwort; danach kann sich die Lehrperson anmelden.
  - `test_zugang_anlegen_fehler`: doppelter Name, zu kurzes Passwort, leerer Anzeigename → 400, Meldung, eingegebene Werte stehen wieder im Formular.
  - `test_passwort_setzen_beendet_sitzungen`: Lehrperson-Client angemeldet; Auftraggeberin setzt neues Passwort → Lehrperson-Client `GET /lehrperson` → 303 `/`; Anmeldung mit neuem Passwort geht, mit altem nicht.
  - `test_loeschen_bestaetigung_zeigt_zahlen` (einen Tagebucheintrag per SQL anlegen → «1 Tagebucheintrag» bzw. Zahl sichtbar).
  - `test_loeschen`: POST → 303 `?erledigt=geloescht`, Konto weg, Aufnahme-Datei weg, Lehrperson-Client ausgeloggt.
  - `test_fremde_ids_404`: `id` der Auftraggeberin und `id=999` bei GET/POST passwort und loeschen → 404.
  - `test_bestaetigung_nur_aus_fester_liste`: `?erledigt=<script>` zeigt nichts davon.
- [ ] **Step 2:** FAIL. **Step 3:** implementieren (Texte nach Spec «Zugänge verwalten»; Einzahl/Mehrzahl korrekt). **Step 4:** PASS, Lint (das Routen-Inventar aus Task 4 deckt die neuen Routen automatisch ab und muss grün bleiben).
- [ ] **Step 5:** Commit `feat: Zugaenge der Lehrpersonen verwalten (#14)`.

### Task 6: E2E-Abläufe und Doku

**Files:**
- Modify: `tests/e2e-pilot.mjs`, `README.md`, `docs/beobachtungen.md` (Eintrag «Kleine Härtungen…»: Teil zu `pruefe` als erledigt vermerken bzw. umformulieren)

**Interfaces:**
- Consumes: Kommando aus Task 1, alle Seiten.
- Produces (`e2e-pilot.mjs`, Gerüst): `muss(bedingung, beschreibung)` — wie `pruefe`, wirft aber bei Fehlschlag (`throw new Error(...)`). `tippe(sel, wert)` setzt `value` per `js()` und löst `input` aus. `sende(sel)` klickt den Knopf und wartet auf das nächste `Page.loadEventFired`. Vor `starteApp()`: `uv run python -m app.kommandos auftraggeberin-anlegen --benutzername projektleitung --anzeigename Projektleitung` mit `DATEN_VERZEICHNIS=DATEN` und Passwort über stdin (`spawnSync`, `input`).

- [ ] **Step 1:** Bestehende Startseiten-Abläufe auf die Login-Seite umstellen (Titel, kein Überlauf, hell/dunkel, Desktop).
- [ ] **Step 2:** Abläufe nach Spec «Prüfung und Nachweis → E2E» Punkte 1–5 in 390 px, mit Screenshots `04-login-fehler`, `05-zugaenge`, `06-zugang-angelegt`, `07-lehrperson-start`, `08-kein-zugriff`; Passwort für die Lehrperson aus der Bestätigungsseite lesen. Jede Seite: `keinUeberlauf`, `keineFehlerSeit`.
- [ ] **Step 3:** `make e2e` → «… bestanden, 0 fehlgeschlagen». Screenshots ansehen (Login 390 px hell/dunkel, Zugänge, Kein Zugriff).
- [ ] **Step 4:** README: Abschnitt «Erstes Konto der Auftraggeberin» mit lokalem Aufruf und fly-Aufruf als `appuser` (genauer Befehl nach Spec; als «beim ersten Deploy geprüft» markieren, der Orchestrator bestätigt ihn). «Stand»-Absatz: Login und Zugänge vorhanden.
- [ ] **Step 5:** `make lint test e2e` grün. Commit `test: E2E-Ablaeufe fuer Anmeldung und Zugaenge, Doku (#14)`.
