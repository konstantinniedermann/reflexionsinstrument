# Design: Push-Benachrichtigungen von der Auftraggeberin an die Lehrpersonen (#37)

Grundlage: Wunsch der Auftraggeberin vom 31.10.2026: «Wenn die Lehrpersonen die Seite auf dem Handy auf dem Startbildschirm speichern, können wir dann mit Push-Benachrichtigungen arbeiten, die ich auslöse und die anderen empfangen?» Der Betreiber will es ausprobieren und hat die Pakete `http-ece` und `py-vapid` freigegeben. [Anforderungen](../../anforderungen.md) (bisher «Bewusst nicht gebaut: Benachrichtigungen»), [datenschutz.md](../../datenschutz.md), [loeschkonzept.md](../../loeschkonzept.md), [Design Anmeldung](2026-10-30-anmeldung-design.md) (CSRF, Rollen, Routen-Inventar). Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»).

## Zweck

Die Auftraggeberin erinnert die Lehrpersonen bisher selbst per WhatsApp an Impulse und Runden. Neu kann sie aus der Verwaltung eine kurze Nachricht schicken, die auf den Handys der Lehrpersonen als Benachrichtigung erscheint. Ein Tipp darauf öffnet das Instrument. Ziel ist, dass die Erinnerung direkt zum Ort führt, an dem man schreibt.

WhatsApp bleibt als Weg möglich. Benachrichtigungen sind freiwillig: Wer sie nicht einschaltet, verpasst nichts ausser der Erinnerung.

## Wie es technisch geht (Web Push)

- Eine Webseite kann Benachrichtigungen empfangen, wenn sie einen **Service Worker** (kleines Skript, das der Browser im Hintergrund behält) registriert und die Person zustimmt. Der Browser liefert dann ein **Abo**: eine Adresse beim Push-Dienst des Herstellers (Apple, Google, Mozilla) plus zwei Schlüssel.
- Der Server schickt die Nachricht verschlüsselt (RFC 8291, `aes128gcm`) an diese Adresse und weist sich mit einer Signatur aus (VAPID, RFC 8292). Der Push-Dienst stellt sie dem Gerät zu. Der Inhalt bleibt für den Push-Dienst unlesbar; er sieht nur, wann eine Nachricht an welches Abo geht.
- **iPhone/iPad:** nur ab iOS 16.4 und nur, wenn die Seite über «Teilen → Zum Home-Bildschirm» als App installiert und von dort geöffnet wurde. Dafür braucht es ein **Web-App-Manifest** (Name, Symbol, Startadresse). Die installierte App hat ihren eigenen Speicher: Man meldet sich dort einmal neu an.
- **Android (Chrome, Firefox) und Computer:** geht direkt im Browser, Installation nicht nötig.
- **Kosten:** keine. Die Push-Dienste sind kostenlos.

## Ziele

- Die Auftraggeberin schreibt in der Verwaltung unter «Benachrichtigung» einen kurzen Text (höchstens 200 Zeichen) und schickt ihn mit einem Tipp an alle Geräte, auf denen Benachrichtigungen eingeschaltet sind. Danach sieht sie, an wie viele Geräte es ging.
- Das Textfeld ist mit dem aktuellen Impuls vorbelegt, wenn es einen gibt.
- Eine Lehrperson schaltet Benachrichtigungen auf ihrem Gerät mit einem Tipp ein und auf der Info-Seite wieder aus. Die Startseite zeigt einen Hinweis, solange sie auf diesem Gerät nicht eingeschaltet sind, mit «Nicht jetzt».
- Auf einem iPhone ohne Installation erklärt der Hinweis in zwei Sätzen, wie man die Seite auf den Startbildschirm legt.
- Die Auftraggeberin kann auf ihrem eigenen Gerät ebenfalls einschalten, um zu sehen, was ankommt.
- Ein Tipp auf die Benachrichtigung öffnet das Instrument (`/`, von dort die Startseite der Rolle).

## Nicht-Ziele

- Zeitgesteuerte oder automatische Benachrichtigungen (z. B. beim Freischalten eines Impulses). Die Auftraggeberin löst jede Nachricht selbst aus.
- Nachrichten an einzelne Lehrpersonen.
- Verlauf der gesendeten Nachrichten, Lesebestätigungen, Statistik.
- Offline-Betrieb. Der Service Worker speichert keine Seiten zwischen.
- Benachrichtigungen in Gast-Ansicht und Vorschau.

## Anti-Ziele

- Kein Dienst eines Dritten für den Versand (kein Firebase-Konto, kein OneSignal). Die App spricht direkt mit den Push-Diensten der Hersteller.
- Keine Inhalte aus Einträgen und keine Namen in einer Benachrichtigung. Der Text stammt allein von der Auftraggeberin.
- Kein Versand an beliebige Adressen: Der Server schickt nur an Adressen bekannter Push-Dienste (Schutz gegen SSRF, siehe unten).
- Keine Gerätekennung ausser dem Abo selbst; kein User-Agent, kein Gerätename.

## Bausteine

### Daten

Migration `004_push_abos.sql`:

| Spalte | Inhalt |
|---|---|
| `id` | INTEGER PRIMARY KEY |
| `konto_id` | Verweis auf `konten`, `ON DELETE CASCADE` |
| `endpunkt` | Adresse beim Push-Dienst, UNIQUE |
| `p256dh`, `auth` | öffentliche Schlüssel des Geräts (base64url) |
| `erstellt` | Zeitpunkt |

Meldet ein Gerät sein Abo ein zweites Mal an (gleicher Endpunkt), wird die Zeile ersetzt und dem aktuellen Konto zugeordnet. So gehört ein Gerät nach einem Kontowechsel dem zuletzt angemeldeten Konto.

### Schlüssel (VAPID)

- Ein Schlüsselpaar P-256 für die ganze App. Der private Schlüssel kommt als Secret `VAPID_SCHLUESSEL` (PEM in base64url, eine Zeile) in die Umgebung; der öffentliche wird daraus abgeleitet.
- Kommando `python -m app.kommandos vapid-schluessel` erzeugt ein Paar und gibt den Wert für `fly secrets set` aus.
- Ohne Secret ist die Funktion aus: Die Seiten zeigen keinen Hinweis, die Verwaltung erklärt «Benachrichtigungen sind nicht eingerichtet». Die App startet trotzdem, auch in Produktion.
- Absenderangabe (`sub` der VAPID-Signatur): die Adresse der App (`https://reflexionsinstrument.fly.dev`), keine E-Mail-Adresse. Die Spezifikation erlaubt eine https-Adresse.

### Endpunkte

| Route | Wer | Zweck |
|---|---|---|
| `GET /manifest.webmanifest` | alle | Manifest mit dem Titel des Instruments (Inhalt der Auftraggeberin), `start_url: "/"`, `display: "standalone"`, Farben, Symbole |
| `GET /sw.js` | alle | Service Worker, an der Wurzel ausgeliefert, damit er für die ganze Seite gilt |
| `POST /benachrichtigung/abo` | angemeldet (beide Rollen) | Abo speichern. Formularfelder `endpunkt`, `p256dh`, `auth`, `csrf` |
| `POST /benachrichtigung/abo/loeschen` | angemeldet | Abo dieses Geräts löschen (Feld `endpunkt`), nur wenn es dem eigenen Konto gehört |
| `GET /verwaltung/benachrichtigung` | Auftraggeberin | Formular mit Anzahl Geräte |
| `POST /verwaltung/benachrichtigung` | Auftraggeberin | senden, Ergebnis anzeigen |

Die Abo-Routen erwarten Formulardaten, damit die bestehende CSRF-Prüfung (`pruefe_csrf`) unverändert gilt; das Skript liest das Token aus dem versteckten Feld der Seite. Manifest und Service Worker kommen in die Liste der öffentlichen Routen im Routen-Inventar-Test.

### Prüfung des Abos (SSRF-Schutz)

Weil der Server an die gespeicherte Adresse eine Anfrage schickt, wird sie beim Speichern geprüft:
- Schema `https`, kein Port ausser 443, keine Zugangsdaten in der Adresse, höchstens 1000 Zeichen.
- Host endet auf einen bekannten Push-Dienst: `push.apple.com`, `fcm.googleapis.com`, `push.services.mozilla.com`, `notify.windows.com`.
- `p256dh` ist ein gültiger unkomprimierter P-256-Punkt (65 Byte), `auth` 16 Byte, beides base64url.
- Höchstens 10 Abos pro Konto; beim elften wird das älteste ersetzt.

Sonst Status 400, nichts gespeichert.

### Versand

- Modul `app/push.py`: `sende(abo, nutzlast) -> Ergebnis`. Verschlüsselung mit `http_ece.encrypt(..., version="aes128gcm")`, Signatur mit `py_vapid`, Versand mit `urllib.request` (Zeitlimit 10 s), Header `TTL: 86400`, `Urgency: normal`, `Content-Encoding: aes128gcm`.
- Nutzlast JSON: `{"titel": <Titel des Instruments>, "text": <Nachricht>}`.
- Antwort 201/202: zugestellt. 404 oder 410: Abo ist ungültig und wird gelöscht. Alles andere: zählt als «nicht erreicht», Abo bleibt. Ins Log kommen Status und Host des Push-Dienstes, nie Endpunkt-Pfad, Schlüssel oder Text.
- Gesendet wird nacheinander in der Anfrage der Auftraggeberin (synchrone Route, läuft im Threadpool). Bei vier bis zehn Geräten dauert das wenige Sekunden. Der Knopf zeigt «Wird gesendet …» nicht; ein Doppelklick schickt doppelt. In Kauf genommen: Der Fall ist harmlos und eine Sperre bräuchte Zustand.
- Ergebnisseite: «Gesendet an 3 Geräte.» und falls nötig «1 Gerät war nicht erreichbar und ist entfernt.» bzw. «1 Gerät hat nicht geantwortet.»

### Service Worker (`app/static/js/sw.js`, ausgeliefert unter `/sw.js`)

- `push`: Nutzlast lesen, `showNotification(titel, {body: text, icon, badge, lang: "de"})`.
- `notificationclick`: Benachrichtigung schliessen, ein offenes Fenster der App fokussieren, sonst `/` öffnen.
- Kein `fetch`-Handler, kein Zwischenspeicher.

### Seiten-Skript (`app/static/js/benachrichtigung.js`)

Eingebunden auf Start- und Info-Seite der Lehrperson und auf der Benachrichtigungsseite der Verwaltung, nur wenn die Funktion eingerichtet ist und nicht in Gast oder Vorschau. Der öffentliche Schlüssel steht als `data-`-Attribut im HTML. Ohne JavaScript bleibt alles verborgen.

Zustände (das Skript zeigt den passenden Teil, alle anderen bleiben `hidden`):

| Zustand | Erkennung | Anzeige |
|---|---|---|
| nicht möglich, iPhone ohne Installation | kein `PushManager`, iOS, nicht `display-mode: standalone` | Anleitung «Startbildschirm» |
| nicht möglich, sonst | kein `serviceWorker` oder `PushManager` | nichts auf Start; auf Info ein Satz «Auf diesem Gerät nicht möglich.» |
| abgelehnt | `Notification.permission === "denied"` | auf Info: «Du hast Benachrichtigungen abgelehnt. Das lässt sich in den Einstellungen des Geräts ändern.» Auf Start nichts |
| aus | kein Abo | Knopf «Benachrichtigungen einschalten»; auf Start mit «Nicht jetzt» |
| an | Abo vorhanden | auf Info «Eingeschaltet» und Knopf «Ausschalten»; auf Start nichts |

«Nicht jetzt» merkt sich das Gerät in `localStorage` (ein Wert ohne Personenbezug). Einschalten: `Notification.requestPermission()` im Klick (iOS verlangt eine Nutzeraktion), dann `pushManager.subscribe({userVisibleOnly: true, applicationServerKey})`, dann POST an den Server. Ist das Abo im Browser vorhanden, aber nicht auf dem Server (z. B. nach Kontowechsel), meldet das Skript es beim Laden der Seite erneut an.

### Manifest und Symbole

- `apple-touch-icon` 180 px, Manifest-Symbole 192 und 512 px, PNG, schlicht: schwarzes Feld mit einer gelben und einer rosa Pille (Bereichsfarben aus #20). Erzeugt mit einem kleinen Python-Skript ohne Pakete, das Skript liegt nicht im Repo, nur die Bilder.
- `basis.html` verweist auf Manifest und `apple-touch-icon`; `<meta name="apple-mobile-web-app-title">` mit dem Titel.

## Texte

Feste Texte im Template, kurz und ohne Fachbegriffe («Benachrichtigungen», «Startbildschirm», kein «Push», kein «Abo»). Die Info-Seite erklärt in einem Satz, dass die Nachricht über den Dienst des Handy-Herstellers läuft und nur den Text der Projektleiterin enthält.

## Datenschutz

- `docs/datenschutz.md`: neue Zeile «Benachrichtigungs-Abo (Adresse beim Push-Dienst und Schlüssel des Geräts)», Zweck, Personenbezug ja (über das Konto). Satz «Es gibt keine Benachrichtigungen» ersetzen. Push-Dienste von Apple/Google/Mozilla als Empfänger der verschlüsselten Nachricht nennen.
- `docs/loeschkonzept.md`: Abos gehören zu Stufe 1 (mit den Konten). Ausschalten oder Konto löschen entfernt sie sofort. Secret `VAPID_SCHLUESSEL` wie `GEHEIMER_SCHLUESSEL` in Stufe 2.
- `docs/anforderungen.md`: Zeile «Erinnerungen» und «Bewusst nicht gebaut» anpassen, Herkunft A (Wunsch vom 31.10.).
- Hinweis an den Betreiber: Der Datenschutz-Hinweistext, den die Auftraggeberin bestätigt, sollte die Benachrichtigungen erwähnen. Ein Vorschlag kommt in den Bericht, der Text bleibt ihre Entscheidung.

## Prüfung

- Unit-Tests: Prüfung des Abos (erlaubte und abgelehnte Adressen, Schlüssel), Speichern/Ersetzen/Löschen nur für das eigene Konto, CSRF, Rollen, Kaskade beim Löschen des Kontos, Obergrenze pro Konto.
- Versand: Test mit echtem Schlüsselpaar eines «Geräts» im Test; die abgefangene Anfrage wird mit `http_ece.decrypt` entschlüsselt und muss die Nutzlast ergeben. VAPID-Header vorhanden und mit dem öffentlichen Schlüssel prüfbar. 410 löscht das Abo, 500 nicht.
- Ohne Secret: kein Hinweis, Verwaltung erklärt es, App startet.
- E2E (Headless-Chrome): Manifest und Service Worker laden, Service Worker registriert sich, keine CSP-Verstösse, Hinweis auf Start erscheint und verschwindet mit «Nicht jetzt», Handy-Ansicht ohne horizontales Scrollen, hell und dunkel. Ein echtes Abo ist headless nicht möglich.
- Auf fly.io: Abo im echten Chrome (Computer) einschalten, Nachricht senden, Antwort 201 des Push-Dienstes im Ergebnis. Danach iPhone und Android durch den Betreiber.
