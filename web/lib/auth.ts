import { createContext, useContext, useState, useEffect } from 'react';
import { User } from '../types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
});

export const AuthProvider = ({ children }: { children: React.ReactNode }) => {
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

        // Create user object from token payload
        const userData: User = {
          id: payload.user_id || payload.sub ?
            (typeof payload.sub === 'string' && payload.sub.startsWith('google_') ?
             hashString(payload.sub) :
             parseInt(payload.sub)) : 1,
          email: payload.email || '',
          is_active: payload.is_active !== false,
          // Add other fields as needed from token
        };
        setUser(userData);
      } catch (e) {
        // If token parsing fails, fall back to mock user
        setUser({ id: 1, email: 'user@example.com', is_active: true });
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