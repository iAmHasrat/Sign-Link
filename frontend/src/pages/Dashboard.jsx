import { Clock, Sparkles, Video } from 'lucide-react';
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
          <p>Connect by video, gesture translation, and accessible multilingual workflows.</p>
        </div>
        <Sparkles aria-hidden="true" />
      </div>
      <div className="action-grid">
        <Link to="/translator" className="action-card"><Sparkles /><h3>{t('translator')}</h3><p>Realtime ISL sign language gesture recognition & translation.</p></Link>
        <Link to="/call" className="action-card"><Video /><h3>{t('videoCall')}</h3><p>Start secure one-to-one WebRTC video sessions.</p></Link>
        <Link to="/history" className="action-card"><Clock /><h3>{t('history')}</h3><p>Review completed, rejected, and missed calls.</p></Link>
      </div>
    </section>
  );
}
