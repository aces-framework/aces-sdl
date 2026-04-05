-- Your SQL goes here
ALTER TABLE exercises
ADD group_name TINYTEXT
AFTER name;
ALTER TABLE deployments
ADD group_name TINYTEXT
AFTER name;