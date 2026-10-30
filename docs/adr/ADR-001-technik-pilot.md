# ADR-001: Technik der Pilot-Version

**Status:** angenommen, 30.10.2026 (#5)

## Kontext

Aus den [Anforderungen](../anforderungen.md) ergeben sich Punkte, die der statische Prototyp nicht abdeckt:
- Login mit Passwort für 4 Lehrpersonen und die Auftraggeberin, strikte Trennung der Einträge
- Sprachaufnahmen im Tagebuch, welche die Auftraggeberin anhören kann
- Eine Eingabemaske, mit der die Auftraggeberin alle Inhalte selbst erfasst, mit Vorschau
- Eine öffentliche Gast-Ansicht ohne Speichern
- Export als Tabelle für Excel
- Läuft auf Handy, Tablet und Computer, Daten in der Schweiz oder EU
- Start in gut drei Wochen, Laufzeit 4 Wochen, danach wird alles gelöscht

## Geprüfte Optionen

| Option | Bewertung |
|---|---|
| **Umfrage-Tool** (LimeSurvey, SoSci Survey) | Verworfen. Ein Tagebuch mit Sprachaufnahmen, eine selbst gestaltete Startseite mit Impulsen und eine Gast-Ansicht lassen sich damit nicht abbilden. Die Inhalte müssten in zwei Systemen gepflegt werden. |
| **No-Code** (Formular-Baukasten, Notion und Ähnliche) | Verworfen. Die Trennung der Lehrpersonen und die Sprachaufnahme gehen nur mit Umwegen. Die Daten lägen meist in den USA, und es fallen Kosten pro Benutzer an. |
| **Node ohne Dependencies** (eingebaute Module für http, sqlite, crypto) | Möglich und passend zum Prototyp. Login, Sessions, Formular-Verarbeitung und Upload müssten aber selbst gebaut werden. Das ist mehr eigener sicherheitskritischer Code. |
| **Python mit FastAPI**, serverseitig gerenderte Seiten | **Gewählt** |

## Entscheidung

- **Python mit FastAPI**, Seiten serverseitig mit **Jinja2** gerendert, wenig JavaScript (Sprachaufnahme, Aufklappen, Vorschau)
- **SQLite** (in Python eingebaut) als Datenbank, Aufnahmen als Dateien, beides auf einem persistenten Volume
- **Hosting auf fly.io**, Region Frankfurt (EU), eine kleine Maschine, neutrale Adresse unter `fly.dev` ohne Personennamen
- Passwörter mit **bcrypt**, Sitzung als signiertes Cookie (**itsdangerous**), Formulare und Uploads mit **python-multipart**
- Sprachaufnahme über die **MediaRecorder-Schnittstelle** des Browsers, gespeichert im Format, das der Browser liefert (WebM/Opus oder MP4/AAC); keine Umwandlung auf dem Server
- Export als **CSV** im Excel-Format (Semikolon, UTF-8 mit BOM), mit Schutz vor Formel-Injection wie im Prototyp
- Gestaltung (CSS) aus dem Prototyp übernehmen. Der Prototyp selbst bleibt als Referenz bestehen, bis die Pilot-Version läuft.

Dependencies (von Koschi freigegeben): `fastapi`, `uvicorn`, `jinja2`, `python-multipart`, `itsdangerous`, `bcrypt`; für die Entwicklung `pytest`, `httpx`, `ruff`.

## Begründung

- **Bewährter Stack des Betreibers:** Derselbe Stack läuft bei Koschi bereits auf fly.io. Betrieb, Deployment und Fehlersuche sind bekannt, das zählt bei drei Wochen bis zum Start mehr als ein dependency-freier Eigenbau.
- **Serverseitig gerendert statt Single-Page-App:** Weniger JavaScript, Login per Cookie ohne Token-Handling, funktioniert auch auf älteren Handys. Für einfache Formulare genügt das.
- **SQLite statt Datenbank-Server:** 5 Konten, wenige hundert Einträge. Ein Datenbank-Server wäre zusätzliche Kosten und Betrieb ohne Nutzen. Die Löschung am Schluss ist eine Datei.
- **fly.io statt GitHub Pages:** Pages kann nur statische Seiten ausliefern. fly.io ist schon eingerichtet und kostet bei dieser Grösse wenig (Schätzung: 0–3 USD pro Monat). Ein Schweizer Anbieter hätte ein neues Konto und eine neue Einrichtung bedeutet.
- **Keine Transkription und keine Umwandlung der Aufnahmen:** Spart grosse Abhängigkeiten (ffmpeg, Sprachmodell), und die Sprachdaten verlassen den Server nicht.

## Konsequenzen

- Laufende Kosten von wenigen Franken pro Monat bis zum Abbau (von Koschi freigegeben).
- Daten in der EU, aber bei einem US-Anbieter. Die Auftraggeberin klärt die Zulässigkeit selbst.
- fly.io legt automatisch tägliche Sicherungskopien des Volumes an. Die Löschung am Schluss muss diese mit einschliessen (#8).
- Bei angehaltener Maschine dauert der erste Aufruf wenige Sekunden länger. Für den Pilot ist das in Ordnung. Stört es, bleibt eine Maschine dauerhaft an (Mehrkosten gering).
- Ein Volume hängt an genau einer Maschine. Die App läuft deshalb mit einer einzigen Maschine, das reicht für 5 Personen.
- Neue Prüfungen: pytest für Logik und Zugriffsschutz, E2E im Browser in Handy-Breite wie beim Prototyp.
