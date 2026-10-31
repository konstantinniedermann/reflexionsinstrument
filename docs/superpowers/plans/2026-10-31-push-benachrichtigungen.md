# Push-Benachrichtigungen Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Die Auftraggeberin schickt aus der Verwaltung kurze Benachrichtigungen an alle Geräte, auf denen Lehrpersonen (oder sie selbst) Benachrichtigungen eingeschaltet haben (#37).

**Architecture:** Web Push ohne Drittdienst: Manifest + Service Worker machen das Instrument installierbar und empfangsbereit; ein Seiten-Skript schliesst das Abo ab und meldet es per Formular-POST (mit CSRF) an; der Server speichert Abos in SQLite und schickt verschlüsselte Nachrichten mit `http_ece` + `py_vapid` über `urllib` direkt an die Push-Dienste der Hersteller.

**Tech Stack:** FastAPI, Jinja2, SQLite, `http-ece`, `py-vapid` (bringen `cryptography` mit), Vanilla-JS, Node-CDP-E2E.

**Spec:** `docs/superpowers/specs/2026-10-31-push-benachrichtigungen-design.md`

## Global Constraints

- Neue Pakete nur `http-ece` und `py-vapid` (freigegeben), sonst keine.
- Ohne Secret `VAPID_SCHLUESSEL` ist die Funktion aus; die App startet trotzdem, auch mit `PRODUKTION=1`.
- Erlaubte Push-Hosts (Suffix): `push.apple.com`, `fcm.googleapis.com`, `push.services.mozilla.com`, `notify.windows.com`. Nur `https`, Port 443, keine Zugangsdaten, Endpunkt ≤ 1000 Zeichen.
- `p256dh` = 65 Byte unkomprimierter P-256-Punkt, `auth` = 16 Byte, beide base64url (ohne `=`).
- Höchstens 10 Abos pro Konto, beim elften fällt das älteste weg.
- Nachricht: höchstens `LAENGE_KURZ` (500) Zeichen, Pflicht. Nutzlast JSON `{"titel": ..., "text": ...}`.
- VAPID: `sub` = `https://reflexionsinstrument.fly.dev`, `aud` = Schema+Host des Endpunkts, `exp` = jetzt + 12 h. Header `TTL: 86400`, `Urgency: normal`, `Content-Encoding: aes128gcm`, Zeitlimit 10 s.
- Status 201/202 zugestellt; 404/410/401/403 Abo löschen; sonst und Netzfehler «nicht erreicht».
- Logs: nur Status und Host, nie Endpunkt-Pfad, Schlüssel, Text.
- Oberfläche ohne «Push», «Abo», «Token»; keine Emojis; kein Inline-Skript/-Stil (CSP `script-src 'self'`).
- Keine Benachrichtigungs-Teile in Gast und Vorschau.

## Review Focus

1. Gerät schaltet ein, Konto wird gelöscht → Abo verschwindet mit (Kaskade), keine Nachricht mehr an das Gerät.
2. Zwei Konten nacheinander auf demselben Gerät → Abo gehört dem zuletzt angemeldeten Konto; Lehrperson A kann das Abo von B nicht löschen.
3. Böswilliger POST mit Endpunkt `https://127.0.0.1/…`, `https://evil.example/push.apple.com`, `https://x.push.apple.com.evil.example/…`, `http://…`, Port 8443 → 400, nichts gespeichert.
4. Push-Dienst nicht erreichbar oder Zeitüberschreitung bei einem Gerät → übrige Geräte bekommen die Nachricht trotzdem, Ergebnis zählt es als «nicht erreicht».
5. Leere oder zu lange Nachricht, Doppel-Absenden ohne CSRF → Fehlermeldung bzw. abgelehnt, nichts gesendet.

---

### Task 1: Pakete, Schlüssel und Einstellungen

**Files:**
- Modify: `pyproject.toml`, `uv.lock` (`uv add http-ece py-vapid`)
- Modify: `app/config.py` (Feld `vapid_schluessel: str | None`, aus Umgebung `VAPID_SCHLUESSEL`, leer → `None`)
- Create: `app/push.py` (Teil Schlüssel)
- Modify: `app/kommandos.py` (Unterkommando `vapid-schluessel`)
- Test: `tests/test_push_schluessel.py`, `tests/test_config.py`

**Interfaces:**
- Produces: `erzeuge_vapid_schluessel() -> str` (PEM des privaten Schlüssels, base64url, eine Zeile); `lade_vapid(wert: str) -> py_vapid.Vapid02`; `oeffentlicher_schluessel(vapid) -> str` (65-Byte-Punkt, base64url ohne `=`); `Einstellungen.vapid_schluessel`.

- [ ] Tests: `test_schluessel_rundreise` (erzeugen → laden → öffentlicher Schlüssel dekodiert zu 65 Byte, beginnt mit `0x04`); `test_kaputter_schluessel` (`lade_vapid("abc")` wirft `ValueError`); `test_config_vapid` (ohne Variable `None`, mit Wert gesetzt, `PRODUKTION=1` ohne Wert startet); `test_kommando_vapid` (Ausgabe enthält `fly secrets set VAPID_SCHLUESSEL=` und einen ladbaren Wert).
- [ ] Laufen lassen, Fehlschlag sehen; Pakete hinzufügen; implementieren; `uv run pytest tests/test_push_schluessel.py tests/test_config.py -q` grün.
- [ ] Commit `feat: VAPID-Schlüssel und Pakete für Benachrichtigungen (#37)`.

### Task 2: Abos speichern und prüfen

**Files:**
- Create: `app/migrationen/004_push_abos.sql`
- Create: `app/push_abos.py`
- Test: `tests/test_push_abos.py`

**Interfaces:**
- Produces: `@dataclass Abo(endpunkt: str, p256dh: str, auth: str)`; `pruefe_abo(endpunkt, p256dh, auth) -> Abo` (wirft `ValueError`); `speichere_abo(db, konto_id: int, abo: Abo) -> None` (UPSERT auf `endpunkt`, Konto übernimmt; danach höchstens 10 pro Konto); `loesche_abo(db, konto_id: int, endpunkt: str) -> bool`; `alle_abos(db) -> list[sqlite3.Row]` (Spalten `id, endpunkt, p256dh, auth`); `entferne_abo(db, abo_id: int) -> None`; `anzahl_abos(db) -> int`.

- [ ] Tests: erlaubte Hosts je einer (z. B. `https://web.push.apple.com/abc`, `https://fcm.googleapis.com/fcm/send/abc`); abgelehnt die fünf Fälle aus Review Focus 3 plus Endpunkt 1001 Zeichen, `p256dh` 64 Byte, `auth` 15 Byte, kein base64url; `test_gleiches_geraet_neues_konto`; `test_fremdes_abo_nicht_loeschbar`; `test_obergrenze_zehn` (11 speichern → 10 übrig, das erste fehlt); `test_kaskade_beim_konto_loeschen`.
- [ ] Fehlschlag sehen, implementieren (Tabelle `push_abos` STRICT, `konto_id ... REFERENCES konten(id) ON DELETE CASCADE`, `endpunkt TEXT NOT NULL UNIQUE`, `erstellt` wie andere Tabellen), grün.
- [ ] Commit `feat: Benachrichtigungs-Abos speichern und prüfen (#37)`.

### Task 3: Versand

**Files:**
- Modify: `app/push.py` (Teil Versand)
- Test: `tests/test_push_versand.py`

**Interfaces:**
- Consumes: `lade_vapid`, `alle_abos`, `entferne_abo`.
- Produces: `sende(vapid, abo: sqlite3.Row, nutzlast: bytes, oeffne=urllib.request.urlopen) -> int | None` (Status, `None` bei Netzfehler); `@dataclass Ergebnis(gesendet: int, entfernt: int, nicht_erreicht: int)`; `verschicke_an_alle(db, vapid, titel: str, text: str, oeffne=...) -> Ergebnis`.

- [ ] Tests mit einem echten Geräte-Schlüsselpaar (`cryptography` EC P-256 + 16 Zufallsbyte) und einem Ersatz für `oeffne`, der die `Request` festhält: `test_nutzlast_entschluesselbar` (`http_ece.decrypt(body, private_key=geraet, auth_secret=auth, version="aes128gcm")` == JSON mit Titel und Text); `test_header` (`TTL`, `Urgency`, `Content-Encoding`, `Authorization` beginnt mit `vapid t=`, `k=` = öffentlicher Schlüssel; JWT-`aud` = `https://fcm.googleapis.com`); `test_410_loescht`, `test_403_loescht`, `test_500_bleibt`, `test_netzfehler_andere_bekommen_es` (erstes Gerät wirft `URLError`, zweites 201 → `Ergebnis(1, 0, 1)`); `test_log_ohne_endpunkt` (caplog enthält Host, nicht den Pfad).
- [ ] Fehlschlag sehen, implementieren, grün.
- [ ] Commit `feat: Benachrichtigungen verschlüsselt versenden (#37)`.

### Task 4: Routen, Manifest, Service Worker

**Files:**
- Create: `app/routen/benachrichtigung.py` (zwei Router: `router` öffentlich/angemeldet, `verwaltung_router` mit `braucht_auftraggeberin`)
- Modify: `app/main.py` (einbinden)
- Create: `app/static/js/sw.js`, `app/static/bilder/symbol-180.png`, `symbol-192.png`, `symbol-512.png`
- Create: `app/templates/verwaltung/benachrichtigung.html`
- Modify: `app/templates/verwaltung/start.html`, `verwaltung/rahmen.html` (Link «Benachrichtigung»)
- Modify: `tests/test_routen_inventar.py` (`/manifest.webmanifest`, `/sw.js` öffentlich)
- Test: `tests/test_benachrichtigung_routen.py`

**Interfaces:**
- Consumes: Task 1–3.
- Produces: `GET /manifest.webmanifest` (`application/manifest+json`), `GET /sw.js` (`text/javascript`, Inhalt aus `app/static/js/sw.js`), `POST /benachrichtigung/abo` (Formular `endpunkt,p256dh,auth,csrf` → 204; ungültig 400; aus → 404), `POST /benachrichtigung/abo/loeschen` (`endpunkt,csrf` → 204), `GET/POST /verwaltung/benachrichtigung`. Template-Global `push_schluessel(request) -> str | None`.

- [ ] Tests: Manifest enthält Titel aus `lies_titel`, `start_url "/"`, `display "standalone"`, drei Symbole; `sw.js` erreichbar ohne Anmeldung; Abo speichern als Lehrperson und als Auftraggeberin (204), ohne Anmeldung → 303 auf `/`, ohne CSRF → 403, ungültige Adresse → 400, ohne Secret → 404; Verwaltung: Lehrperson → 403; Formular vorbelegt mit aktuellem Impuls; leerer Text → Fehlermeldung, nichts gesendet; Senden ruft `verschicke_an_alle` (per `monkeypatch`) und zeigt «Gesendet an 2 Geräte.»; ohne Secret erklärt die Seite «Benachrichtigungen sind nicht eingerichtet.» und hat kein Formular.
- [ ] Fehlschlag sehen, implementieren (Service Worker: `push` → `showNotification(titel, {body, icon: "/static/bilder/symbol-192.png", lang: "de"})`; `notificationclick` → vorhandenes Fenster fokussieren, sonst `clients.openWindow("/")`; kein `fetch`-Handler), grün; Routen-Inventar grün.
- [ ] Commit `feat: Manifest, Service Worker und Senden in der Verwaltung (#37)`.

### Task 5: Ein- und Ausschalten auf dem Gerät

**Files:**
- Create: `app/static/js/benachrichtigung.js`, `app/templates/_benachrichtigung.html`
- Modify: `app/templates/basis.html` (Manifest, `apple-touch-icon`, `apple-mobile-web-app-title`, `theme-color`)
- Modify: `app/templates/lehrperson/start.html`, `lehrperson/info.html`, `verwaltung/benachrichtigung.html` (Partial, nur wenn `push_schluessel` und `ansicht.speichert` bzw. Verwaltung)
- Modify: `app/texte.py` (Vorlage `hinweis_benachrichtigung`, Bereich `hinweise`, Ort «Auf der Info-Seite bei den Benachrichtigungen.», Vorschlag wörtlich aus dem Design), `app/seiten_lehrperson.py` (Info-Kontext)
- Modify: `app/static/css/style.css` (Abschnitt `/* Benachrichtigungen (#37) */`)
- Test: `tests/test_benachrichtigung_seiten.py`, betroffene Zähltests der Hinweise

**Interfaces:**
- Consumes: Routen aus Task 4. Partial-Parameter `ort` = `"start"` | `"info"` | `"verwaltung"`.
- Produces: Markup mit `data-push-schluessel`, `data-ort`, Teilen `[data-zustand="ios"|"aus"|"an"|"abgelehnt"|"unmoeglich"]` (alle `hidden`), Knöpfe `data-aktion="ein"|"aus"|"spaeter"`, verstecktes CSRF-Feld.

- [ ] Tests: Start und Info der Lehrperson enthalten das Partial und `benachrichtigung.js` nur mit Secret; Gast und Vorschau nie; Info zeigt den Hinweistext; Eingabemaske listet sechs Hinweise; `basis.html` verweist auf Manifest und Symbol.
- [ ] Skript gemäss Zustandstabelle im Design, iOS-Erkennung inkl. iPad, Schlüsselvergleich (`subscription.options.applicationServerKey`), erneutes Anmelden beim Laden, «Nicht jetzt» in `localStorage` (`benachrichtigung-spaeter`, in try/catch).
- [ ] `make test`, `make lint` grün.
- [ ] Commit `feat: Benachrichtigungen auf dem Gerät ein- und ausschalten (#37)`.

### Task 6: E2E, Doku

**Files:**
- Modify: `tests/e2e-pilot.mjs` (Ablauf «Benachrichtigungen», App mit Test-`VAPID_SCHLUESSEL` starten)
- Modify: `docs/datenschutz.md`, `docs/loeschkonzept.md`, `docs/anforderungen.md`, `fly.toml` (Kommentar Secret), `README.md` falls Befehle gelistet

- [ ] E2E: Manifest und `/sw.js` laden (200), Service Worker registriert (`navigator.serviceWorker.getRegistration()`), Hinweis auf Start sichtbar, «Nicht jetzt» blendet aus und bleibt nach Neuladen aus, Info zeigt Ein-Knopf und Hinweistext, Verwaltung zeigt Formular; 390 px ohne horizontales Scrollen, hell/dunkel; keine CSP-Verstösse; Screenshots `80-…` bis `85-…`.
- [ ] Doku gemäss Abschnitt «Datenschutz» im Design.
- [ ] `make test`, `make lint`, `make e2e` grün.
- [ ] Commit `test: E2E Benachrichtigungen` und `docs: Datenschutz, Löschkonzept, Anforderungen zu Benachrichtigungen (#37)`.

### Task 7: Produktion

- [ ] Review (Code-Review-Agent + `cas-reviewer`), Befunde beheben, PR, Merge.
- [ ] `python -m app.kommandos vapid-schluessel` → `fly secrets set VAPID_SCHLUESSEL=…` (Wert nicht ins Repo, nicht in Logs), `make deploy` von `main`.
- [ ] Nachweis: Testkonto per `fly ssh` (Memory «Prod-Nachweis als Lehrperson»), im echten Chrome einschalten, als Auftraggeberin senden → Ergebnis «Gesendet an 1 Gerät», Benachrichtigung sichtbar; Testkonto wieder löschen (Kaskade entfernt das Abo).
- [ ] iPhone/Android: Prüfliste für den Betreiber im PR/Issue.
