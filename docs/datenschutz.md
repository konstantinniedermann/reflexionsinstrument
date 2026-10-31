# Datenschutz technisch (#8)

Welche Daten die Pilot-Version speichert, was sie bewusst nicht speichert, was in den Logs landet und welche Hinweistexte die Lehrpersonen sehen. Die Löschung nach dem Pilot steht im [Löschkonzept](loeschkonzept.md). Die rechtliche Seite (Einwilligung, Vorgaben der Hochschule) klärt die Auftraggeberin selbst (#3).

Die Entscheidungen hier hat Claude getroffen (Projektregel «Fragen selbst beantworten»), mit Begründung jeweils dabei.

## Welche Daten entstehen

| Daten | Wo | Zweck | Personenbezug |
|---|---|---|---|
| Anzeigename, Benutzername, Passwort-Hash (bcrypt), Rolle, Sitzungsversion, Erstelldatum | `konten` | Anmeldung, Zuordnung der Einträge für die Auftraggeberin | ja |
| Antworten, Tagebucheinträge mit Erstell- und Änderungszeitpunkt | `antworten`, `tagebucheintraege` | Forschungsdaten. Die Zeitpunkte braucht der Export (Woche) | ja, inhaltlich heikel |
| Sprachaufnahmen mit Dauer in Sekunden (`aufnahmen.dauer_sekunden`) | `/data/aufnahmen/`, Verweis in `aufnahmen` | Tagebuch und Antworten zum Einsprechen | ja, Stimme |
| Zwischendatei beim Hochladen einer Aufnahme | temporärer Ordner der Maschine, nicht auf dem Volume | Verarbeitung der Anfrage | ja, Stimme; gelöscht am Ende der Anfrage |
| Texte der Auftraggeberin (Infoblock, Runden, Fragen, Impulse, Hinweise) | übrige Tabellen | Inhalt | nein |
| Sitzungs-Cookie im Browser | Browser | angemeldet bleiben. Enthält Konto-ID und Sitzungsversion, signiert. Technisch nötig, kein Tracking | ja (Konto-ID) |
| Cookie `csrf` im Browser | Browser | Schutz der Formulare vor fremden Seiten. Zufallswert ohne Personenbezug, 30 Tage gültig | nein |
| Entwurf eines noch nicht gespeicherten Texts | Browser-Tab (`sessionStorage`) | Schutz vor Verlust beim Neuladen | ja, bis gespeichert, verworfen, abgemeldet oder Tab geschlossen |
| Noch nicht gespeicherte Aufnahme | Arbeitsspeicher des Browser-Tabs | Anhören vor dem Speichern | ja; weg beim Speichern, Neu aufnehmen, Neuladen oder Schliessen |
| Zähler für Fehlversuche beim Anmelden | nur Arbeitsspeicher der App | Schutz gegen das Durchprobieren von Passwörtern | Client-IP und eingegebener Benutzername |
| Benachrichtigungs-Abo (#37): Adresse beim Push-Dienst des Geräteherstellers, zwei öffentliche Schlüssel des Geräts, Konto, Zeitpunkt | `push_abos` | Erinnerungen der Auftraggeberin zustellen; nur wenn die Person auf dem Gerät einschaltet | ja (über das Konto); die Adresse kennzeichnet das Gerät beim Push-Dienst |
| «Nicht jetzt» bei der Einladung zu Benachrichtigungen | Browser (`localStorage`, Wert `1`) | Einladung auf der Startseite nicht erneut zeigen | nein |

**Umsetzung in #14:** Für die Begrenzung der Fehlversuche hält die App die Client-IP aus dem Header `Fly-Client-IP` und den eingegebenen Benutzernamen nur im Arbeitsspeicher (höchstens 15 Minuten pro Eintrag; veraltete Einträge räumt jeder Anmeldeversuch weg), ohne sie in die Datenbank oder in Logs zu schreiben. Sie verschwindet beim Neustart der Maschine (spätestens beim automatischen Anhalten bei Inaktivität).

**Nicht gespeichert:** E-Mail-Adressen, Telefonnummern, IP-Adressen (dauerhaft), Browser- oder Gerätekennungen ausser dem freiwilligen Benachrichtigungs-Abo, Standort, Nutzungsstatistik. Benachrichtigungen laufen über das Abo und brauchen keine Kontaktdaten.

**Benachrichtigungen (#37):** Die App schickt die Nachricht verschlüsselt (RFC 8291) an den Push-Dienst des Geräteherstellers bzw. Browsers (Apple, Google, Mozilla oder Microsoft, ausserhalb der Schweiz/EU). Der Dienst sieht Abo-Adresse, Zeitpunkt und Grösse, nicht den Inhalt. Der Inhalt ist allein der Text der Auftraggeberin, nie ein Eintrag. Die App schickt nur an Adressen dieser Dienste (Prüfung beim Speichern, `app/push_abos.py`). Ins Log kommen nur Dienst und Status, nie Adresse oder Text (Test `test_log_ohne_endpunkt_und_text`). Der Hinweistext `hinweis_benachrichtigung` steht auf der Info-Seite beim Ein- und Ausschalten. Das Abo gehört dem Gerät: Abmelden schaltet es nicht aus; es wechselt zum nächsten Konto, das sich auf dem Gerät anmeldet. Ausschalten geht auf der Info-Seite. Weil jede Nachricht an alle geht, erfährt dadurch niemand etwas über ein anderes Konto.

## Prüfung der Datensparsamkeit

Stand 30.10.2026 (Grundgerüst aus #13 plus dieses Issue).

| Prüfpunkt | Ergebnis | Absicherung |
|---|---|---|
| Keine E-Mail-Adressen | Das Schema hat kein Feld dafür. «Passwort vergessen» läuft über die Auftraggeberin. | `app/migrationen/001_grundschema.sql`, [Anforderungen](anforderungen.md#anmeldung-und-konten) |
| Kein Tracking | Kein Analyse-Skript, nur zwei technisch nötige Cookies (Sitzung und `csrf`), kein JavaScript von Dritten | CSP `script-src 'self'` (`app/sicherheit.py`) |
| Gast-Ansicht speichert nichts | Kein Login, kein eigenes Cookie, Datenbank nur lesend; Eingaben werden geprüft und verworfen | Test `test_gast_datenbank_unveraendert` |
| Keine externen Ressourcen | Templates und CSS laden nichts von aussen. Schriften sind Systemschriften (`Helvetica Neue`, `Helvetica`, `Arial`), kein `@import`, kein `url(…)` | Test `test_vorlagen_und_css_laden_nichts_von_aussen` (alle Templates und CSS-Dateien, auch künftige), Test `test_startseite_ohne_externe_quellen`, CSP `default-src 'self'` |
| Keine Weitergabe beim Verlassen der Seite | Kein Referrer an fremde Seiten | `Referrer-Policy: no-referrer` |
| Keine IP-Adressen in Logs | Bis jetzt protokollierte uvicorn jede Anfrage mit echter Client-IP und Pfad, auch die Health-Checks alle 30 Sekunden. Abgeschaltet, siehe [Logs](#logs) | Test `test_produktion_schreibt_keine_zugriffsprotokolle` |
| Gelöschte Einträge sind wirklich weg | Ohne Einstellung bleibt der Text eines gelöschten Eintrags als freier Speicher in der Datenbankdatei. Jetzt überschreibt SQLite ihn (`PRAGMA secure_delete = ON`). Reste in der Begleitdatei `-wal` und in Snapshots behandelt das [Löschkonzept](loeschkonzept.md#löschen-während-der-laufzeit) | Test `test_geloeschter_eintrag_ist_aus_der_datei_entfernt` |
| Aufnahmen ohne Zusatzangaben | Der Browser liefert WebM/Opus bzw. MP4/AAC; die App wandelt nichts um und schickt nichts weiter | #17 prüft an einer Testaufnahme, dass keine Geräte- oder Ortsangaben in der Datei stehen |
| Daten in der EU | Region Frankfurt (`primary_region = "fra"`) | `fly.toml` |

## Logs

**Entscheidung:** uvicorn läuft in Produktion mit `--no-access-log` (`Dockerfile`).

**Begründung:**
- Das Zugriffsprotokoll schreibt pro Anfrage die Client-IP und den Pfad. Mit `--proxy-headers` ist das die echte IP der Lehrperson, zusammen mit dem Zeitpunkt. Daraus lässt sich ablesen, wer wann von wo schreibt.
- Die Logs gehen an fly.io, bleiben dort 7 Tage und lassen sich nicht löschen ([Löschkonzept](loeschkonzept.md#logs-bei-flyio)). Was nicht entsteht, muss nicht gelöscht werden.
- Der Nutzen für die Fehlersuche ist bei 5 Personen klein. Fehler mit Ablauf (Traceback), Start und Stopp schreibt uvicorn weiterhin.

**Verworfen:** IP-Adressen im Log kürzen (eigenes Log-Format, mehr Code für wenig Nutzen); Zugriffsprotokoll behalten (siehe oben).

**Nachweis:** Lokal mit denselben Argumenten gestartet: Mit Zugriffsprotokoll erscheint `203.0.113.7:0 - "GET / HTTP/1.1" 200 OK`, mit `--no-access-log` nur noch Start und Stopp. Auf fly.io wirkt es ab dem nächsten Deploy. Danach zuerst die echte Startzeile prüfen (`fly ssh console -C "sh -c 'for f in /proc/[0-9]*/cmdline; do tr \"\\0\" \" \" < \$f; echo; done | grep uvicorn'"`, enthält `--no-access-log`; das Image hat kein `ps`, der Stern löst `sh` auf der Maschine auf), dann zeigt `fly logs` keine Zeilen `GET /healthz` mehr. Der Deploy soll vor dem Testlauf (#9) erfolgen, damit nie eine IP-Adresse einer Lehrperson in die Logs gelangt.

**Regel für alle weiteren Issues:** Eigene Log-Meldungen enthalten keine Inhalte, keine Benutzernamen, keine Passwörter und keine IP-Adressen. Fehlversuche beim Anmelden (#14) werden höchstens als Ereignis ohne diese Angaben geloggt. Muss das Zugriffsprotokoll für eine Fehlersuche während der Laufzeit vorübergehend eingeschaltet werden, kommt das ins Löschprotokoll (#10).

## Hinweistexte

Die Hinweise sind Inhalt, kein Code: Sie liegen in der Tabelle `texte` (`schluessel`, `inhalt`) und die Auftraggeberin bearbeitet sie in der Eingabemaske (#15). Den Wortlaut schreibt sie. Die Platzhalter unten sind erfunden, aber so formuliert, dass sie im Notfall stehen bleiben könnten. Weil die Anrede (Du oder Sie) noch offen ist, kommen sie ohne Anrede aus.

| Schlüssel | Wo er erscheint | Zweck | Platzhalter |
|---|---|---|---|
| `hinweis_tagebuch` | Tagebuch: gut sichtbar über dem Eingabefeld bzw. dem Aufnahmeknopf, bei jedem neuen und geänderten Eintrag, für alle drei Arten (frei, Leitfragen, Aufnahme). Empfehlung an #16: derselbe Text auch über den Fragen einer Runde. | Keine Angaben, die Rückschlüsse auf Personen erlauben (Anforderung, Muss) | «Bitte keine Namen, Orte oder Klassenbezeichnungen notieren und nichts, was Rückschlüsse auf Kinder, Eltern oder Kolleginnen und Kollegen erlaubt. Situationen lassen sich allgemein beschreiben, zum Beispiel ‹ein Kind aus der Klasse›.» |
| `hinweis_wer_sieht_was` | Startseite der Lehrperson, unter der Begrüssung, immer sichtbar | Transparenz: Die Auftraggeberin liest alle Einträge mit Namen, schon während der Laufzeit | «Die anderen Lehrpersonen sehen die Einträge nicht. Die Projektleiterin liest alle Einträge mit Namen und hört die Aufnahmen an, schon während der vier Wochen. Sie dienen ihr als Grundlage für die Gespräche nach dem Projekt.» |
| `hinweis_gast` | Gast-Ansicht («Ansehen ohne Konto», #19): als Band oben auf jeder Seite | Klarstellen: Ansicht ohne Speichern, keine Einträge sichtbar | «Ansicht ohne Speichern. Hier lässt sich das Instrument mit den bereits freigeschalteten Inhalten ansehen. Eingaben werden nicht gespeichert, und Einträge von Lehrpersonen sind nicht sichtbar.» |
| `hinweis_datenspeicherung` | Infoblock, als fester letzter Abschnitt «Datenschutz». Fest heisst: nicht löschbar, nur der Text ist bearbeitbar. Damit sieht ihn auch der Gast. | Wo die Daten liegen, was gespeichert wird, wann gelöscht wird | «Die Einträge und Aufnahmen liegen auf einem Server in Frankfurt (EU). Gespeichert werden nur Name, Benutzername, Passwort (unlesbar gespeichert), Einträge und Aufnahmen, keine E-Mail-Adressen. Eigene Einträge lassen sich jederzeit ändern und löschen. Nach Abschluss des Projekts werden alle Daten gelöscht.» Sobald das Löschdatum feststeht, ergänzt die Auftraggeberin es hier. |
| `hinweis_aufnahme` | Neben dem Aufnahmeknopf (#17), im Tagebuch und bei Fragen | Die Stimme ist ein besonders persönliches Merkmal, und beim Sprechen rutscht ein Name leichter heraus | «Die Aufnahme wird gespeichert, und die Projektleiterin hört sie an. Bitte auch beim Sprechen keine Namen nennen.» |
| `hinweis_benachrichtigung` | Auf der Info-Seite bei den Benachrichtigungen (#37) | Benachrichtigungen sind freiwillig; die Nachricht läuft über einen Dienst des Geräteherstellers ausserhalb der Schweiz/EU | «Benachrichtigungen sind freiwillig und lassen sich hier jederzeit ausschalten. Sie enthalten nur kurze Erinnerungen der Projektleiterin, nie Einträge. Zugestellt werden sie verschlüsselt über den Dienst des Geräteherstellers (zum Beispiel Apple oder Google). Dieser sieht, wann eine Nachricht an das Gerät geht, aber nicht ihren Inhalt.» |

**Für #15 (Eingabemaske):**
- #15 trägt die fünf Schlüssel mit den Platzhaltern in ein Register fester Texte im Code ein (`app/texte.py`, siehe Design zu #15). Fehlt ein Text in der Tabelle `texte`, gilt der Platzhalter, und die Maske markiert ihn als noch nicht bestätigt. Eine Migration braucht es dafür nicht.
- In der Eingabemaske stehen sie unter einem eigenen Bereich «Hinweise», jeweils mit dem Ort aus der Spalte «Wo er erscheint» als Erklärung in einfacher Sprache.
- Ein Hinweis darf nicht leer gespeichert werden. Einfache Formatierung wie bei den anderen Texten.
- Angezeigt werden sie von #16 (Lehrpersonen-Ansicht), #17 (Aufnahme) und #19 (Gast-Ansicht).
