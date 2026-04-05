ALTER TABLE packages ADD COLUMN readme_path TEXT AFTER license;
UPDATE packages SET readme_path="README.md" WHERE readme_path IS NULL;
ALTER TABLE packages MODIfY COLUMN readme_path TEXT NOT NULL;