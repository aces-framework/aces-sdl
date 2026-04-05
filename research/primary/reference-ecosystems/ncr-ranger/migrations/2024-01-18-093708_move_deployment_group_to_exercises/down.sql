ALTER TABLE exercises
DROP COLUMN deployment_group;
ALTER TABLE deployments
MODIFY COLUMN deployment_group TINYTEXT;
UPDATE deployments
SET deployment_group = NULL
WHERE deployment_group = '';