# Zusatzinfos frei anordnen – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Zusatzinfos werden eigene Bausteine einer Runde, frei zwischen den Fragen angeordnet; die Lehrpersonen-Seite sperrt weiter vor jeder Zusatzinfo, bis die Fragen davor beantwortet sind.

**Architecture:** Neue Tabelle `zusatzinfos` mit gemeinsamer `reihenfolge` neben `fragen`. `inhalte.ablauf()` liefert die gemischte Liste; die Abschnittsbildung in `seiten_lehrperson.py` liest Bausteine statt Fragen. Eingabemaske zeigt den Ablauf als Karten mit Verschieben über beide Arten.

**Tech Stack:** FastAPI, Jinja2, SQLite (STRICT, Migrationen per `PRAGMA user_version`), pytest, Node-E2E mit Headless-Chrome.

**Spec:** `docs/superpowers/specs/2026-11-22-zusatzinfos-frei-anordnen-design.md`

## Global Constraints

- Keine neue Dependency.
- Texte für Lehrpersonen und Auftraggeberin: Hochdeutsch, ohne Fachjargon, keine Emojis.
- Für bestehende Inhalte bleibt die Lehrpersonen-Seite identisch (gleiche Abschnitte, gleiche Hinweissätze).
- Anker auf der Lehrpersonen-Seite: `zusatzinfo-<Id der Zusatzinfo>`; Karten in der Maske: `frage-<Id>`, `zusatzinfo-<Id>`.
- Vermerk-Texte in der Maske: «Erscheint sofort beim Öffnen der Runde» / «Erscheint, sobald die Fragen davor beantwortet sind».

## Review Focus

- Zwei Zusatzinfos direkt hintereinander nach Fragen: erscheinen zusammen, Sprung zur ersten der beiden.
- Zusatzinfo vor der ersten Frage ohne Fallbeispiel (Woche 4): sofort sichtbar, kein Hinweissatz.
- Runde nur mit Zusatzinfos, ohne Fragen: Lehrperson sieht die Infos, kein Formular-Absturz.
- Verschieben einer Info über eine schon beantwortete Frage hinweg: keine Antwort verschwindet (Regel «bleibt offen»).
- Gast/Vorschau mit Info am Schluss: Knopf unten öffnet die Info statt zur Startseite zu führen.

---

### Task 1: Migration 007 und Datenschicht

**Files:**
- Create: `app/migrationen/007_zusatzinfos_als_baustein.sql`
- Modify: `app/inhalte.py` (Runden-SQL ohne `zusatzinfo`, Fragen ohne `zusatzinfo`, neu: Zusatzinfos, Ablauf, Verschieben im Ablauf; `wartende_zusatzinfo` entfällt)
- Modify: `app/kommandos.py`, `tests/platzhalter/inhalte.json` (Feld `ablauf`)
- Test: `tests/test_migration_007.py`, `tests/test_migration_006.py` (bis 006 begrenzen), `tests/test_inhalte.py`

**Interfaces – Produces:**
- `ablauf(db, runde_id) -> list[dict]`: jeweils `{"art": "frage", "frage": Row}` oder `{"art": "zusatzinfo", "zusatzinfo": Row}`, sortiert nach `(reihenfolge, art, id)`.
- `zusatzinfo(db, info_id) -> Row | None`, `lege_zusatzinfo_an(db, runde_id, inhalt) -> int`, `aendere_zusatzinfo(db, info_id, inhalt) -> None`, `loesche_zusatzinfo(db, info_id) -> None` (Fehlerfeld `inhalt`, Pflicht: «Bitte einen Text eingeben.»).
- `verschiebe_im_ablauf(db, art: "frage"|"zusatzinfo", eintrag_id, richtung) -> None`.
- `lege_frage_an`/`aendere_frage` ohne Parameter `zusatzinfo`.

- [ ] Test `test_migration_007`: Runde A (Fragen 1–3, Info nach 1 und 3), Runde B (nur wartende Info), Runde C (Frage ohne Info). Nach `migriere` ist `[(art, text)]` von `ablauf` = A: F1, I1, F2, F3, I3; B: I; C: F. Spalten `zusatzinfo` fehlen in `fragen` und `runden`.
- [ ] Tests in `test_inhalte`: neue Frage und neue Info kommen ans Ende des gemischten Ablaufs; `verschiebe_im_ablauf` tauscht Info mit Frage; Löschen einer Frage nummeriert 1..n neu; leere Info → `InhaltFehler("inhalt", …)`.
- [ ] Migration und Funktionen umsetzen, `test_migration_006` auf `00[1-6]` begrenzen, Platzhalter auf `ablauf` umstellen (Runde 3: zwei Fragen, Info, Frage).
- [ ] `make test` (Teilmenge), Commit `feat: Zusatzinfo als eigener Baustein im Ablauf der Runde`.

### Task 2: Lehrpersonen-, Gast- und Vorschau-Seite

**Files:**
- Modify: `app/seiten_lehrperson.py` (`_zeilen` → Bausteine, `abschnitte`, `neu_geoeffnete_info`, `kontext_runde`), `app/templates/lehrperson/runde.html`, `app/routen/aufnahmen.py` (Anker unverändert über `neue_info`)
- Test: `tests/test_zusatzinfo.py`, `tests/testdaten.py` (`zusatzinfos` als `{stelle_nach_frage: text}` erzeugt Bausteine; neu `ablauf=`-Variante)

**Interfaces – Consumes:** `ablauf()` aus Task 1. **Produces:** `abschnitte(bausteine) -> list[list[dict]]` (neuer Abschnitt bei Zusatzinfo, wenn der laufende eine Frage hat); `neu_geoeffnete_info(...) -> int | None` = Id der ersten Zusatzinfo des neu geöffneten Abschnitts; Kontext `bausteine` (offene), `hinweis_zusatzinfo` (None oder Satz).

- [ ] Tests: Info vor erster Frage sofort sichtbar; zwei Infos hintereinander gehen zusammen auf; «F, F, I, F»: I und dritte Frage erst nach beiden; Info am Schluss; Runde nur mit Infos; Sprung-Anker ist Info-Id; bestehende Tests grün.
- [ ] Umsetzen; Template iteriert Bausteine, Hinweissatz nach dem letzten sichtbaren Baustein (`id="weiter-hinweis"`).
- [ ] `make test`, Commit `feat: Lehrpersonen-Seite liest den gemischten Ablauf`.

### Task 3: Eingabemaske

**Files:**
- Create: `app/templates/verwaltung/inhalte/formular_zusatzinfo.html`
- Modify: `app/routen/verwaltung_inhalte.py`, `app/templates/verwaltung/inhalte/runde.html`, `formular_frage.html`, CSS falls nötig
- Test: `tests/test_verwaltung_inhalte.py`, `tests/test_routen_inventar.py`, `tests/test_inhalte_zugriff.py`

**Routen (alle unter `/verwaltung/inhalte`, POST mit CSRF):** `GET /runden/{id}/zusatzinfos/neu`, `POST /runden/{id}/zusatzinfos`, `GET|POST /zusatzinfos/{id}`, `POST /zusatzinfos/{id}/verschieben`, `GET|POST /zusatzinfos/{id}/loeschen`. Fragen-Verschieben nutzt `verschiebe_im_ablauf`.

- [ ] Tests: Detailseite zeigt Ablauf gemischt mit Vermerken; Info anlegen/bearbeiten/löschen mit Redirect auf `#zusatzinfo-<id>`; leere Info → 400 mit Fehler; Frageformular ohne Zusatzinfo-Feld; Löschseite der Frage ohne Info-Hinweis; Inventar und Zugriffsschutz für neue Routen.
- [ ] Umsetzen.
- [ ] `make test && make lint`, Commit `feat: Zusatzinfos in der Eingabemaske frei anordnen`.

### Task 4: E2E, Doku, Nachweis

- [ ] `tests/e2e-pilot.mjs`: Zusatzinfo-Szenario auf neuen Ablauf (Maske: Info anlegen, verschieben; Lehrperson: «F, F, I, F»), Handy-Ansicht 390 px per CDP.
- [ ] `docs/anforderungen.md`, `README.md`, Ablöse-Vermerk im Spec vom 21.11.
- [ ] `make test`, `make lint`, `make e2e`; Commit `docs: …` / `test: …`.
- [ ] Review (superpowers + `merge-reviewer`), PR, Merge, Migration auf Kopie der Prod-DB prüfen, Deploy von `origin/main`, Anleitung in `intern/` neu bauen.
