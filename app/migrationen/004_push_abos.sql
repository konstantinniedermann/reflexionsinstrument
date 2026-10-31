-- Benachrichtigungen (#37): ein Abo pro Gerät, gehört dem zuletzt angemeldeten Konto.
-- Gelöscht mit dem Konto (Kaskade), beim Ausschalten oder wenn der Push-Dienst es ablehnt.
CREATE TABLE push_abos (
    id INTEGER PRIMARY KEY,
    konto_id INTEGER NOT NULL REFERENCES konten (id) ON DELETE CASCADE,
    endpunkt TEXT NOT NULL UNIQUE,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    erstellt TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
) STRICT;

CREATE INDEX idx_push_abos_konto ON push_abos (konto_id);
