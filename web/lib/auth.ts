import React, { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
});

export const SessionProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const token = localStorage.getItem('token');
    if (token) {
      // In a real app, you would validate the token and fetch user data
      // For now, we'll decode the JWT to get user info (not secure for production!)
      try {
        // Base64 decode the payload part of JWT
        const payloadBase64 = token.split('.')[1];
        const payload = JSON.parse(atob(payloadBase64));

        // Create user object from token payload.
        // The JWT only carries id + email; fill remaining User fields
        // with safe null/empty defaults so it satisfies the full type.
        const userData: User = {
          id: payload.user_id || payload.sub ?
            (typeof payload.sub === 'string' && payload.sub.startsWith('google_') ?
             hashString(payload.sub) :
             parseInt(payload.sub)) : 1,
          email: payload.email || '',
          username: payload.username || null,
          full_name: payload.full_name || payload.name || null,
          bio: payload.bio || null,
          avatar_url: payload.avatar_url || payload.picture || null,
          is_active: payload.is_active !== false,
          is_verified: payload.is_verified === true,
          google_id: payload.google_id ||
            (typeof payload.sub === 'string' && payload.sub.startsWith('google_')
              ? payload.sub
              : null),
        };
        setUser(userData);
      } catch (e) {
        // If token parsing fails, fall back to a minimal mock user
        setUser({
          id: 1,
          email: 'user@example.com',
          username: null,
          full_name: null,
          bio: null,
          avatar_url: null,
          is_active: true,
          is_verified: false,
          google_id: null,
        });
      }
    } else {
      setUser(null);
    }
    setLoading(false);
  }, []);

  // Simple string hash function for demo purposes
  const hashString = (str: string) => {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
      const char = str.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32bit integer
    }
    return Math.abs(hash);
  };

  return React.createElement(AuthContext.Provider, { value: { user: user, loading: loading } }, children);
};

export const useAuth = () => useContext(AuthContext);