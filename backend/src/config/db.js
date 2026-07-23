// db.js — JSON File Store (replaces MySQL for local/demo use)
// No external database required. Data persists to db.json next to this file.

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const DB_FILE = path.resolve(__dirname, '../../db.json');

// ── In-memory store ────────────────────────────────────────────────────────
let _db = {
  users: [],
  messages: [],
  calls: []
};

// Load from disk on startup
function _load() {
  try {
    if (fs.existsSync(DB_FILE)) {
      const raw = fs.readFileSync(DB_FILE, 'utf8');
      _db = JSON.parse(raw);
      console.log(`[JSON DB] Loaded from ${DB_FILE} — ${_db.users.length} users, ${_db.messages.length} messages`);
    } else {
      _save(); // create empty file
      console.log('[JSON DB] No db.json found — created fresh store.');
    }
  } catch (e) {
    console.warn('[JSON DB] Could not load db.json, starting fresh:', e.message);
  }
}

function _save() {
  try {
    fs.writeFileSync(DB_FILE, JSON.stringify(_db, null, 2), 'utf8');
  } catch (e) {
    console.warn('[JSON DB] Could not save db.json:', e.message);
  }
}

_load();

// ── Public API (same shape as mysql2 pool, but no-op ping) ────────────────
export const pool = {
  // Not used — kept so any leftover imports don't crash
  query: async () => [[], []],
  execute: async () => [[], []],
  getConnection: async () => ({ ping: async () => {}, release: () => {} })
};

export async function pingDatabase() {
  console.log('[JSON DB] pingDatabase() — JSON store is always available ✓');
}

// ── Store accessors (used by models) ─────────────────────────────────────
export function getUsers()    { return _db.users; }
export function getMessages() { return _db.messages; }
export function getCalls()    { return _db.calls; }
export function saveDb()      { _save(); }
