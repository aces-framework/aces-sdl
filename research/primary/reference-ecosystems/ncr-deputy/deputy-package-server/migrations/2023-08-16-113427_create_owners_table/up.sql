CREATE TABLE owners (
    id BINARY(16) PRIMARY KEY,
    email TINYTEXT NOT NULL,
    package_id BINARY(16) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01',
    CONSTRAINT FK_Package_Owners FOREIGN KEY (package_id) REFERENCES packages(id),
    CONSTRAINT unique_owner_email_package_deleted UNIQUE (email, package_id, deleted_at)
);