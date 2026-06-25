import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { FormInput } from '../components/FormInput.jsx';
import { useAuth } from '../contexts/AuthContext.jsx';
import { useI18n } from '../contexts/I18nContext.jsx';

export function Login() {
  const { login } = useAuth();
  const { t } = useI18n();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: '', password: '' });
  const [error, setError] = useState('');

  async function submit(event) {
    event.preventDefault();
    setError('');
    try {
      await login(form);
      navigate('/dashboard');
    } catch (err) {
      setError(err.response?.data?.message || 'Login failed');
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <h1>{t('login')}</h1>
        {error ? <div className="alert">{error}</div> : null}
        <FormInput label={t('email')} type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
        <FormInput label={t('password')} type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} required />
        <button className="primary-button" type="submit">{t('login')}</button>
        <Link to="/register">{t('register')}</Link>
      </form>
    </main>
  );
}
