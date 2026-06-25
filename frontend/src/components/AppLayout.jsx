import { Bell, History, Home, LogOut, MessageSquare, Moon, Search, Settings, User, Video } from 'lucide-react';
import { NavLink, Outlet } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';
import { useTheme } from '../contexts/ThemeContext.jsx';

const navItems = [
  ['dashboard', '/dashboard', Home],
  ['search', '/search', Search],
  ['chat', '/chat', MessageSquare],
  ['videoCall', '/call', Video],
  ['history', '/history', History],
  ['profile', '/profile', User],
  ['settings', '/settings', Settings]
];

export function AppLayout() {
  const { logout, user } = useAuth();
  const { t, language, setLanguage } = useI18n();
  const { dark, setDark } = useTheme();

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <NavLink to="/dashboard" className="brand">
          <span>SL</span>
          <strong>{t('appName')}</strong>
        </NavLink>
        <nav className="nav-list">
          {navItems.map(([key, href, Icon]) => (
            <NavLink key={href} to={href} className="nav-link">
              <Icon size={19} aria-hidden="true" />
              <span>{t(key)}</span>
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="main-panel">
        <header className="topbar">
          <div>
            <p className="eyebrow">{user?.role}</p>
            <h1>{user?.full_name}</h1>
          </div>
          <div className="top-actions">
            <select value={language} onChange={(event) => setLanguage(event.target.value)} aria-label={t('language')}>
              <option value="en">English</option>
              <option value="hi">हिन्दी</option>
              <option value="pa">ਪੰਜਾਬੀ</option>
            </select>
            <button className="icon-button" onClick={() => setDark(!dark)} aria-label={t('darkMode')}>
              <Moon size={18} />
            </button>
            <button className="icon-button" aria-label="Notifications">
              <Bell size={18} />
            </button>
            <button className="ghost-button" onClick={logout}>
              <LogOut size={18} />
              {t('logout')}
            </button>
          </div>
        </header>
        <Outlet />
      </main>
    </div>
  );
}
