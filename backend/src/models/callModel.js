// callModel.js — JSON-backed call store

import { getCalls, saveDb } from '../config/db.js';

let _nextId = null;

function nextId() {
  if (_nextId === null) {
    const calls = getCalls();
    _nextId = calls.length > 0 ? Math.max(...calls.map(c => c.call_id)) + 1 : 1;
  }
  return _nextId++;
}

export async function createCall(callerId, receiverId, status = 'started') {
  const calls = getCalls();
  const call = {
    call_id: nextId(),
    caller_id: callerId,
    receiver_id: receiverId,
    status,
    started_at: new Date().toISOString(),
    ended_at: null
  };
  calls.push(call);
  saveDb();
  console.log('[JSON DB] createCall', { callId: call.call_id, callerId, receiverId });
  return call.call_id;
}

export async function finishCall(callId, status = 'completed') {
  const calls = getCalls();
  const call = calls.find(c => String(c.call_id) === String(callId));
  if (call) {
    call.status = status;
    call.ended_at = new Date().toISOString();
    saveDb();
  }
  console.log('[JSON DB] finishCall', { callId, status });
}

export async function listCallHistory(userId) {
  return getCalls()
    .filter(c => String(c.caller_id) === String(userId) || String(c.receiver_id) === String(userId))
    .sort((a, b) => new Date(b.started_at) - new Date(a.started_at));
}
