ALTER TABLE metrics
ADD COLUMN has_artifact TINYINT(1) NOT NULL DEFAULT 0
AFTER max_score;
CREATE TRIGGER update_has_artifact
AFTER
INSERT ON artifacts FOR EACH ROW BEGIN
UPDATE metrics
SET has_artifact = true
WHERE id = NEW.metric_id;
END;