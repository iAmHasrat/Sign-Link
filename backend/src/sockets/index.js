import { authenticateSocket } from '../middleware/auth.js';
import { createCall, finishCall } from '../models/callModel.js';
import { createMessage, markConversationSeen } from '../models/messageModel.js';

const onlineUsers = new Map();

function onlineSnapshot() {
  return [...onlineUsers.entries()].map(([userId, socketIds]) => ({
    userId,
    online: socketIds.size > 0
  }));
}

export function registerSockets(io) {
  io.use(authenticateSocket);

  io.on('connection', (socket) => {
    const userId = socket.user.userId;
    const sUserId = String(userId);
    if (!onlineUsers.has(sUserId)) onlineUsers.set(sUserId, new Set());
    onlineUsers.get(sUserId).add(socket.id);

    // Join both number and string format rooms for 100% signaling delivery
    socket.join(`user:${userId}`);
    socket.join(`user:${sUserId}`);
    console.log(`[Socket.IO] Connected socket ${socket.id} for user ${sUserId} (rooms: user:${userId}, user:${sUserId})`);

    socket.emit('presence-snapshot', onlineSnapshot());
    io.emit('user-online', { userId: sUserId, online: true });

    socket.on('typing', ({ receiverId, isTyping }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('typing', { senderId: sUserId, isTyping: Boolean(isTyping) });
    });

    socket.on('send-message', async ({ receiverId, messageText }, ack) => {
      try {
        const target = String(receiverId);
        const message = await createMessage(sUserId, target, messageText);
        socket.emit('message-sent', message);
        io.to(`user:${receiverId}`).to(`user:${target}`).emit('message-received', message);
        ack?.({ ok: true, message });
      } catch (error) {
        ack?.({ ok: false, message: error.message });
      }
    });

    socket.on('messages-seen', async ({ peerId }, ack) => {
      try {
        const target = String(peerId);
        const seenMessages = await markConversationSeen(sUserId, target);
        io.to(`user:${peerId}`).to(`user:${target}`).emit('messages-seen', {
          byUserId: sUserId,
          messageIds: seenMessages.map((message) => message.message_id),
          seenAt: new Date().toISOString()
        });
        ack?.({ ok: true, seenMessages });
      } catch (error) {
        ack?.({ ok: false, message: error.message });
      }
    });

    socket.on('incoming-call', async ({ receiverId, offer }, ack) => {
      try {
        const target = String(receiverId);
        console.log('[Socket.IO] incoming-call received from caller:', sUserId, 'for receiver:', target);
        const callId = await createCall(sUserId, target);
        io.to(`user:${receiverId}`).to(`user:${target}`).emit('incoming-call', { callId, callerId: sUserId, offer });
        console.log('[Socket.IO] incoming-call successfully forwarded to rooms: user:' + receiverId + ', user:' + target);
        ack?.({ ok: true, callId });
      } catch (error) {
        console.error('[Socket.IO] incoming-call error:', error);
        ack?.({ ok: false, message: error.message });
      }
    });

    socket.on('call-accepted', ({ callerId, callId, answer }) => {
      const target = String(callerId);
      console.log('[Socket.IO] call-accepted from receiver:', sUserId, 'to caller:', target);
      io.to(`user:${callerId}`).to(`user:${target}`).emit('call-accepted', { callId, receiverId: sUserId, answer });
    });

    socket.on('call-rejected', async ({ callerId, callId }) => {
      const target = String(callerId);
      if (callId) await finishCall(callId, 'rejected');
      io.to(`user:${callerId}`).to(`user:${target}`).emit('call-rejected', { callId, receiverId: sUserId });
    });

    socket.on('offer', ({ receiverId, callId, offer }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('offer', { callId, callerId: sUserId, offer });
    });

    socket.on('answer', ({ receiverId, callId, answer }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('answer', { callId, senderId: sUserId, answer });
    });

    socket.on('ice-candidate', ({ receiverId, callId, candidate }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('ice-candidate', { callId, senderId: sUserId, candidate });
    });

    socket.on('call-ended', async ({ receiverId, callId }) => {
      const target = String(receiverId);
      if (callId) await finishCall(callId, 'completed');
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('call-ended', { callId, senderId: sUserId });
    });

    socket.on('translation', ({ receiverId, text, inputMethod }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('translation', { senderId: sUserId, text, inputMethod });
    });

    socket.on('live-caption', ({ receiverId, text }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('live-caption', { senderId: sUserId, text });
    });

    socket.on('peer-landmarks', ({ receiverId, landmarks }) => {
      const target = String(receiverId);
      io.to(`user:${receiverId}`).to(`user:${target}`).emit('peer-landmarks', { senderId: sUserId, landmarks });
    });

    socket.on('disconnect', () => {
      const sockets = onlineUsers.get(sUserId);
      sockets?.delete(socket.id);
      if (!sockets || sockets.size === 0) {
        io.emit('user-online', { userId, online: false });
      }
    });
  });
}
