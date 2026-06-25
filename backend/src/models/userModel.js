import { pool } from '../config/db.js';

const publicFields = 'user_id, full_name, username, email, role, preferred_language, profile_picture, created_at';

export async function findUserByEmail(email) {
  const [rows] = await pool.execute('SELECT * FROM users WHERE email = ?', [email]);
  return rows[0];
}

export async function findUserByUsername(username) {
  const [rows] = await pool.execute('SELECT * FROM users WHERE username = ?', [username]);
  return rows[0];
}

export async function findUserById(userId) {
  const [rows] = await pool.execute(`SELECT ${publicFields} FROM users WHERE user_id = ?`, [userId]);
  return rows[0];
}

export async function createUser({ fullName, username, email, passwordHash, role, preferredLanguage }) {
  const [result] = await pool.execute(
    `INSERT INTO users (full_name, username, email, password_hash, role, preferred_language)
     VALUES (?, ?, ?, ?, ?, ?)`,
    [fullName, username, email, passwordHash, role, preferredLanguage]
  );
  return findUserById(result.insertId);
}

export async function searchUsers(query, currentUserId) {
  const term = `%${query || ''}%`;
  const [rows] = await pool.execute(
    `SELECT ${publicFields}
     FROM users
     WHERE user_id != ? AND (full_name LIKE ? OR username LIKE ? OR email LIKE ?)
     ORDER BY full_name ASC
     LIMIT 30`,
    [currentUserId, term, term, term]
  );
  return rows;
}

export async function updateUser(userId, updates) {
  const fields = [];
  const values = [];
  const map = {
    fullName: 'full_name',
    role: 'role',
    preferredLanguage: 'preferred_language',
    profilePicture: 'profile_picture'
  };

  for (const [key, column] of Object.entries(map)) {
    if (updates[key] !== undefined) {
      fields.push(`${column} = ?`);
      values.push(updates[key]);
    }
  }

  if (fields.length) {
    await pool.execute(`UPDATE users SET ${fields.join(', ')} WHERE user_id = ?`, [...values, userId]);
  }

  return findUserById(userId);
}
