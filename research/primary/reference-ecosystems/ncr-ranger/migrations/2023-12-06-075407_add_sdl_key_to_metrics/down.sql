UPDATE metrics
SET name = sdl_key
WHERE name IS NULL
    OR name = '';
ALTER TABLE metrics DROP COLUMN sdl_key;
ALTER TABLE metrics
MODIFY COLUMN name TEXT NOT NULL;