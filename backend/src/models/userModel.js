// userModel.js — JSON-backed user store (no MySQL needed)

import bcrypt from 'bcrypt';
import { getUsers, saveDb } from '../config/db.js';

let _nextId = null;

function nextId() {
  if (_nextId === null) {
    const users = getUsers();
    _nextId = users.length > 0 ? Math.max(...users.map(u => u.user_id)) + 1 : 1;
  }
  return _nextId++;
}

function sanitize(user) {
  if (!user) return null;
  const { password_hash, ...safe } = user;
  return safe;
}

// ── Queries ────────────────────────────────────────────────────────────────

export async function findUserByEmail(email) {
  if (!email) return null;
  return getUsers().find(u => u.email.toLowerCase() === email.toLowerCase()) ?? null;
}

export async function findUserByUsername(username) {
  if (!username) return null;
  return getUsers().find(u => u.username.toLowerCase() === username.toLowerCase()) ?? null;
}

export async function findUserById(userId) {
  const user = getUsers().find(u => String(u.user_id) === String(userId));
  return sanitize(user);
}

export async function createUser({ fullName, username, email, passwordHash, role, preferredLanguage }) {
  const users = getUsers();
  const user = {
    user_id: nextId(),
    full_name: fullName,
    username,
    email,
    password_hash: passwordHash,
    role: role || 'Deaf',
    preferred_language: preferredLanguage || 'en',
    profile_picture: null,
    created_at: new Date().toISOString()
  };
  users.push(user);
  saveDb();
  console.log(`[JSON DB] Created user: ${username} (id=${user.user_id})`);
  return sanitize(user);
}

export async function searchUsers(query, currentUserId) {
  const q = (query || '').toLowerCase();
  return getUsers()
    .filter(u =>
      String(u.user_id) !== String(currentUserId) &&
      (u.username.toLowerCase().includes(q) ||
       u.full_name.toLowerCase().includes(q) ||
       u.email.toLowerCase().includes(q))
    )
    .map(sanitize);
}

export async function updateUser(userId, updates) {
  const users = getUsers();
  const idx = users.findIndex(u => String(u.user_id) === String(userId));
  if (idx === -1) return null;
  const allowed = ['full_name', 'preferred_language', 'profile_picture', 'role'];
  allowed.forEach(k => { if (updates[k] !== undefined) users[idx][k] = updates[k]; });
  saveDb();
  return sanitize(users[idx]);
}
