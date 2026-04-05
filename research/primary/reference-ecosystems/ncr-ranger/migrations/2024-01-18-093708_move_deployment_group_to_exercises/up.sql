UPDATE deployments
SET deployment_group = ''
WHERE deployment_group IS NULL;
ALTER TABLE deployments
MODIFY COLUMN deployment_group TINYTEXT NOT NULL DEFAULT '';
ALTER TABLE exercises
ADD COLUMN deployment_group TINYTEXT NOT NULL DEFAULT ''
AFTER group_name;
UPDATE exercises
SET deployment_group = COALESCE(
        (
            SELECT deployment_group
            FROM deployments
            WHERE deployments.exercise_id = exercises.id
            LIMIT 1
        ), ''
    );