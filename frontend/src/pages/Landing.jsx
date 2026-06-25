import { MessageCircle, ShieldCheck, Video } from 'lucide-react';
import { Link } from 'react-router-dom';
import { useI18n } from '../contexts/I18nContext.jsx';

export function Landing() {
  const { t } = useI18n();
  return (
    <main className="landing">
      <nav className="public-nav">
        <div className="brand">
          <span>SL</span>
          <strong>{t('appName')}</strong>
        </div>
        <div>
          <Link className="ghost-button" to="/login">{t('login')}</Link>
          <Link className="primary-button" to="/register">{t('register')}</Link>
        </div>
      </nav>
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Inclusive communication</p>
          <h1>{t('appName')}</h1>
          <p>{t('tagline')}</p>
          <div className="hero-actions">
            <Link className="primary-button" to="/register">{t('register')}</Link>
            <Link className="ghost-button" to="/login">{t('login')}</Link>
          </div>
        </div>
        <div className="hero-media" aria-hidden="true">
          <div className="video-tile large"><Video /></div>
          <div className="video-tile"><MessageCircle /></div>
          <div className="video-tile accent"><ShieldCheck /></div>
        </div>
      </section>
      <section className="feature-band">
        <article><Video /><h2>WebRTC calls</h2><p>Private one-to-one video with audio, camera, and fullscreen controls.</p></article>
        <article><MessageCircle /><h2>Realtime chat</h2><p>Socket.IO messaging, timestamps, online status, and typing presence.</p></article>
        <article><ShieldCheck /><h2>Secure access</h2><p>JWT sessions, hashed passwords, validation, Helmet, and MySQL storage.</p></article>
      </section>
    </main>
  );
}
