import { Router } from 'express';
import { getCallHistory } from '../controllers/callController.js';
import { authenticate } from '../middleware/auth.js';

export const callRouter = Router();

callRouter.use(authenticate);
callRouter.get('/history', getCallHistory);
