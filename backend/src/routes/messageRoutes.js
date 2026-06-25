import { Router } from 'express';
import { conversationRules, getConversation, markSeen, messageRules, sendMessage } from '../controllers/messageController.js';
import { authenticate } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';

export const messageRouter = Router();

messageRouter.use(authenticate);
messageRouter.get('/:peerId', conversationRules, validate, getConversation);
messageRouter.patch('/:peerId/seen', conversationRules, validate, markSeen);
messageRouter.post('/', messageRules, validate, sendMessage);
