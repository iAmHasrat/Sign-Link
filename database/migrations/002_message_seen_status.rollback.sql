USE sign_link;

SET @has_seen_at := (
  SELECT COUNT(*)
  FROM INFORMATION_SCHEMA.COLUMNS
  WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'messages'
    AND COLUMN_NAME = 'seen_at'
);

SET @drop_seen_at := IF(
  @has_seen_at = 1,
  'ALTER TABLE messages DROP COLUMN seen_at',
  'SELECT ''messages.seen_at does not exist'' AS message'
);

PREPARE stmt FROM @drop_seen_at;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
