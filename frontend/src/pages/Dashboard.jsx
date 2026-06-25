import { Clock, MessageSquare, Search, Sparkles, Video } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';

export function Dashboard() {
  const { user } = useAuth();
  const { t } = useI18n();

  return (
    <section className="page-stack">
      <div className="dashboard-hero">
        <div>
          <p className="eyebrow">Welcome back</p>
          <h2>{user?.full_name}</h2>
          <p>Connect by video, message, and accessible multilingual workflows.</p>
        </div>
        <Sparkles aria-hidden="true" />
      </div>
      <div className="action-grid">
        <Link to="/search" className="action-card"><Search /><h3>{t('search')}</h3><p>Find Deaf or Hearing users by name, username, or email.</p></Link>
        <Link to="/chat" className="action-card"><MessageSquare /><h3>{t('chat')}</h3><p>Send realtime messages and see typing indicators.</p></Link>
        <Link to="/call" className="action-card"><Video /><h3>{t('videoCall')}</h3><p>Start secure one-to-one WebRTC video sessions.</p></Link>
        <Link to="/history" className="action-card"><Clock /><h3>{t('history')}</h3><p>Review completed, rejected, and missed calls.</p></Link>
      </div>
    </section>
  );
}
