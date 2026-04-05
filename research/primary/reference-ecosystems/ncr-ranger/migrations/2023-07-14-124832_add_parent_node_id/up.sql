ALTER TABLE deployment_elements
    ADD parent_node_id BINARY(16) DEFAULT NULL AFTER event_id;