ALTER TABLE packages ADD COLUMN version TINYTEXT AFTER id;
ALTER TABLE packages ADD COLUMN license TEXT AFTER version;
ALTER TABLE packages ADD COLUMN readme_path MEDIUMTEXT AFTER license;
ALTER TABLE packages ADD COLUMN readme_html LONGTEXT AFTER readme_path;
ALTER TABLE packages ADD COLUMN checksum TEXT AFTER readme_html;

UPDATE packages, versions
SET
    packages.version = versions.version,
    packages.license = versions.license,
    packages.readme_path = versions.readme_path,
    packages.readme_html = versions.readme_html,
    packages.checksum = versions.checksum
WHERE packages.id = versions.package_id;


ALTER TABLE packages MODIfY COLUMN version TINYTEXT NOT NULL;
ALTER TABLE packages MODIfY COLUMN license TEXT NOT NULL;
ALTER TABLE packages MODIfY COLUMN readme_path MEDIUMTEXT NOT NULL;
ALTER TABLE packages MODIfY COLUMN readme_html LONGTEXT NOT NULL;
ALTER TABLE packages MODIfY COLUMN checksum TEXT NOT NULL;

DROP table versions;
