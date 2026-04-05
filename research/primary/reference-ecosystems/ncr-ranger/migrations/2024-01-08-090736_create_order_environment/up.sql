CREATE TABLE environments (
    id BINARY(16) NOT NULL,
    order_id BINARY(16) NOT NULL,
    name TINYTEXT NOT NULL,
    category TINYTEXT NOT NULL,
    size INT NOT NULL,
    additional_information LONGTEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE TABLE environment_weakness (
    id BINARY(16) NOT NULL,
    environment_id BINARY(16) NOT NULL,
    weakness TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);
CREATE TABLE environment_strength (
    id BINARY(16) NOT NULL,
    environment_id BINARY(16) NOT NULL,
    strength TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (environment_id) REFERENCES environments(id) ON DELETE CASCADE
);