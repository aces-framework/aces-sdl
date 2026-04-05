ALTER TABLE event_info_data
MODIFY checksum CHAR(64);
ALTER TABLE events
MODIFY event_info_data_checksum CHAR(64);