import { useI18n } from '../contexts/I18nContext.jsx';
import { useTheme } from '../contexts/ThemeContext.jsx';

export function Settings() {
  const { t, language, setLanguage } = useI18n();
  const { dark, setDark } = useTheme();

  return (
    <section className="page-stack">
      <div className="settings-panel">
        <label className="setting-row">
          <span>{t('language')}</span>
          <select value={language} onChange={(e) => setLanguage(e.target.value)}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="pa">ਪੰਜਾਬੀ</option>
          </select>
        </label>
        <label className="setting-row">
          <span>{t('darkMode')}</span>
          <input type="checkbox" checked={dark} onChange={(e) => setDark(e.target.checked)} />
        </label>
      </div>
    </section>
  );
}
