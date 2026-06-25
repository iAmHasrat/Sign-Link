import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FormInput } from '../components/FormInput.jsx';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';

export function Register() {
  const { register } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState({
    fullName: '',
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    role: 'Deaf',
    preferredLanguage: 'en'
  });
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      await register(form);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.message || 'Registration failed');
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card wide" onSubmit={submit}>
        <h1>{t('register')}</h1>
        {error ? <div className="alert">{error}</div> : null}
        <div className="grid-2">
          <FormInput label={t('fullName')} value={form.fullName} onChange={(e) => setForm({ ...form, fullName: e.target.value })} required />
          <FormInput label={t('username')} value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          <FormInput label={t('email')} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <FormInput label={t('password')} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
          <FormInput label={t('confirmPassword')} type="password" value={form.confirmPassword} onChange={(e) => setForm({ ...form, confirmPassword: e.target.value })} required />
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
        </div>
        <button className="primary-button" type="submit">{t('register')}</button>
        <Link to="/login">{t('login')}</Link>
      </form>
    </main>
  );
}
