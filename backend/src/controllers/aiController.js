import { asyncHandler } from '../utils/asyncHandler.js';

export const predictSign = asyncHandler(async (req, res) => {
  res.json({ sign: 'HELP', confidence: 0.95, provider: 'placeholder' });
});

export const translate = asyncHandler(async (req, res) => {
  const { text = '', targetLanguage = 'en' } = req.body;
  if (!text.trim()) {
    return res.json({ sourceText: text, translatedText: '', targetLanguage });
  }

  const langMap = {
    hi: 'hi',
    pa: 'pa',
    en: 'en',
    es: 'es',
    fr: 'fr',
    de: 'de',
    zh: 'zh-CN'
  };
  const tl = langMap[targetLanguage] || targetLanguage || 'en';

  // Primary: Google GTX Translation API
  try {
    const url = `https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=${tl}&dt=t&q=${encodeURIComponent(text)}`;
    const response = await fetch(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
      }
    });
    if (response.ok) {
      const data = await response.json();
      const translatedText = data[0].map((item) => item[0]).join('');
      if (translatedText) {
        return res.json({ sourceText: text, translatedText, targetLanguage: tl, provider: 'google-gtx' });
      }
    }
  } catch (err) {
    console.warn('[AI Controller] Primary Google GTX translate failed, trying MyMemory fallback:', err.message);
  }

  // Fallback: MyMemory Translation API
  try {
    const fallbackUrl = `https://api.mymemory.translated.net/get?q=${encodeURIComponent(text)}&langpair=auto|${tl}`;
    const fbRes = await fetch(fallbackUrl);
    if (fbRes.ok) {
      const fbData = await fbRes.json();
      const translatedText = fbData?.responseData?.translatedText;
      if (translatedText) {
        return res.json({ sourceText: text, translatedText, targetLanguage: tl, provider: 'mymemory' });
      }
    }
  } catch (fbErr) {
    console.error('[AI Controller] Fallback translation failed:', fbErr.message);
  }

  res.json({ sourceText: text, translatedText: text, targetLanguage: tl, provider: 'passthrough' });
});

export const speechToText = asyncHandler(async (req, res) => {
  res.json({ text: '', provider: 'placeholder' });
});

export const textToSpeech = asyncHandler(async (req, res) => {
  res.json({ audioUrl: null, provider: 'placeholder' });
});
