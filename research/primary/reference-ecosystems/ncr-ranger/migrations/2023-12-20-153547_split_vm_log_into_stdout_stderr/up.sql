ALTER TABLE deployment_elements
ADD COLUMN executor_stdout MEDIUMTEXT NULL
AFTER status,
    ADD COLUMN executor_stderr MEDIUMTEXT NULL
AFTER executor_stdout;
UPDATE deployment_elements
SET executor_stdout = executor_log;
ALTER TABLE deployment_elements DROP COLUMN executor_log;