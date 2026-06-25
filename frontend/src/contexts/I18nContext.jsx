import { createContext, useContext, useMemo, useState } from 'react';
import en from '../i18n/en.json';
import hi from '../i18n/hi.json';
import pa from '../i18n/pa.json';
import { storage } from '../utils/storage.js';

const dictionaries = { en, hi, pa };
const I18nContext = createContext(null);

export function I18nProvider({ children }) {
  const [language, setLanguage] = useState(storage.get('sign-link-language') || 'en');
  const value = useMemo(() => {
    const t = (key) => dictionaries[language]?.[key] || dictionaries.en[key] || key;
    return {
      language,
      setLanguage: (next) => {
        storage.set('sign-link-language', next);
        setLanguage(next);
      },
      t
    };
  }, [language]);

  return <I18nContext.Provider value={value}>{children}</I18nContext.Provider>;
}

export const useI18n = () => useContext(I18nContext);
