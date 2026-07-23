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

const mockUser = {
  id: 999,
  full_name: 'Developer Guest',
  email: 'dev@signlink.org',
  role: 'Developer'
};
const mockToken = 'mock-developer-jwt-token';

export function AuthProvider({ children }) {
  // Ensure mock values are in storage on startup for Axios interceptors
  if (!storage.get('sign-link-token')) {
    storage.set('sign-link-token', mockToken);
    storage.set('sign-link-user', JSON.stringify(mockUser));
  }

  const [token, setToken] = useState(() => storage.get('sign-link-token') || mockToken);
  const [user, setUser] = useState(() => {
    try {
      return JSON.parse(storage.get('sign-link-user')) || mockUser;
    } catch {
      return mockUser;
    }
  });
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Disable server-side session refresh to bypass database
    setLoading(false);
  }, [token]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      socket: null,
      async login(payload) {
        const email = payload.email || 'dev@signlink.org';
        const name = email.split('@')[0];
        const isB = name.toLowerCase().includes('b');
        const customUser = {
          id: isB ? 888 : 999,
          full_name: isB ? 'Developer B' : 'Developer A',
          email: email,
          role: 'Developer',
          username: isB ? 'dev_b' : 'dev_a'
        };
        const customToken = isB ? 'mock-token-b' : 'mock-token-a';

        storage.set('sign-link-token', customToken);
        storage.set('sign-link-user', JSON.stringify(customUser));
        setToken(customToken);
        setUser(customUser);
      },
      async register(payload) {
        const email = payload.email || 'dev@signlink.org';
        const name = email.split('@')[0];
        const isB = name.toLowerCase().includes('b');
        const customUser = {
          id: isB ? 888 : 999,
          full_name: isB ? 'Developer B' : 'Developer A',
          email: email,
          role: 'Developer',
          username: isB ? 'dev_b' : 'dev_a'
        };
        const customToken = isB ? 'mock-token-b' : 'mock-token-a';

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
    [loading, token, user]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}



export const useAuth = () => useContext(AuthContext);
