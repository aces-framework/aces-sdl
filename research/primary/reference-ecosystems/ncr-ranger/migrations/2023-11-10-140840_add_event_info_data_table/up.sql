CREATE TABLE event_info_data (
    checksum CHAR(32) NOT NULL,
    name TINYTEXT NOT NULL,
    file_name TINYTEXT NOT NULL,
    file_size BIGINT UNSIGNED NOT NULL,
    content MEDIUMBLOB NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (checksum)
);