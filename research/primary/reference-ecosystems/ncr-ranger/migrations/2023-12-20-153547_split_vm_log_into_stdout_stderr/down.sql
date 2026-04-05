ALTER TABLE deployment_elements
ADD COLUMN executor_log MEDIUMTEXT NULL
AFTER status;
UPDATE deployment_elements
SET executor_log = CONCAT_WS('\n\n', executor_stdout, executor_stderr);
ALTER TABLE deployment_elements DROP COLUMN executor_stdout,
    DROP COLUMN executor_stderr;