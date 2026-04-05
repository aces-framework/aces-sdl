ALTER TABLE exercises
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
ALTER TABLE deployments
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
ALTER TABLE deployment_elements
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
ALTER TABLE accounts
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
ALTER TABLE condition_messages
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
ALTER TABLE scores
MODIFY deleted_at TIMESTAMP NULL DEFAULT NULL;
UPDATE exercises
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
UPDATE deployments
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
UPDATE deployment_elements
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
UPDATE accounts
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
UPDATE condition_messages
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
UPDATE scores
SET deleted_at = NULL
WHERE deleted_at = '1970-01-01 00:00:01';
ALTER TABLE exercises DROP INDEX name;
ALTER TABLE exercises
ADD UNIQUE INDEX name (name);
ALTER TABLE deployments DROP INDEX name;
ALTER TABLE deployments
ADD UNIQUE INDEX name (name, exercise_id);
ALTER TABLE accounts
ADD UNIQUE INDEX id (id);