-- Zusatzinfos werden eigene Bausteine einer Runde. Fragen und Zusatzinfos teilen sich die
-- Reihenfolge der Runde und lassen sich frei gegeneinander verschieben.
CREATE TABLE zusatzinfos (
    id INTEGER PRIMARY KEY,
    runde_id INTEGER NOT NULL REFERENCES runden (id) ON DELETE CASCADE,
    inhalt TEXT NOT NULL,
    reihenfolge INTEGER NOT NULL DEFAULT 0
) STRICT;

CREATE INDEX idx_zusatzinfos_runde ON zusatzinfos (runde_id);

-- Rang jeder Frage in ihrer Runde, bevor sich die Reihenfolge ändert.
CREATE TEMP TABLE rang_007 AS
SELECT id, ROW_NUMBER() OVER (PARTITION BY runde_id ORDER BY reihenfolge, id) AS rang
FROM fragen;

-- Die Zusatzinfo einer Frage steht direkt nach ihr: Frage 2 x Rang, Info 2 x Rang + 1.
INSERT INTO zusatzinfos (runde_id, inhalt, reihenfolge)
SELECT f.runde_id, f.zusatzinfo, 2 * r.rang + 1
FROM fragen f JOIN rang_007 r ON r.id = f.id
WHERE f.zusatzinfo IS NOT NULL AND trim(f.zusatzinfo) <> ''
ORDER BY f.runde_id, r.rang;

UPDATE fragen SET reihenfolge = 2 * (SELECT r.rang FROM rang_007 r WHERE r.id = fragen.id);

-- Eine Info, die noch bei einer Runde ohne Frage wartet (nach Migration 006), wird ihr Baustein.
INSERT INTO zusatzinfos (runde_id, inhalt, reihenfolge)
SELECT r.id, r.zusatzinfo, 1 FROM runden r
WHERE r.zusatzinfo IS NOT NULL AND trim(r.zusatzinfo) <> ''
AND NOT EXISTS (SELECT 1 FROM fragen f WHERE f.runde_id = r.id);

DROP TABLE rang_007;

ALTER TABLE fragen DROP COLUMN zusatzinfo;
ALTER TABLE runden DROP COLUMN zusatzinfo;
