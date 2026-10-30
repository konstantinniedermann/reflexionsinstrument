-- Datenmodell fuer #16 bis #19. Nur Ergaenzungen: eine Spalte und Indizes.
-- Keine Fremdschluessel-Regel aendert sich, darum kein Neuaufbau einer Tabelle.

-- Laenge einer Aufnahme in ganzen Sekunden, vom Browser gemessen (#17).
-- Nur zur Anzeige ("Aufnahme, 2 Min."); die Obergrenze prueft der Server ueber die Groesse.
ALTER TABLE aufnahmen ADD COLUMN dauer_sekunden INTEGER
    CHECK (dauer_sekunden IS NULL OR dauer_sekunden >= 0);

-- Eine Aufnahme gehoert hoechstens zu einer Antwort bzw. einem Tagebucheintrag.
CREATE UNIQUE INDEX idx_antworten_aufnahme
    ON antworten (aufnahme_id) WHERE aufnahme_id IS NOT NULL;
CREATE UNIQUE INDEX idx_tagebucheintraege_aufnahme
    ON tagebucheintraege (aufnahme_id) WHERE aufnahme_id IS NOT NULL;

-- Zugriffspruefung und Loeschen pro Konto (#17, #18).
CREATE INDEX idx_aufnahmen_konto ON aufnahmen (konto_id);
