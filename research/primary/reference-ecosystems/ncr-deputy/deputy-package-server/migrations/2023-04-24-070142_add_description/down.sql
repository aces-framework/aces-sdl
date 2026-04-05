ALTER TABLE versions DROP COLUMN description;

ALTER TABLE versions ADD COLUMN readme_path TEXT AFTER license;
UPDATE versions SET readme_path="README.md" WHERE readme_path IS NULL;
ALTER TABLE versions MODIFY COLUMN readme_path TEXT NOT NULL;