-- Grundschema der Pilot-Version. Fremdschluessel-Regeln lassen sich in SQLite
-- nicht nachtraeglich aendern, darum stehen sie hier von Anfang an.

CREATE TABLE konten (
    id INTEGER PRIMARY KEY,
    anzeigename TEXT NOT NULL,
    benutzername TEXT NOT NULL UNIQUE COLLATE NOCASE,
    passwort_hash TEXT NOT NULL,
    rolle TEXT NOT NULL CHECK (rolle IN ('lehrperson', 'auftraggeberin')),
    sitzungsversion INTEGER NOT NULL DEFAULT 1,
    erstellt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE TABLE einstellungen (
    schluessel TEXT PRIMARY KEY,
    wert TEXT NOT NULL
) STRICT;

CREATE TABLE texte (
    schluessel TEXT PRIMARY KEY,
    inhalt TEXT NOT NULL,
    geaendert TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE TABLE info_abschnitte (
    id INTEGER PRIMARY KEY,
    titel TEXT NOT NULL,
    inhalt TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE runden (
    id INTEGER PRIMARY KEY,
    titel TEXT NOT NULL,
    fallbeispiel TEXT,
    freischaltdatum TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE fragen (
    id INTEGER PRIMARY KEY,
    runde_id INTEGER NOT NULL REFERENCES runden (id) ON DELETE CASCADE,
    typ TEXT NOT NULL CHECK (typ IN ('freitext', 'skala')),
    text TEXT NOT NULL,
    skala_min_text TEXT,
    skala_max_text TEXT,
    reihenfolge INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE leitfragen (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE TABLE impulse (
    id INTEGER PRIMARY KEY,
    text TEXT NOT NULL,
    sichtbar_ab TEXT NOT NULL
) STRICT;

CREATE TABLE aufnahmen (
    id INTEGER PRIMARY KEY,
    konto_id INTEGER NOT NULL REFERENCES konten (id) ON DELETE CASCADE,
    dateiname TEXT NOT NULL UNIQUE,
    mime_typ TEXT NOT NULL,
    groesse_bytes INTEGER NOT NULL,
    erstellt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE TABLE antworten (
    id INTEGER PRIMARY KEY,
    frage_id INTEGER NOT NULL REFERENCES fragen (id) ON DELETE RESTRICT,
    konto_id INTEGER NOT NULL REFERENCES konten (id) ON DELETE CASCADE,
    text TEXT,
    skalawert INTEGER,
    aufnahme_id INTEGER REFERENCES aufnahmen (id) ON DELETE SET NULL,
    erstellt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    geaendert TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (frage_id, konto_id)
) STRICT;

CREATE TABLE tagebucheintraege (
    id INTEGER PRIMARY KEY,
    konto_id INTEGER NOT NULL REFERENCES konten (id) ON DELETE CASCADE,
    art TEXT NOT NULL CHECK (art IN ('frei', 'leitfragen', 'aufnahme', 'impuls')),
    text TEXT,
    impuls_id INTEGER REFERENCES impulse (id) ON DELETE SET NULL,
    impuls_text TEXT,
    leitfrage_id INTEGER REFERENCES leitfragen (id) ON DELETE SET NULL,
    leitfrage_text TEXT,
    aufnahme_id INTEGER REFERENCES aufnahmen (id) ON DELETE SET NULL,
    erstellt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    geaendert TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE INDEX idx_antworten_konto ON antworten (konto_id);
CREATE INDEX idx_tagebucheintraege_konto ON tagebucheintraege (konto_id);
CREATE INDEX idx_fragen_runde ON fragen (runde_id);
