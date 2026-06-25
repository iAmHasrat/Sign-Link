import { Router } from 'express';
import { login, me, register } from '../controllers/authController.js';
import { authenticate } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { loginRules, registerRules } from '../validators/authValidators.js';

export const authRouter = Router();

authRouter.post('/register', registerRules, validate, register);
authRouter.post('/login', loginRules, validate, login);
authRouter.get('/me', authenticate, me);
