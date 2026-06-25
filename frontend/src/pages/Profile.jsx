import { useState } from 'react';
import { FormInput } from '../components/FormInput.jsx';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';
import { api } from '../services/api.js';

export function Profile() {
  const { user, updateUser } = useAuth();
  const { t } = useI18n();
  const [form, setForm] = useState({
    fullName: user?.full_name || '',
    role: user?.role || 'Deaf',
    preferredLanguage: user?.preferred_language || 'en',
    profilePicture: user?.profile_picture || ''
  });
  const [saved, setSaved] = useState(false);

  async function submit(event) {
    event.preventDefault();
    const { data } = await api.put('/users/profile', form);
    updateUser(data.user);
    setSaved(true);
  }

  return (
    <section className="page-stack">
      <form className="settings-panel" onSubmit={submit}>
        {saved ? <div className="success">Profile updated.</div> : null}
        <FormInput label={t('fullName')} value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} />
        <FormInput label="Profile picture URL" value={form.profilePicture} onChange={(e) => setForm({ ...form, profilePicture: e.target.value })} />
        <label className="field">
          <span>{t('role')}</span>
          <select value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
            <option value="Deaf">{t('deaf')}</option>
            <option value="Hearing">{t('hearing')}</option>
          </select>
        </label>
        <label className="field">
          <span>{t('language')}</span>
          <select value={form.preferredLanguage} onChange={(e) => setForm({ ...form, preferredLanguage: e.target.value })}>
            <option value="en">English</option>
            <option value="hi">हिन्दी</option>
            <option value="pa">ਪੰਜਾਬੀ</option>
          </select>
        </label>
        <button className="primary-button" type="submit">{t('save')}</button>
      </form>
    </section>
  );
}
