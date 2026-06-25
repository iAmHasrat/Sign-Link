import { asyncHandler } from '../utils/asyncHandler.js';

export const predictSign = asyncHandler(async (req, res) => {
  res.json({ sign: 'HELP', confidence: 0.95, provider: 'placeholder' });
});

export const translate = asyncHandler(async (req, res) => {
  const { text = '', targetLanguage = 'en' } = req.body;
  res.json({ sourceText: text, translatedText: text, targetLanguage, provider: 'placeholder' });
});

export const speechToText = asyncHandler(async (req, res) => {
  res.json({ text: '', provider: 'placeholder' });
});

export const textToSpeech = asyncHandler(async (req, res) => {
  res.json({ audioUrl: null, provider: 'placeholder' });
});
