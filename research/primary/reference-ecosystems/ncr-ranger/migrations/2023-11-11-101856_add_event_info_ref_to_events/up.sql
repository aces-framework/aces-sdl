ALTER TABLE events
ADD COLUMN event_info_data_checksum CHAR(32) NULL
AFTER triggered_at;