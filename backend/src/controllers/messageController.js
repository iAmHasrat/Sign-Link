import { body, param } from 'express-validator';
import { asyncHandler } from '../utils/asyncHandler.js';
import { createMessage, listConversation, markConversationSeen } from '../models/messageModel.js';

export const messageRules = [
  body('receiverId').isInt({ min: 1 }).withMessage('Receiver is required'),
  body('messageText').trim().isLength({ min: 1, max: 2000 }).withMessage('Message must be 1-2000 characters')
];

export const conversationRules = [param('peerId').isInt({ min: 1 }).withMessage('Peer id is required')];

export const sendMessage = asyncHandler(async (req, res) => {
  const message = await createMessage(req.user.userId, req.body.receiverId, req.body.messageText);
  req.app.get('io')?.to(`user:${req.body.receiverId}`).emit('message-received', message);
  res.status(201).json({ message });
});

export const getConversation = asyncHandler(async (req, res) => {
  const messages = await listConversation(req.user.userId, Number(req.params.peerId));
  res.json({ messages });
});

export const markSeen = asyncHandler(async (req, res) => {
  const peerId = Number(req.params.peerId);
  const seenMessages = await markConversationSeen(req.user.userId, peerId);
  req.app.get('io')?.to(`user:${peerId}`).emit('messages-seen', {
    byUserId: req.user.userId,
    messageIds: seenMessages.map((message) => message.message_id),
    seenAt: new Date().toISOString()
  });
  res.json({ seenMessages });
});
