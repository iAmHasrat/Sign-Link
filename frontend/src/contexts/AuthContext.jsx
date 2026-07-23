import { createContext, useContext, useEffect, useMemo, useState } from 'react';
import { api } from '../services/api.js';
import { disconnectSocket, getSocket } from '../services/socket.js';
import { storage } from '../utils/storage.js';

const AuthContext = createContext(null);

const userA = {
  id: 999,
  user_id: 999,
  full_name: 'User A (Laptop 1)',
  email: 'a@signlink.org',
  role: 'Developer',
  username: 'dev_a'
};

const userB = {
  id: 888,
  user_id: 888,
  full_name: 'User B (Laptop 2)',
  email: 'b@signlink.org',
  role: 'Developer',
  username: 'dev_b'
};

const tokenA = 'mock-token-a';
const tokenB = 'mock-token-b';

export function AuthProvider({ children }) {
  if (!storage.get('sign-link-token')) {
    storage.set('sign-link-token', tokenA);
    storage.set('sign-link-user', JSON.stringify(userA));
  }

  const [token, setToken] = useState(() => storage.get('sign-link-token') || tokenA);
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(storage.get('sign-link-user')) || userA;
    } catch {
      return userA;
    }
  });
  const [loading, setLoading] = useState(false);
  const [socket, setSocket] = useState(null);

  // Manage live Socket.IO connection
  useEffect(() => {
    if (token) {
      const s = getSocket(token);
      setSocket(s);
    } else {
      disconnectSocket();
      setSocket(null);
    }
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      socket,
      switchUser(type = 'A') {
        const nextUser = type === 'B' ? userB : userA;
        const nextToken = type === 'B' ? tokenB : tokenA;
        storage.set('sign-link-token', nextToken);
        storage.set('sign-link-user', JSON.stringify(nextUser));
        setToken(nextToken);
        setUser(nextUser);
      },
      async login(payload) {
        const email = payload.email || 'a@signlink.org';
        const isB = email.toLowerCase().includes('b');
        const customUser = isB ? userB : userA;
        const customToken = isB ? tokenB : tokenA;

        storage.set('sign-link-token', customToken);
        storage.set('sign-link-user', JSON.stringify(customUser));
        setToken(customToken);
        setUser(customUser);
      },
      async register(payload) {
        const email = payload.email || 'a@signlink.org';
        const isB = email.toLowerCase().includes('b');
        const customUser = isB ? userB : userA;
        const customToken = isB ? tokenB : tokenA;

        storage.set('sign-link-token', customToken);
        storage.set('sign-link-user', JSON.stringify(customUser));
        setToken(customToken);
        setUser(customUser);
      },
      async updateUser(nextUser) {
        setUser(nextUser);
        storage.set('sign-link-user', JSON.stringify(nextUser));
      },
      logout() {
        storage.remove('sign-link-token');
        storage.remove('sign-link-user');
        setToken(null);
        setUser(null);
      }
    }),
    [loading, token, user, socket]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
