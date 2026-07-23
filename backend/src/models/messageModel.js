// messageModel.js — JSON-backed message store

import { getMessages, saveDb } from '../config/db.js';
import { findUserById } from './userModel.js';

let _nextId = null;

function nextId() {
  if (_nextId === null) {
    const msgs = getMessages();
    _nextId = msgs.length > 0 ? Math.max(...msgs.map(m => m.message_id)) + 1 : 1;
  }
  return _nextId++;
}

export async function createMessage(senderId, receiverId, messageText) {
  const messages = getMessages();
  const sender   = await findUserById(senderId);
  const receiver = await findUserById(receiverId);

  const msg = {
    message_id: nextId(),
    sender_id: senderId,
    receiver_id: receiverId,
    message_text: messageText,
    created_at: new Date().toISOString(),
    seen_at: null,
    sender_username:   sender?.username   ?? String(senderId),
    receiver_username: receiver?.username ?? String(receiverId)
  };

  messages.push(msg);
  saveDb();
  return msg;
}

export async function listConversation(userId, peerId) {
  return getMessages()
    .filter(m =>
      (String(m.sender_id) === String(userId)   && String(m.receiver_id) === String(peerId)) ||
      (String(m.sender_id) === String(peerId)   && String(m.receiver_id) === String(userId))
    )
    .sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
}

export async function markConversationSeen(userId, peerId) {
  const messages = getMessages();
  const seenAt = new Date().toISOString();
  const updated = [];
  messages.forEach(m => {
    if (String(m.sender_id) === String(peerId) &&
        String(m.receiver_id) === String(userId) &&
        !m.seen_at) {
      m.seen_at = seenAt;
      updated.push(m);
    }
  });
  if (updated.length) saveDb();
  return updated;
}
