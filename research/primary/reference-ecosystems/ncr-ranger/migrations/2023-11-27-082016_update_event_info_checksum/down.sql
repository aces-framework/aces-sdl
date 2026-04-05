UPDATE event_info_data
SET checksum = MD5(content);
ALTER TABLE event_info_data
MODIFY checksum CHAR(32);
ALTER TABLE events
MODIFY event_info_data_checksum CHAR(32);