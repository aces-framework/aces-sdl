ALTER TABLE packages ADD COLUMN readme MEDIUMTEXT AFTER license;
UPDATE packages SET readme = "No readme provided" WHERE readme IS NULL;
ALTER TABLE packages MODIfY COLUMN readme MEDIUMTEXT NOT NULL;