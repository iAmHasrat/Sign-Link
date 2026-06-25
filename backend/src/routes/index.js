import { Router } from 'express';
import { aiRouter } from './aiRoutes.js';
import { authRouter } from './authRoutes.js';
import { callRouter } from './callRoutes.js';
import { messageRouter } from './messageRoutes.js';
import { userRouter } from './userRoutes.js';

export const apiRouter = Router();

apiRouter.get('/health', (req, res) => res.json({ status: 'ok', service: 'sign-link-api' }));
apiRouter.use('/auth', authRouter);
apiRouter.use('/users', userRouter);
apiRouter.use('/messages', messageRouter);
apiRouter.use('/calls', callRouter);
apiRouter.use('/', aiRouter);
