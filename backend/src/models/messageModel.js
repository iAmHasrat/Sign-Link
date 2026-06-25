import { pool } from '../config/db.js';

export async function createMessage(senderId, receiverId, messageText) {
  const [result] = await pool.execute(
    'INSERT INTO messages (sender_id, receiver_id, message_text) VALUES (?, ?, ?)',
    [senderId, receiverId, messageText]
  );
  const [rows] = await pool.execute(
    `SELECT m.*, s.username AS sender_username, r.username AS receiver_username
     FROM messages m
     JOIN users s ON s.user_id = m.sender_id
     JOIN users r ON r.user_id = m.receiver_id
     WHERE m.message_id = ?`,
    [result.insertId]
  );
  return rows[0];
}

export async function listConversation(userId, peerId) {
  const [rows] = await pool.execute(
    `SELECT *
     FROM messages
     WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?)
     ORDER BY created_at ASC
     LIMIT 200`,
    [userId, peerId, peerId, userId]
  );
  return rows;
}

export async function markConversationSeen(userId, peerId) {
  await pool.execute(
    `UPDATE messages
     SET seen_at = COALESCE(seen_at, CURRENT_TIMESTAMP)
     WHERE sender_id = ? AND receiver_id = ? AND seen_at IS NULL`,
    [peerId, userId]
  );

  const [rows] = await pool.execute(
    `SELECT message_id, sender_id, receiver_id, seen_at
     FROM messages
     WHERE sender_id = ? AND receiver_id = ? AND seen_at IS NOT NULL
     ORDER BY seen_at DESC
     LIMIT 200`,
    [peerId, userId]
  );
  return rows;
}
