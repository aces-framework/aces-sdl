ALTER TABLE deployment_elements
ADD COLUMN error_message TEXT
AFTER parent_node_id;