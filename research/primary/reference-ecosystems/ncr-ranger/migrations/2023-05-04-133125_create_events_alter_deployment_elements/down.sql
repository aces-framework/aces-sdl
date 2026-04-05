ALTER TABLE deployment_elements 
    DROP FOREIGN KEY deployment_elements_ibfk_2;

ALTER TABLE deployment_elements 
    DROP COLUMN event_id;

DROP TABLE events;