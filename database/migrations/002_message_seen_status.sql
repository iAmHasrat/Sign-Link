USE sign_link;

SET @has_seen_at := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'messages'
    AND COLUMN_NAME = 'seen_at'
);

SET @add_seen_at := IF(
  @has_seen_at = 0,
  'ALTER TABLE messages ADD COLUMN seen_at TIMESTAMP NULL AFTER message_text',
  'SELECT ''messages.seen_at already exists'' AS message'
);

PREPARE stmt FROM @add_seen_at;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
