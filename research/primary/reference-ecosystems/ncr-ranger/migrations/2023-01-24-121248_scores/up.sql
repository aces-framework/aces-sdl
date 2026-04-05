CREATE TABLE scores (
    id BINARY(16) NOT NULL,
    exercise_id BINARY(16) NOT NULL,
    deployment_id BINARY(16) NOT NULL,
    tlo_name TINYTEXT NOT NULL,
    metric_name TINYTEXT NOT NULL,
    value DECIMAL(18, 17) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (exercise_id) REFERENCES exercises(id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
);