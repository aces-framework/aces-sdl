ALTER TABLE versions ADD COLUMN description LONGTEXT AFTER version;
UPDATE versions
INNER JOIN packages ON versions.package_id = packages.id
SET
    versions.description = packages.name
WHERE versions.description IS NULL;
ALTER TABLE versions MODIFY COLUMN description LONGTEXT NOT NULL;
ALTER TABLE versions DROP COLUMN readme_path;