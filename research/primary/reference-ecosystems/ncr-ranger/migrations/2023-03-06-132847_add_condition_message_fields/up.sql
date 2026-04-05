ALTER TABLE condition_messages
ADD exercise_id BINARY(16) NOT NULL
AFTER id;
ALTER TABLE condition_messages
ADD virtual_machine_id BINARY(16) NOT NULL
AFTER deployment_id;
ALTER TABLE condition_messages
ADD condition_name TINYTEXT NOT NULL
AFTER virtual_machine_id;