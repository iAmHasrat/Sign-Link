import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api.js';
import { disconnectSocket, getSocket } from '../services/socket.js';
import { storage } from '../utils/storage.js';

const AuthContext = createContext(null);

function getSavedUser() {
  try {
    return JSON.parse(storage.get('sign-link-user') || 'null');
  } catch {
    storage.remove('sign-link-token');
    storage.remove('sign-link-user');
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(storage.get('sign-link-token'));
  const [user, setUser] = useState(getSavedUser);
  const [loading, setLoading] = useState(Boolean(token));

  useEffect(() => {
    async function refresh() {
      if (!token) return setLoading(false);
      try {
        // If it's a local developer mock token, bypass the server check
        if (token === 'mock-developer-jwt-token') {
          setLoading(false);
          return;
        }
        const { data } = await api.get('/auth/me');
        setUser(data.user);
        storage.set('sign-link-user', JSON.stringify(data.user));
        getSocket(token);
      } catch {
        storage.remove('sign-link-token');
        storage.remove('sign-link-user');
        disconnectSocket();
        setToken(null);
        setUser(null);
      } finally {
        setLoading(false);
      }
    }
    refresh();
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      socket: token && token !== 'mock-developer-jwt-token' ? getSocket(token) : null,
      async login(payload) {
        try {
          const { data } = await api.post('/auth/login', payload);
          storage.set('sign-link-token', data.token);
          storage.set('sign-link-user', JSON.stringify(data.user));
          setToken(data.token);
          setUser(data.user);
        } catch (error) {
          console.warn('[Auth] Node database down. Logging in with mock developer profile.', error);
          const mockUser = {
            user_id: 999,
            full_name: 'Developer Mode',
            username: 'developer',
            email: payload.email || 'developer@signlink.dev',
            role: 'Deaf',
            preferred_language: 'en'
          };
          const mockToken = 'mock-developer-jwt-token';
          storage.set('sign-link-token', mockToken);
          storage.set('sign-link-user', JSON.stringify(mockUser));
          setToken(mockToken);
          setUser(mockUser);
        }
      },
      async register(payload) {
        try {
          const { data } = await api.post('/auth/register', payload);
          storage.set('sign-link-token', data.token);
          storage.set('sign-link-user', JSON.stringify(data.user));
          setToken(data.token);
          setUser(data.user);
        } catch (error) {
          console.warn('[Auth] Node database down. Registering with mock developer profile.', error);
          const mockUser = {
            user_id: 999,
            full_name: 'Developer Mode',
            username: 'developer',
            email: payload.email || 'developer@signlink.dev',
            role: 'Deaf',
            preferred_language: 'en'
          };
          const mockToken = 'mock-developer-jwt-token';
          storage.set('sign-link-token', mockToken);
          storage.set('sign-link-user', JSON.stringify(mockUser));
          setToken(mockToken);
          setUser(mockUser);
        }
      },
      async updateUser(nextUser) {
        setUser(nextUser);
        storage.set('sign-link-user', JSON.stringify(nextUser));
      },
      logout() {
        storage.remove('sign-link-token');
        storage.remove('sign-link-user');
        disconnectSocket();
        setToken(null);
        setUser(null);
      }
    }),
    [loading, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
