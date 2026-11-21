-- Zusatzinfo pro Frage: erscheint nach dieser Frage, sobald die Fragen davor beantwortet sind.
ALTER TABLE fragen ADD COLUMN zusatzinfo TEXT;

-- Die bisherige Zusatzinfo der Runde stand nach Frage 1 und wandert genau dorthin.
UPDATE fragen SET zusatzinfo = (SELECT r.zusatzinfo FROM runden r WHERE r.id = fragen.runde_id)
WHERE id IN (
    SELECT (SELECT f.id FROM fragen f WHERE f.runde_id = r.id ORDER BY f.reihenfolge, f.id LIMIT 1)
    FROM runden r WHERE r.zusatzinfo IS NOT NULL
);

-- Runden ohne Frage behalten ihre Info; sie wandert mit der ersten neuen Frage (app/inhalte.py).
UPDATE runden SET zusatzinfo = NULL
WHERE EXISTS (SELECT 1 FROM fragen f WHERE f.runde_id = runden.id);
