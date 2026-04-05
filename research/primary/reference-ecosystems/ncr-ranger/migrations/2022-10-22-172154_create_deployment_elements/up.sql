CREATE TABLE deployment_elements (
  id BINARY(16) NOT NULL,
  deployment_id BINARY(16) NOT NULL,
  scenario_reference TINYTEXT NOT NULL,
  handler_reference TINYTEXT DEFAULT NULL,
  deployer_type TINYTEXT NOT NULL,
  status TINYTEXT NOT NULL,
  executor_log MEDIUMTEXT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted_at TIMESTAMP NULL DEFAULT NULL,
  PRIMARY KEY (id),
  FOREIGN KEY (deployment_id) REFERENCES deployments(id),
  CONSTRAINT unique_references UNIQUE (
    scenario_reference,
    handler_reference,
    deployment_id
  )
);