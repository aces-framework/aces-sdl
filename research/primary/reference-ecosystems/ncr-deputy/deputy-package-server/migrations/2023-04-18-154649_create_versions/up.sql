CREATE TABLE versions (
    id BINARY(16) PRIMARY KEY,
    package_id BINARY(16) NOT NULL,
    version TINYTEXT NOT NULL,
    license TEXT NOT NULL,
    readme_path MEDIUMTEXT NOT NULL,
    readme_html LONGTEXT NOT NULL,
    checksum TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    CONSTRAINT FK_PackageVersion FOREIGN KEY (package_id)
    REFERENCES packages(id)
);

INSERT INTO versions (id, package_id, version, license, readme_path, readme_html, checksum)
SELECT UNHEX(REPLACE(UUID(), '-', '')), id, version, license, readme_path, readme_html, checksum FROM packages GROUP BY(name);

ALTER TABLE packages DROP COLUMN version;
ALTER TABLE packages DROP COLUMN license;
ALTER TABLE packages DROP COLUMN readme_path;
ALTER TABLE packages DROP COLUMN readme_html;
ALTER TABLE packages DROP COLUMN checksum;
