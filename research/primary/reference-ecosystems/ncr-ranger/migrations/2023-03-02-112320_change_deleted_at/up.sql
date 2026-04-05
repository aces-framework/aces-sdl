UPDATE exercises
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
UPDATE deployments
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
UPDATE deployment_elements
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
UPDATE accounts
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
UPDATE condition_messages
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
UPDATE scores
SET deleted_at = '1970-01-01 00:00:01'
WHERE deleted_at IS NULL;
ALTER TABLE exercises
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE deployments
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE deployment_elements
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE accounts
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE condition_messages
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE scores
MODIFY deleted_at TIMESTAMP NOT NULL DEFAULT '1970-01-01 00:00:01';
ALTER TABLE exercises DROP INDEX name;
ALTER TABLE exercises
ADD UNIQUE INDEX name (name, deleted_at);
ALTER TABLE deployments DROP INDEX name;
ALTER TABLE deployments
ADD UNIQUE INDEX name (name, exercise_id, deleted_at);
ALTER TABLE accounts DROP INDEX id;