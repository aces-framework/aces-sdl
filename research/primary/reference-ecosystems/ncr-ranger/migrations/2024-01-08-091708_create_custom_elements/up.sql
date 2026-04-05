CREATE TABLE custom_elements (
    id BINARY(16) NOT NULL,
    order_id BINARY(16) NOT NULL,
    name TINYTEXT NOT NULL,
    description TEXT NOT NULL,
    environment_id BINARY(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);