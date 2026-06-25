import { Router } from 'express';
import { findUsers, getProfile, updateProfile } from '../controllers/userController.js';
import { authenticate } from '../middleware/auth.js';
import { validate } from '../middleware/validate.js';
import { profileRules } from '../validators/profileValidators.js';

export const userRouter = Router();

userRouter.use(authenticate);
userRouter.get('/profile', getProfile);
userRouter.put('/profile', profileRules, validate, updateProfile);
userRouter.get('/search', findUsers);
