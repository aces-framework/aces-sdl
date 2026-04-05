CREATE TABLE structures (
    id BINARY(16) NOT NULL,
    order_id BINARY(16) NOT NULL,
    parent_id BINARY(16),
    name TINYTEXT NOT NULL,
    description TEXT,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES structures(id) ON DELETE CASCADE
);
CREATE TABLE skills (
    id BINARY(16) NOT NULL,
    structure_id BINARY(16) NOT NULL,
    skill TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (structure_id) REFERENCES structures(id) ON DELETE CASCADE
);
CREATE TABLE structure_training_objectives (
    id BINARY(16) NOT NULL,
    structure_id BINARY(16) NOT NULL,
    training_objective_id BINARY(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (structure_id) REFERENCES structures(id) ON DELETE CASCADE,
    FOREIGN KEY (training_objective_id) REFERENCES training_objectives(id) ON DELETE CASCADE
);
CREATE TABLE structure_weaknesses (
    id BINARY(16) NOT NULL,
    structure_id BINARY(16) NOT NULL,
    weakness TINYTEXT NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (structure_id) REFERENCES structures(id) ON DELETE CASCADE
);