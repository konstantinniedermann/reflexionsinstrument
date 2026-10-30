# Design: Anmeldung, Rollen und Konten (#14)

Grundlage: [Anforderungen](../../anforderungen.md) (Abschnitt «Anmeldung und Konten»), [ADR-001](../../adr/ADR-001-technik-pilot.md), [Design Grundgerüst](2026-10-30-grundgeruest-design.md), Hinweise aus den Reviews zu #13 (Kommentar in #14). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»); wo es eine Alternative gab, steht die Begründung dabei.

## Zweck

Lehrpersonen und die Auftraggeberin melden sich mit Benutzername und Passwort an. Jede Rolle erreicht nur ihre Seiten. Die Auftraggeberin verwaltet die Zugänge der Lehrpersonen selbst. Dieses Issue legt die Bausteine fest, die #15–#19 für jede neue Seite verwenden: Anmeldeprüfung, Rollenprüfung, CSRF-Schutz, Fehlerseiten, Seitenrahmen mit Navigation.

## Ziele

- Die Adresse führt auf die Login-Seite. Nach der Anmeldung landet jede Rolle auf ihrer Startseite.
- Jede Anfrage prüft serverseitig Sitzung, Sitzungsversion und Rolle.
- Passwort zurücksetzen oder Konto löschen beendet alle Sitzungen dieses Kontos.
- Durchprobieren von Passwörtern wird gebremst.
- Alle Formulare sind gegen CSRF geschützt.
- Die Auftraggeberin legt Zugänge für Lehrpersonen an, setzt Passwörter zurück und löscht Zugänge samt Einträgen und Aufnahmen.
- Der Betreiber legt das erste Konto der Auftraggeberin per Kommando an.
- Ein Test prüft für **jede** registrierte Route, dass sie ohne Anmeldung nicht erreichbar ist (ausser einer kleinen, ausdrücklichen Liste). Damit sind auch die Routen von #15–#19 automatisch abgedeckt.

## Nicht-Ziele

- Inhalte der Startseiten. Die Lehrperson sieht vorerst «Hallo, Anzeigename» und den Hinweis, dass die Runden bald folgen (#16). Die Auftraggeberin sieht eine Übersicht mit dem Punkt «Zugänge» und Platzhaltern für «Inhalte» (#15), «Einträge» (#18), «Vorschau» (#19).
- Knopf «Ansehen ohne Konto» (#19). Die Login-Seite lässt dafür einen markierten Platz.
- Passwort selbst ändern durch die Lehrperson, «Passwort vergessen» per E-Mail, Anzeigename oder Benutzername nachträglich ändern (nicht verlangt; Zugang löschen und neu anlegen genügt in der Testphase).
- Weitere Konten der Rolle Auftraggeberin über die Oberfläche (nur per Kommando).
- Zugriffstests auf Einträge und Aufnahmen fremder Lehrpersonen: Diese Seiten entstehen in #16/#17; dort gilt das Akzeptanzkriterium aus #14 weiter (siehe «Übergabe an spätere Issues»).

## Anti-Ziele

- Keine neue Dependency (alles mit `bcrypt`, `itsdangerous`, `python-multipart` und Standardbibliothek).
- Keine Sitzungstabelle in der Datenbank. Widerruf geht über `konten.sitzungsversion` (ADR-001).
- Keine technischen Begriffe in der Oberfläche («Zugang» statt «Konto», «Passwort» ja, «Session», «Token», «Rolle» nein).
- Kein JavaScript für Anmeldung und Verwaltung.

## Begriffe in der Oberfläche

| Im Code | In der Oberfläche |
|---|---|
| Konto | Zugang |
| Lehrperson / Auftraggeberin | Lehrperson / (keine Bezeichnung, sie ist «du») |
| Sitzung beenden | Abmelden |
| `sitzungsversion` erhöhen | «Alle Anmeldungen dieses Zugangs werden beendet.» |

## Adressen

| Methode, Pfad | Wer | Was |
|---|---|---|
| `GET /` | alle | Nicht angemeldet: Login-Seite. Angemeldet: Weiterleitung (303) auf die Startseite der Rolle |
| `POST /anmelden` | alle | Anmeldung prüfen. Erfolg: Cookie setzen, 303 auf Startseite der Rolle. Fehler: Login-Seite mit Meldung (Status 400, bzw. 429 bei Sperre) |
| `POST /abmelden` | angemeldet | Cookie löschen, 303 auf `/` |
| `GET /lehrperson` | Lehrperson | Startseite (Platzhalter bis #16) |
| `GET /verwaltung` | Auftraggeberin | Übersicht |
| `GET /verwaltung/zugaenge` | Auftraggeberin | Liste der Zugänge, Formular «Neuer Zugang» |
| `POST /verwaltung/zugaenge` | Auftraggeberin | Zugang anlegen |
| `GET /verwaltung/zugaenge/{id}/passwort` | Auftraggeberin | Formular neues Passwort |
| `POST /verwaltung/zugaenge/{id}/passwort` | Auftraggeberin | Passwort setzen, Sitzungsversion erhöhen |
| `GET /verwaltung/zugaenge/{id}/loeschen` | Auftraggeberin | Bestätigungsseite mit Anzahl Einträge und Aufnahmen |
| `POST /verwaltung/zugaenge/{id}/loeschen` | Auftraggeberin | Zugang samt Einträgen und Aufnahmen löschen |
| `GET /healthz`, `/static/…` | alle | wie bisher |

Präfixe für spätere Issues: Lehrperson unter `/lehrperson/…` (#16, #17), Auftraggeberin unter `/verwaltung/…` (#15, #18, Vorschau #19), Gast unter `/gast/…` (#19).

Die Verwaltung bearbeitet nur Konten der Rolle Lehrperson. Eine `id` eines Kontos der Auftraggeberin oder eine unbekannte `id` ergibt 404.

## Sitzung

- Cookie `sitzung`, Inhalt mit `itsdangerous.URLSafeTimedSerializer(geheimer_schluessel, salt="sitzung")` signiert: `{"k": konto_id, "v": sitzungsversion, "d": dauerhaft (bool)}`.
- Attribute: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Secure` genau dann, wenn `einstellungen.produktion` (nicht abhängig vom Schema der Anfrage; hinter dem fly-Proxy kommt die Anfrage als HTTP an).
- **Angemeldet bleiben** (Häkchen, standardmässig an): Cookie mit `Max-Age` 30 Tage, Signatur gilt 30 Tage. Ohne Häkchen: Cookie ohne `Max-Age` (endet mit dem Browser), Signatur gilt höchstens 12 Stunden. Begründung 12 h: Browser stellen Sitzungs-Cookies beim Wiederherstellen der Tabs oft wieder her; auf einem Schulcomputer soll die Anmeldung trotzdem am selben Tag enden.
- **Verlängerung:** Ist die Signatur einer dauerhaften Sitzung älter als 1 Tag, wird das Cookie bei der nächsten Anfrage mit neuem Zeitstempel neu gesetzt. Begründung: Testphase ab Mitte November plus 4 Wochen Laufzeit sind länger als 30 Tage; eine Lehrperson soll mitten in der Laufzeit nicht unerwartet abgemeldet werden. Nicht dauerhafte Sitzungen werden nicht verlängert.
- **Prüfung bei jeder Anfrage:** Signatur und Alter gültig, Konto existiert, `v` gleich `konten.sitzungsversion`. Sonst gilt die Anfrage als nicht angemeldet, und das Cookie wird gelöscht.
- **Neue Konten starten mit einer zufälligen Sitzungsversion** (`secrets.randbelow(2**31) + 1`), nicht mit 1. Grund: `konten.id` hat kein `AUTOINCREMENT`; wird das Konto mit der höchsten `id` gelöscht, vergibt SQLite die `id` neu. Mit Version 1 wäre das Cookie der gelöschten Person für den neuen Zugang gültig. Mit zufälliger Startversion passt es nur mit Wahrscheinlichkeit 1 : 2³¹. Gilt für die Verwaltung und das Kommando (Entscheidung Claude; Alternative `AUTOINCREMENT` hätte einen Neuaufbau der Tabelle per Migration gebraucht). Test: Konto löschen, neues anlegen (gleiche `id`), altes Cookie → nicht angemeldet.
- Abmelden löscht nur das Cookie dieses Geräts. «Überall abmelden» gibt es über «Passwort zurücksetzen».

## Zugriffsprüfung (Bausteine für alle Routen)

`app/sitzung.py` stellt FastAPI-Dependencies bereit:

- `aktuelles_konto(request, db) -> Konto | None` — liest und prüft das Cookie (Ergebnis pro Anfrage in `request.state` zwischengespeichert).
- `braucht_lehrperson` und `braucht_auftraggeberin` — liefern das `Konto` oder brechen ab:
  - nicht angemeldet → **303 auf `/`** (bei GET) bzw. 303 auf `/` (bei POST; die Eingabe geht verloren, das ist bei abgelaufener Anmeldung in Ordnung, weil «Angemeldet bleiben» Standard ist),
  - falsche Rolle → **403** mit Fehlerseite «Kein Zugriff».
- `Konto` ist eine kleine, unveränderliche Dataclass (`id`, `anzeigename`, `benutzername`, `rolle`, `sitzungsversion`).
- Regel für #16–#18: Objekte einer anderen Lehrperson (Einträge, Aufnahmen) ergeben **404**, nicht 403, damit nicht erkennbar ist, ob sie existieren. Jede Abfrage auf Einträge filtert in SQL nach `konto_id`.

Die Abbrüche laufen über eigene Exceptions (`NichtAngemeldet`, `KeinZugriff`) mit Exception-Handlern in `erstelle_app`. Für 403 und 404 gibt es eine gemeinsame Fehlerseite `fehler.html` im Seitenrahmen (Titel, ein Satz, Link «Zur Startseite»). Der bestehende Handler für `HTTPException` 404 wird so ersetzt, dass auch unbekannte Adressen diese Seite zeigen (Sicherheits-Header bleiben, das prüft schon ein Test aus #13).

## CSRF-Schutz

Doppelter Wert mit Signatur, gebunden an den Browser und bei jeder Anmeldung erneuert:

- Cookie `csrf`: zufälliger Wert (`secrets.token_urlsafe(32)`), `HttpOnly`, `SameSite=Lax`, `Secure` wie oben, `Max-Age` 30 Tage. Eine kleine Middleware setzt es, wenn es in der Anfrage fehlt, und legt den Wert in `request.state.csrf_wert` ab, damit schon die erste Seite ein gültiges Formular rendert.
- Formularfeld `csrf`: HMAC-SHA256 des Cookie-Werts mit dem geheimen Schlüssel (Zweck-Präfix `"csrf:"`), hex.
- Jede POST-Route hängt die Dependency `pruefe_csrf` an. Sie liest das Formular, vergleicht mit `hmac.compare_digest` und antwortet sonst mit **403** und der Fehlerseite («Das Formular ist abgelaufen. Bitte die Seite neu laden.»).
- Anmelden und Abmelden setzen einen neuen `csrf`-Wert (gegen untergeschobene Werte vor der Anmeldung).
- In Templates: globale Jinja-Funktion `csrf_feld(request)` gibt das versteckte Feld als `Markup` zurück; eingebunden über `app/vorlagen.py`. Uploads per `fetch` (#17) schicken dasselbe Feld im `FormData` mit.
- Begründung gegen ein Token im Sitzungs-Cookie: Die Login-Seite braucht den Schutz schon vor der Anmeldung; ein einziger Mechanismus für beide Fälle ist einfacher. Gegen eine Prüfung des `Origin`-Headers: Mit `Referrer-Policy: no-referrer` senden Browser bei POST `Origin: null`.

Ein Test stellt sicher, dass **jede** POST-Route ohne gültiges `csrf`-Feld mit 403 antwortet (über das Routen-Inventar, siehe Prüfung).

## Passwörter

- `bcrypt.hashpw(passwort.encode(), bcrypt.gensalt())` (Kostenfaktor 12, Standard); in Tests per Einstellung auf 4 gesenkt (Fixture), damit die Tests schnell bleiben. Umsetzung: Modulvariable `BCRYPT_RUNDEN` in `app/konten.py`, Tests patchen sie.
- Regeln beim Setzen: mindestens 8 Zeichen, höchstens 72 Bytes (bcrypt 5 wirft sonst `ValueError`). Meldung bei zu lang: «Das Passwort ist zu lang.»
- Beim Anmelden: Passwort über 72 Bytes → gilt als falsch (ohne Exception). Unbekannter Benutzername → trotzdem ein `bcrypt.checkpw` gegen einen festen Dummy-Hash, damit die Antwortzeit nicht verrät, ob es den Benutzernamen gibt.
- **Passwort-Vorschlag:** Die Formulare «Neuer Zugang» und «Neues Passwort» sind mit einem lesbaren Vorschlag vorausgefüllt (drei Silbengruppen aus Konsonant-Vokal-Paaren plus zwei Ziffern, z. B. `lomi-saku-pete-47`, mit `secrets` erzeugt, ohne leicht verwechselbare Zeichen). Das Feld ist ein normales Textfeld (kein Passwortfeld), damit die Auftraggeberin das Passwort sieht und der Lehrperson weitergeben kann. Nach dem Speichern zeigt die Bestätigung das Passwort ein letztes Mal an («Bitte notieren, es wird danach nicht mehr angezeigt.»). Begründung: Sie verteilt die Zugänge bei der Einführung persönlich; ein vorgeschlagenes Passwort erspart ihr das Ausdenken und ist am Handy abtippbar.
- Benutzername: 3–40 Zeichen, nur Kleinbuchstaben a–z, Ziffern, Punkt, Bindestrich (wird beim Anlegen kleingeschrieben und getrimmt). Eindeutigkeit ohne Gross-/Kleinschreibung erzwingt schon die Datenbank; Meldung «Diesen Benutzernamen gibt es schon.» Anmeldung ist unabhängig von Gross-/Kleinschreibung und ignoriert Leerzeichen am Rand.
- Anzeigename: 1–60 Zeichen, getrimmt.

## Schutz gegen Durchprobieren

Im Arbeitsspeicher (eine Maschine, ein Prozess; ein Neustart setzt die Zähler zurück, das ist in Ordnung):

- Klasse `Anmeldeschutz` in `app/anmeldeschutz.py` mit einstellbarer Uhr (für Tests), gehalten in `app.state.anmeldeschutz`.
- Zählt **Fehlversuche** in einem gleitenden Fenster von 15 Minuten, getrennt pro Benutzername (kleingeschrieben) und pro Client-Adresse.
- Sperre: ab **5** Fehlversuchen pro Benutzername oder **20** pro Adresse im Fenster. Während der Sperre wird auch ein richtiges Passwort abgelehnt (sonst ginge das Durchprobieren weiter), ohne bcrypt-Prüfung. Meldung (429): «Zu viele Fehlversuche. Bitte in 15 Minuten nochmals versuchen.»
- Erfolgreiche Anmeldung löscht die Fehlversuche dieses Benutzernamens (nicht die der Adresse).
- **Client-Adresse:** In Produktion der Header `Fly-Client-IP` (setzt der fly-Proxy), sonst `request.client.host`. Nicht `X-Forwarded-For` (das linke Feld kann der Client selbst setzen). Die Adresse wird nur im Arbeitsspeicher gehalten und nirgends gespeichert.
- Speicher begrenzen: Einträge, deren Fenster abgelaufen ist, werden beim Zugriff entfernt; höchstens 10 000 Schlüssel (danach werden die ältesten verworfen).
- Bewusst in Kauf genommen: Wer einen Benutzernamen kennt, kann diesen Zugang 15 Minuten sperren. Bei 5 bekannten Personen ist das harmlos, und nach 15 Minuten ist es vorbei.

## Zugänge verwalten

Seite «Zugänge» (`/verwaltung/zugaenge`), mobile-first als Karten:

- Liste aller Lehrpersonen: Anzeigename, Benutzername, angelegt am; pro Karte die Links «Neues Passwort» und «Löschen». Das eigene Konto der Auftraggeberin erscheint nicht in der Liste.
- Formular «Neuer Zugang»: Anzeigename, Benutzername, Passwort (vorausgefüllt). Fehler zeigen das Formular mit den eingegebenen Werten und einer Meldung pro Feld.
- **Löschen:** Bestätigungsseite «Zugang *Anzeigename* löschen? Dabei werden auch N Antworten, M Tagebucheinträge und K Aufnahmen gelöscht. Das lässt sich nicht rückgängig machen.» Knopf «Endgültig löschen» (POST). Die Zahlen kommen aus der Datenbank (in #14 sind es noch 0, die Abfrage steht aber).
- Löschen entfernt zuerst die Aufnahme-Dateien des Kontos aus `aufnahmen_verzeichnis` (Dateinamen aus der Tabelle `aufnahmen`), dann die Kontozeile (Kaskade entfernt Antworten, Tagebucheinträge, Aufnahmen-Zeilen). Fehlt eine Datei, wird das ignoriert. Dateinamen aus der Datenbank werden nur als Name (`Path(name).name`) im Aufnahmen-Ordner verwendet, nie als Pfad.
- Nach jeder Aktion: 303 zurück auf die Liste mit einer kurzen Bestätigung oben (über Query-Parameter mit festem Schlüssel, z. B. `?erledigt=angelegt`; der Text kommt aus einer festen Tabelle im Code, nicht aus der Adresse). Ausnahme «angelegt» und «Passwort gesetzt»: Diese zeigen das Passwort einmal an und werden deshalb direkt gerendert (200), nicht umgeleitet.

## Kommando für den Betreiber

`python -m app.kommandos` mit Unterbefehlen (argparse):

- `auftraggeberin-anlegen --benutzername NAME --anzeigename "TEXT"` — legt ein Konto der Rolle Auftraggeberin an.
- `passwort-setzen --benutzername NAME` — setzt ein neues Passwort für ein beliebiges Konto und erhöht die Sitzungsversion (falls die Auftraggeberin ihr Passwort vergisst).

Das Passwort wird nie als Argument übergeben (Shell-Verlauf): mit Terminal per `getpass` (zweimal zur Bestätigung), ohne Terminal als erste Zeile von stdin (für E2E und Skripte). Das Kommando liest nur `DATEN_VERZEICHNIS` (Standard `.daten`), nicht den geheimen Schlüssel, und führt vorher die Migrationen aus. Ausgabe: eine Zeile Bestätigung oder eine verständliche Fehlermeldung mit Exit-Code 1.

Auf fly.io als `appuser`, damit die Datenbankdateien nicht root gehören (siehe README):
`fly ssh console --pty -C "setpriv --reuid=appuser --regid=appuser --init-groups python -m app.kommandos auftraggeberin-anlegen --benutzername … --anzeigename …"`. Der genaue Aufruf wird beim Deploy geprüft und in der README festgehalten. Ein Make-Ziel ist nicht nötig (einmalige Handlung).

## Seitenrahmen und Gestaltung

- `basis.html` erhält einen Kopf: links der Titel des Instruments (vorerst fest «Reflexionsinstrument»; #15 macht ihn zum Inhalt), rechts, wenn angemeldet, der Anzeigename und ein Knopf «Abmelden» (Formular mit POST und CSRF-Feld). Blöcke für Navigation, damit #16 die Lehrpersonen-Navigation und #15/#18 die Verwaltungsnavigation einsetzen können.
- Login-Seite: Titel, Felder Benutzername (`autocomplete="username"`, `autocapitalize="none"`, `autocorrect="off"`), Passwort (`autocomplete="current-password"`), Häkchen «Angemeldet bleiben» (an), Knopf «Anmelden». Kurzer Hilfetext «Den Zugang erhältst du von der Projektleitung.» Ein markierter Bereich `{% block gast %}` unter dem Formular für #19.
- Fehlermeldung bei falscher Anmeldung: «Benutzername oder Passwort stimmt nicht.» (verrät nicht, welches).
- Stil: vorhandene Klassen aus `style.css` (`karte`, `formular`, `feld`, `knopf`, `fehler`, `hinweis`, `gedaempft`). Neue Klassen nur, wenn nötig, am Ende der Datei in einem Abschnitt «Pilot: Anmeldung und Verwaltung». Kein Inline-CSS, kein Inline-JavaScript.
- Anrede: «du» wie im Prototyp (die Auftraggeberin kann die festen Texte in #20 anpassen lassen).

## Kopfzeilen

- `Cache-Control: no-store` auf allen Antworten ausser `/static/…`. Begründung: einfacher und sicherer als pro Seite zu entscheiden; die Seiten sind klein. Umsetzung in `SicherheitsHeaderMiddleware` (Pfad-Prüfung).

## Datenmodell

Keine Migration nötig: `konten` mit `sitzungsversion` steht seit 001.

**Vergabe der Migrationsnummern** (damit parallel gebaute Issues nicht kollidieren; `migriere` überspringt kleinere Nummern als `user_version`, Lücken sind erlaubt, eine zu kleine Nummer nach einem späteren Merge liefe aber nie):

| Nummer | Issue |
|---|---|
| 002 | #15 Eingabemaske |
| 003 | #16 Lehrpersonen-Ansicht, inklusive allem, was #17, #18, #19 an Schema brauchen |
| 004 und folgende | nur falls #17–#19 doch etwas brauchen: Nummer erst beim Merge vergeben, nach dem Rebase auf `main` |

## Prüfung und Nachweis

**pytest** (Fixtures in `conftest.py`: `konto_lehrperson`, `konto_auftraggeberin`, `anmelden(client, benutzername, passwort)`, CSRF-Helfer, der den Wert aus einer gerenderten Seite liest):

- Anmelden mit richtigem Passwort → 303 auf die Startseite der Rolle; Cookie mit `HttpOnly`, `SameSite=Lax`; `Secure` nur mit `produktion=True`; `Max-Age` nur mit «Angemeldet bleiben».
- Falsches Passwort, unbekannter Benutzername, Passwort über 72 Bytes → gleiche Meldung, kein Cookie.
- Benutzername in anderer Schreibweise und mit Leerzeichen meldet an.
- 5 Fehlversuche → auch das richtige Passwort wird 15 Minuten abgelehnt; nach Ablauf (Uhr vorgestellt) geht es wieder. Sperre pro Adresse nach 20 Fehlversuchen über verschiedene Benutzernamen. `Fly-Client-IP` zählt nur in Produktion.
- Manipuliertes Cookie, abgelaufenes Cookie (nicht dauerhaft nach 12 h, dauerhaft nach 30 Tagen), Cookie eines gelöschten Kontos → nicht angemeldet.
- Dauerhafte Sitzung älter als 1 Tag wird verlängert.
- Passwort zurücksetzen und Konto löschen beenden bestehende Sitzungen (alter Cookie → nicht angemeldet).
- Lehrperson erreicht keine Seite unter `/verwaltung` (403); Auftraggeberin erreicht `/lehrperson` nicht (403).
- **Routen-Inventar:** Über `app.routes` wird jede Route gesammelt. Jede GET-Route ausser der Liste `OEFFENTLICH = {"/", "/healthz", "/static"}` (künftig plus `/gast/…` aus #19) antwortet ohne Anmeldung mit 303 auf `/`. Jede POST-Route ohne CSRF-Feld antwortet mit 403. Pfadparameter werden mit `1` belegt. Neue Routen späterer Issues fallen damit automatisch unter den Test.
- Verwaltung: anlegen (Validierungen, doppelter Benutzername), Passwort setzen (alte Sitzung ungültig, neues Passwort gilt), löschen (Zeile weg, Kaskade, Aufnahme-Datei im Ordner weg), fremde `id` (Auftraggeberin, unbekannt) → 404.
- Kommando: legt Konto an (stdin), verweigert doppelten Benutzernamen, `passwort-setzen` erhöht die Sitzungsversion.
- `Cache-Control: no-store` auf Seiten, nicht auf `/static`.

**E2E** (`tests/e2e-pilot.mjs`, Abschnitt «Abläufe» erweitern; vorher Auftraggeberin per Kommando mit stdin anlegen), in 390 px, hell und dunkel für die Login-Seite, Desktop einmal:
1. `/` zeigt die Login-Seite, kein horizontales Scrollen, keine Konsolenfehler.
2. Falsches Passwort → Meldung sichtbar.
3. Auftraggeberin meldet sich an, legt einen Zugang an, sieht das Passwort, meldet sich ab.
4. Lehrperson meldet sich mit diesem Passwort an, sieht ihre Startseite mit Anzeigename, öffnet `/verwaltung` → «Kein Zugriff».
5. Screenshots: Login, Fehlermeldung, Zugänge-Liste, Passwort-Anzeige, Lehrperson-Start, Kein Zugriff.

Die werfende Variante von `pruefe` aus `docs/beobachtungen.md` wird jetzt nötig (Abläufe mit abhängigen Schritten): Hilfsfunktion `muss(bedingung, text)`, die bei Fehlschlag den Ablauf abbricht.

**fly.io:** Nach dem Deploy Konto der Auftraggeberin anlegen (Koschi gibt Benutzername und Anzeigename an, das Passwort tippt er selbst), Login-Seite in 390 px prüfen, `/healthz` 200, Cookie-Attribute per `curl -i` (Secure gesetzt).

## Übergabe an spätere Issues

- Jede neue Seite nutzt `braucht_lehrperson` bzw. `braucht_auftraggeberin`, jedes Formular `{{ csrf_feld(request) }}` und jede POST-Route `pruefe_csrf`. Das Routen-Inventar erzwingt die ersten beiden Punkte für GET bzw. POST.
- Das Akzeptanzkriterium «kein Zugriff auf Einträge, Aufnahmen und Adressen einer anderen Lehrperson» prüfen #16 (Einträge, Antworten) und #17 (Aufnahmen) mit je einem Test über zwei Lehrpersonen-Konten; erwartet ist 404.
- Löschen eines Kontos entfernt die Aufnahme-Dateien bereits (#14); #17 muss nur das Löschen einzelner Einträge samt Datei ergänzen.

## Dem Umsetzer überlassen

Genaue Texte der Bestätigungen und Fehlermeldungen (im Ton oben), Aufteilung der Tests auf Dateien, Aufbau des Passwort-Vorschlags im Detail, Gestaltung der Übersichtsseite der Verwaltung.
