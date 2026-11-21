# Mehrere Zusatzinfos pro Runde – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jede Frage einer Runde kann eine Zusatzinfo tragen, die nach ihr erscheint, sobald alle Fragen ihres Abschnitts beantwortet sind.

**Architecture:** Neue Spalte `fragen.zusatzinfo` (Migration 006 verschiebt `runden.zusatzinfo` zur ersten Frage). Eine reine Funktion teilt die Zeilen der Runde in Abschnitte und zählt die offenen. `kontext_runde` liefert nur die sichtbaren Zeilen und die Stelle des Hinweises, beide Speicher-Routen springen zur ersten neu geöffneten Info.

**Tech Stack:** FastAPI, Jinja2, SQLite, pytest, Ruff, Node-E2E (CDP).

**Spec:** `docs/superpowers/specs/2026-11-21-mehrere-zusatzinfos-design.md`

## Global Constraints

- Keine neue Dependency, kein JavaScript für die Logik.
- Texte für Lehrpersonen auf Hochdeutsch, «du»-Form, ohne Emojis. Hinweissätze wörtlich wie im Spec.
- Repo öffentlich: nur Platzhalter-Inhalte.
- Vor jedem Commit `make format`, dann `make lint`.

## Review Focus

1. Abschnitt mit zwei Fragen, nur eine beantwortet → nächste Info bleibt zu (Task 2).
2. Skala «Keine Angabe» als letzte Frage eines Abschnitts → bleibt zu (Task 2).
3. Antwort in Abschnitt 1 gelöscht, Abschnitt 2 hat Antworten → Abschnitte 1 und 2 bleiben offen (Task 2).
4. Speichern, während spätere Abschnitte verborgen sind → löscht keine verborgenen Antworten (fehlende Felder bleiben unverändert; Task 2).
5. Migration: Runde mit Zusatzinfo ohne Fragen → Info bleibt bei der Runde und wandert mit der ersten neuen Frage (Task 1).

---

### Task 1: Datenmodell, Migration, Fachfunktionen

**Files:** Create `app/migrationen/006_zusatzinfo_pro_frage.sql`, `tests/test_migration_006.py`. Modify `app/inhalte.py`, `app/kommandos.py`, `tests/platzhalter/inhalte.json`, `tests/testdaten.py`, `tests/test_migration_003.py`, `tests/test_db.py`.

**Interfaces – Produces:**
- `lege_frage_an(db, runde_id, typ, text, skala_min_text, skala_max_text, zusatzinfo: str = "") -> int`: speichert die abgeschickte Info und leert bei der ersten Frage eine wartende `runden.zusatzinfo` (das Formular zeigt sie vorbelegt).
- `aendere_frage(..., zusatzinfo: str = "") -> None`.
- `lege_runde_an`/`aendere_runde` ohne Parameter `zusatzinfo`; `runde()` liefert `zusatzinfo` weiter (wartende Info).
- `testdaten.lege_runde_an(..., zusatzinfos: dict[int, str] | None = None)`: Index der Frage (0-basiert) → Info.

- [ ] Test `test_migration_006`: DB bis 005 migrieren, Runde A mit Info und zwei Fragen (Reihenfolge 2, 1), Runde B mit Info ohne Fragen; nach 006 steht die Info bei der Frage mit Reihenfolge 1 und `runden.zusatzinfo` von A ist NULL, B behält sie. Danach legt `lege_frage_an` für B die Info bei der neuen Frage ab.
- [ ] Migration schreiben, Fachfunktionen anpassen, Platzhalter (Runde 1: Info nach Frage 1 und Frage 3; übrige Runden: nach Frage 1), bestehende Tests anpassen.
- [ ] `uv run pytest` grün, Commit `feat: Zusatzinfo hängt an der Frage (Migration 006)`.

### Task 2: Abschnittsregel und Lehrpersonen-Ansicht

**Files:** Modify `app/seiten_lehrperson.py`, `app/templates/lehrperson/runde.html`, `app/routen/lehrperson.py`, `app/routen/aufnahmen.py`. Test `tests/test_zusatzinfo.py` (neu geschrieben).

**Interfaces – Produces:**
- `offene_abschnitte(zeilen: list[dict], antworten) -> int`: Abschnitte = Fragen bis einschliesslich der ersten mit Info, dann bis zur nächsten usw. (eine Info nach der letzten Frage ergibt einen leeren Schlussabschnitt). Abschnitt k+1 ist offen, wenn k offen ist und alle Fragen von k beantwortet sind oder irgendeine Frage ab Abschnitt k+1 beantwortet ist.
- `neu_geoeffnete_info(db, konto_id, runde_id, vorher: int) -> int | None`: Frage-Id der ersten Info, die seit `vorher` offenen Abschnitten aufging.
- `offene_abschnitte_gespeichert(db, konto_id, runde_id) -> int`.
- Kontext `kontext_runde`: `zeilen` (nur sichtbare), `gesperrt_nach` (Frage-Id, deren Info noch zu ist, oder None), `hinweis_zusatzinfo` (Satz laut Spec).
- Anker der Info: `zusatzinfo-<frage_id>`.

- [ ] Tests: ohne Antwort nur Abschnitt 1 + Satz «… die Frage oben …»; Abschnitt mit zwei Fragen halb → zu, Satz «… alle Fragen oben …»; ganz → offen; Skala «Keine Angabe» → zu; Aufnahme zählt; spätere Antwort hält offen; Sprung `#zusatzinfo-<id>` nur beim Aufgehen; Info nach letzter Frage, Satz ohne «mit weiteren Fragen»; Runde ohne Info zeigt alles; Gast und Vorschau mit abgeschickten Werten; Aufnahme-Route springt zur Info.
- [ ] Umsetzen, `uv run pytest` grün, Commit `feat: mehrere Zusatzinfos erscheinen Abschnitt für Abschnitt`.

### Task 3: Eingabemaske

**Files:** Modify `app/routen/verwaltung_inhalte.py`, `app/templates/verwaltung/inhalte/formular_frage.html`, `formular_runde.html`, `runde.html`. Test `tests/test_verwaltung_inhalte.py`.

- [ ] Tests: Frage mit Info anlegen und bearbeiten (Leerzeichen → NULL); Rundenformular ohne Feld `zusatzinfo`; Detailseite zeigt Info unter der Frage-Karte mit Vermerk; wartende Info mit Vermerk «erscheint, sobald die Runde eine Frage hat»; Löschseite einer Frage mit Info sagt «Die Zusatzinfo nach dieser Frage wird mitgelöscht.»
- [ ] Hilfetext im Frageformular: «Erscheint nach dieser Frage, sobald die Lehrperson alle Fragen davor (seit der letzten Zusatzinfo) beantwortet hat.»
- [ ] Umsetzen, Tests grün, Commit `feat: Zusatzinfo in der Eingabemaske bei der Frage`.

### Task 4: E2E, Doku, Nachweis

- [ ] `tests/e2e-pilot.mjs` an Anker `zusatzinfo-<id>` und zwei Infos in Runde 1 anpassen; `make e2e` grün, Screenshots 390 px der drei Stufen prüfen.
- [ ] `docs/anforderungen.md`, README, altes Spec (Verweis auf neues) nachführen. Commit `docs: mehrere Zusatzinfos`.
