import { pool } from '../config/db.js';

export async function createCall(callerId, receiverId, status = 'started') {
  const [result] = await pool.execute(
    'INSERT INTO calls (caller_id, receiver_id, call_status) VALUES (?, ?, ?)',
    [callerId, receiverId, status]
  );
  await pool.execute('INSERT INTO call_history (call_id, caller_id, receiver_id) VALUES (?, ?, ?)', [
    result.insertId,
    callerId,
    receiverId
  ]);
  return result.insertId;
}

export async function finishCall(callId, status = 'completed') {
  await pool.execute(
    `UPDATE calls
     SET end_time = CURRENT_TIMESTAMP,
         duration_seconds = TIMESTAMPDIFF(SECOND, start_time, CURRENT_TIMESTAMP),
         call_status = ?
     WHERE call_id = ?`,
    [status, callId]
  );
}

export async function listCallHistory(userId) {
  const [rows] = await pool.execute(
    `SELECT c.*, caller.full_name AS caller_name, receiver.full_name AS receiver_name
     FROM calls c
     JOIN users caller ON caller.user_id = c.caller_id
     JOIN users receiver ON receiver.user_id = c.receiver_id
     WHERE c.caller_id = ? OR c.receiver_id = ?
     ORDER BY c.start_time DESC
     LIMIT 100`,
    [userId, userId]
  );
  return rows;
}
