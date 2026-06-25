import { Router } from 'express';
import { predictSign, speechToText, textToSpeech, translate } from '../controllers/aiController.js';
import { authenticate } from '../middleware/auth.js';

export const aiRouter = Router();

aiRouter.use(authenticate);
aiRouter.post('/sign/predict', predictSign);
aiRouter.post('/translate', translate);
aiRouter.post('/speech-to-text', speechToText);
aiRouter.post('/text-to-speech', textToSpeech);
