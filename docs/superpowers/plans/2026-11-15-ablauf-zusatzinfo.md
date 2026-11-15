# Zusatzinfo, unterstützende Frage, Blocksatz – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Runden bekommen eine Zusatzinfo, die nach Frage 1 erscheint, sobald diese beantwortet ist; Leitfragen werden zur aufklappbaren «unterstützenden Frage» im Tagebuch; Fliesstexte stehen im Blocksatz.

**Architecture:** Neue Spalte `runden.zusatzinfo`. Eine reine Funktion entscheidet aus den Zeilen der Runde, ob die Zusatzinfo offen ist; `kontext_runde` liefert dafür `zusatzinfo_offen`, die Vorlage teilt die Fragen in vor/nach. Tagebuch: Leitfragen als `<details>` auf «Frei schreiben» und «Frei sprechen», die eigene Auswahl und ihre Routen entfallen.

**Tech Stack:** FastAPI, Jinja2, SQLite, pytest, Ruff.

**Spec:** `docs/superpowers/specs/2026-11-15-ablauf-zusatzinfo-design.md`

## Global Constraints

- Keine neue Dependency, kein JavaScript für die neue Logik.
- Texte für Lehrpersonen auf Hochdeutsch, «du»-Form, ohne Emojis.
- Repo ist öffentlich: nur Platzhalter-Inhalte in Tests.
- Formatieren vor jedem Commit: `make format` (prüft auch Python-Blöcke in docs/*.md).

## Review Focus

1. Frage 1 ist eine Skala mit «Keine Angabe» → gilt als unbeantwortet, Zusatzinfo bleibt zu (Test in Task 2).
2. Frage 1 nur als Aufnahme beantwortet (Text leer) → Zusatzinfo offen (Test in Task 2).
3. Antwort auf Frage 1 gelöscht, Frage 2 hat Antwort → Zusatzinfo bleibt offen, Antworten bleiben sichtbar (Test in Task 2).
4. Speichern mit Frage 1 leer, solange die Fragen 2/3 ausgeblendet sind → löscht keine Antworten der ausgeblendeten Fragen (fehlende Felder bleiben unverändert, `lies_runden_eingaben`; Test in Task 2).
5. Runde mit Zusatzinfo, aber nur einer Frage → Zusatzinfo erscheint nach Frage 1 ohne Folgefragen (Test in Task 2).

---

### Task 1: Datenmodell und Eingabemaske für die Zusatzinfo

**Files:**
- Create: `app/migrationen/005_zusatzinfo.sql` (`ALTER TABLE runden ADD COLUMN zusatzinfo TEXT;`)
- Modify: `app/inhalte.py` (`_RUNDEN_SQL`, `_pruefe_runde`, `lege_runde_an`, `aendere_runde`), `app/routen/verwaltung_inhalte.py` (Formularfeld `zusatzinfo` beim Anlegen und Bearbeiten), `app/templates/verwaltung/inhalte/formular_runde.html`, `app/templates/verwaltung/inhalte/runde.html`, `app/kommandos.py` (Platzhalter-Import liest optional `zusatzinfo`), `tests/testdaten.py` (`lege_runde_an(..., zusatzinfo: str | None = None)`)
- Test: `tests/test_verwaltung_inhalte.py`, `tests/test_inhalte.py`

**Interfaces:**
- Produces: `lege_runde_an(db, titel, fallbeispiel, freischaltdatum, zusatzinfo="") -> int`, `aendere_runde(db, runde_id, titel, fallbeispiel, freischaltdatum, zusatzinfo="") -> None`; Zeilen aus `runden()`/`runde()` haben Spalte `zusatzinfo`.

- [ ] Test: Runde mit Zusatzinfo anlegen und bearbeiten über die Verwaltung; Detailseite zeigt den Text und «Erscheint nach Frage 1». Leere Zusatzinfo wird als NULL gespeichert.
- [ ] Test fällt durch, Umsetzung (Feld unter dem Fallbeispiel, Label «Zusatzinfo (freiwillig)», Hilfetext «Erscheint nach der ersten Frage, sobald die Lehrperson sie beantwortet hat.»), Tests grün, Commit `feat: Zusatzinfo pro Runde in der Eingabemaske`.

### Task 2: Zusatzinfo in der Runde (Lehrperson, Gast, Vorschau)

**Files:**
- Modify: `app/seiten_lehrperson.py` (`kontext_runde`), `app/routen/lehrperson.py` (`runde_speichern`: Anker `zusatzinfo`), `app/templates/lehrperson/runde.html`
- Test: `tests/test_runde.py`, `tests/test_ohne_speichern.py`

**Interfaces:**
- Produces: `zusatzinfo_offen(zeilen: list[dict], antworten: dict[int, Row]) -> bool` in `app/seiten_lehrperson.py`. Offen, wenn eine Zeile `wert` hat (Skala `"1"`–`"5"`, Freitext nicht leer nach `strip`) oder eine gespeicherte Antwort mit `aufnahme_id` hat. Kontext bekommt `zusatzinfo_offen: bool` (immer `True`, wenn die Runde keine Zusatzinfo hat).

- [ ] Tests (`tests/test_runde.py`): ohne Antwort zeigt die Seite Frage 1 und den Satz «Sobald du deine Antwort gespeichert hast, folgt eine Zusatzinformation mit weiteren Fragen.», nicht aber Zusatzinfo und Frage 2; nach dem Speichern von Frage 1 Weiterleitung mit `#zusatzinfo`, die Seite zeigt Zusatzinfo (`id="zusatzinfo"`) vor Frage 2; Skala-Frage 1 mit «Keine Angabe» → zu; Antwort nur als Aufnahme → offen; Frage 1 gelöscht, Frage 2 beantwortet → offen; Speichern bei verdeckten Fragen löscht deren Antworten nicht; Runde ohne Zusatzinfo zeigt alle Fragen; Runde mit Zusatzinfo und nur einer Frage.
- [ ] Test (`tests/test_ohne_speichern.py`): Gast schickt Frage 1 ab → Antwortseite zeigt die Zusatzinfo.
- [ ] Umsetzung, Tests grün, Commit `feat: Zusatzinfo erscheint nach der ersten beantworteten Frage`.

### Task 3: Unterstützende Frage im Tagebuch

**Files:**
- Modify: `app/templates/lehrperson/tagebuch_wahl.html` (Leitfragen-Abschnitt weg), `app/templates/lehrperson/tagebuch_neu.html` und `aufnahme_tagebuch.html` (neu: Include `lehrperson/_unterstuetzung.html`), `app/seiten_lehrperson.py` (`kontext_tagebuch_neu` liefert `unterstuetzung` nur bei `art == "frei"`, `kontext_tagebuch_wahl` ohne Leitfragen, `ARTEN_NEU`/`hole_bezug` ohne `leitfrage`, Bezeichnung alter Einträge «Zur unterstützenden Frage»), `app/routen/aufnahmen.py` (Kontext der Seite «Frei sprechen» bekommt `unterstuetzung`), `app/routen/lehrperson.py` und `app/routen/ohne_speichern.py` (Routen `/tagebuch/neu/leitfrage/...` entfernen), `app/templates/lehrperson/tagebuch_eintrag.html`, `app/templates/verwaltung/eintraege/_eintrag.html`, Verwaltung: `leitfragen.html`, `formular_leitfrage.html`, `uebersicht.html`, Titel in `verwaltung_inhalte.py` → «Unterstützende Frage(n)»
- Create: `app/templates/lehrperson/_unterstuetzung.html`
- Test: `tests/test_tagebuch_routen.py`, `tests/test_ohne_speichern.py`, `tests/test_verwaltung_inhalte.py`, betroffene bestehende Tests anpassen (`tests/test_routen_inventar.py`)

**Interfaces:**
- Consumes: `inhalte.leitfragen(db) -> list[Row]` (unverändert).
- Produces: Vorlagenvariable `unterstuetzung: list[Row]`; `_unterstuetzung.html` rendert nichts bei leerer Liste, sonst `<details class="karte aufklapp unterstuetzung">` zugeklappt mit Summary «Unterstützende Frage» bzw. «Unterstützende Fragen».

- [ ] Tests: «Frei schreiben» und «Frei sprechen» enthalten die Frage in einem `<details>` ohne `open`; ohne Leitfragen kein `<details class="... unterstuetzung">`; Tagebuch-Auswahl enthält keinen Link `/tagebuch/neu/leitfrage/`; GET `/lehrperson/tagebuch/neu/leitfrage/1` → 404; Verwaltung zeigt «Unterstützende Fragen».
- [ ] Umsetzung, Tests grün, Commit `feat: Leitfragen werden zur aufklappbaren unterstützenden Frage`.

### Task 4: Blocksatz

**Files:**
- Modify: `app/static/css/style.css` (Regel für `.seite-lehrperson .formatiert p, li` o. ä. — Selektor nach dem tatsächlichen Body-/Rahmen-Klassennamen der Lehrpersonen-Ansicht; nicht in der Verwaltung), Abschnitt **nicht** ans Dateiende hängen, sondern bei `.formatiert`
- Test: `tests/test_muster_b.py` oder neu `tests/test_blocksatz.py` (Stylesheet enthält `text-align: justify` und `hyphens: auto` für den Selektor)

- [ ] Test, Umsetzung, Commit `feat: Blocksatz mit Silbentrennung für Fliesstexte`.

### Task 5: Doku und Nachweis

- [ ] `docs/anforderungen.md`: Runde um Zusatzinfo ergänzen, Tagebuch «unterstützende Frage aufklappbar» statt «zu Leitfragen schreiben», Gestaltung: Blocksatz. Commit `docs: ...`.
- [ ] `make lint test`, `make e2e` falls Leitfragen-Pfade darin vorkommen anpassen.
- [ ] Handy-Screenshots (CDP 390 px) mit Platzhaltern: Runde vor/nach Speichern, Startseite, Tagebuch mit aufgeklappter Frage.
- [ ] Review (Subagent + `merge-reviewer`), PR, Merge, Deploy, Nachweis auf fly.io.
