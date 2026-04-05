CREATE TABLE condition_messages (
    id BINARY(16) NOT NULL,
    deployment_id BINARY(16) NOT NULL,
    condition_id BINARY(16) NOT NULL,
    value DECIMAL(18, 17) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (deployment_id) REFERENCES deployments(id)
)