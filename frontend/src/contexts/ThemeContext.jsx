import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { storage } from '../utils/storage.js';
const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [dark, setDark] = useState(storage.get('sign-link-theme') === 'dark');

  useEffect(() => {
    document.documentElement.classList.toggle('dark', dark);
    storage.set('sign-link-theme', dark ? 'dark' : 'light');
  }, [dark]);

  const value = useMemo(() => ({ dark, setDark }), [dark]);
  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export const useTheme = () => useContext(ThemeContext);
