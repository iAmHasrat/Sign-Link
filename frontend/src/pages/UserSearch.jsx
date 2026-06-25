import { MessageSquare, Search, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useI18n } from '../contexts/I18nContext.jsx';
import { api } from '../services/api.js';

export function UserSearch() {
  const { t } = useI18n();
  const [q, setQ] = useState('');
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const timer = setTimeout(async () => {
      setLoading(true);
      try {
        const { data } = await api.get('/users/search', { params: { q } });
        setUsers(data.users);
      } finally {
        setLoading(false);
      }
    }, 250);
    return () => clearTimeout(timer);
  }, [q]);

  return (
    <section className="page-stack">
      <div className="tool-row">
        <label className="search-box">
          <Search size={18} />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search name, username, or email" />
        </label>
      </div>
      <div className="list-panel">
        {loading ? <p>Searching...</p> : null}
        {users.map((user) => (
          <article className="user-row" key={user.user_id}>
            <div className="avatar">{user.full_name?.slice(0, 1)}</div>
            <div>
              <h3>{user.full_name}</h3>
              <p>@{user.username} · {user.role}</p>
            </div>
            <div className="row-actions">
              <Link className="icon-button" to={`/chat/${user.user_id}`} aria-label={t('chat')}><MessageSquare size={18} /></Link>
              <Link className="icon-button" to={`/call/${user.user_id}`} aria-label={t('videoCall')}><Video size={18} /></Link>
            </div>
          </article>
        ))}
        {!loading && users.length === 0 ? <p>No users found.</p> : null}
      </div>
    </section>
  );
}
