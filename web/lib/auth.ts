import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types';
import { fetchMe } from './api';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  /**
   * Re-fetch the user from the backend. Use this after any action
   * that could change the user record (subscription update, profile
   * edit, plan upgrade) so the rest of the UI sees the fresh state
   * without a full page reload.
   */
  refresh: () => Promise<void>;
  /**
   * Replace the cached user object in-place. Useful for "edit my
   * profile" flows where the new value is already known and we just
   * need the rest of the app to see it.
   */
  setUser: (u: User | null) => void;
}

const AuthContext = createContext<AuthContextType>({
  user: null,
  loading: true,
  refresh: async () => {},
  setUser: () => {},
});

/**
 * Session boot path. Replaces the old JWT-decode-on-boot (insecure —
 * any user can read the payload) with a real GET /users/me call.
 *
 * Outcomes:
 *   - No stored token       → user is null, loading false
 *   - Stored token + valid  → user populated, loading false
 *   - Stored token + 401    → token is bad; we cleared it, user is null
 *   - Network error         → user is null (treated as logged out);
 *                             the next page load will retry
 *
 * The provider is intentionally forgiving: a failed /me call never
 * throws to the consumer. Pages that need an authenticated user still
 * gate on `useAuth().user` and redirect themselves.
 */
export const SessionProvider = ({ children }: { children: React.ReactNode }) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  const refresh = useCallback(async () => {
    try {
      const u = await fetchMe();
      setUser(u);
    } catch {
      setUser(null);
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (typeof window === 'undefined') {
        setLoading(false);
        return;
      }
      const token = window.localStorage.getItem('token');
      if (!token) {
        if (!cancelled) {
          setUser(null);
          setLoading(false);
        }
        return;
      }
      try {
        const u = await fetchMe();
        if (!cancelled) setUser(u);
      } catch {
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const value = React.useMemo<AuthContextType>(
    () => ({ user, loading, refresh, setUser }),
    [user, loading, refresh]
  );

  return React.createElement(AuthContext.Provider, { value }, children);
};

export const useAuth = () => useContext(AuthContext);
