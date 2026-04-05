CREATE TABLE training_objectives (
    id BINARY(16) NOT NULL,
    order_id BINARY(16) NOT NULL,
    objective TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE TABLE threats (
    id BINARY(16) NOT NULL,
    training_objective_id BINARY(16) NOT NULL,
    threat TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (training_objective_id) REFERENCES training_objectives(id) ON DELETE CASCADE
);