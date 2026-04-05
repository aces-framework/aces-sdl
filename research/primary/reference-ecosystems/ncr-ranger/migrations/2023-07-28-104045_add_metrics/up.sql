CREATE TABLE metrics (
    id BINARY(16) NOT NULL,
    exercise_id BINARY(16) NOT NULL,
    deployment_id BINARY(16) NOT NULL,
    user_id TEXT NOT NULL,
    entity_selector TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    role TINYTEXT NOT NULL,
    text_submission TEXT,
    score INT UNSIGNED,
    max_score INT UNSIGNED NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01',
    PRIMARY KEY (id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(id),
    UNIQUE (name, deployment_id, entity_selector, deleted_at)
);