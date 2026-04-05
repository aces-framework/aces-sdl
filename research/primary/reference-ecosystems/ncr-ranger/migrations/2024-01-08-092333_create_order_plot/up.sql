CREATE TABLE plots (
    id BINARY(16) NOT NULL,
    order_id BINARY(16) NOT NULL,
    name TINYTEXT NOT NULL,
    description TEXT NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);
CREATE TABLE plot_points (
    id BINARY(16) NOT NULL,
    plot_id BINARY(16) NOT NULL,
    objective_id BINARY(16) NOT NULL,
    name TINYTEXT NOT NULL,
    description TEXT NOT NULL,
    trigger_time TIMESTAMP NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (plot_id) REFERENCES plots(id) ON DELETE CASCADE
);
CREATE TABLE plot_point_structures (
    id BINARY(16) NOT NULL,
    plot_point_id BINARY(16) NOT NULL,
    structure_id BINARY(16) NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (plot_point_id) REFERENCES plot_points(id) ON DELETE CASCADE,
    FOREIGN KEY (structure_id) REFERENCES structures(id) ON DELETE CASCADE
);