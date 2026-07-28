import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { User } from '../types';
import { fetchMe, login as apiLogin } from './api';

/**
 * Dev-only auto-login bypass.
 *
 * Set NEXT_PUBLIC_DEV_AUTO_LOGIN=true in web/.env.local (or in Vercel env vars)
 * to skip the login screen entirely. When true, `SessionProvider` performs a
 * real `POST /auth/login` against the seeded admin account on mount, stores
 * the resulting JWT in localStorage, and populates the user from `/users/me`.
 * From that point the app behaves indistinguishably from a normal sign-in —
 * every API call carries a valid Bearer token, so /chat, /admin, /billing,
 * /api-keys all load real data.
 *
 * This is a deliberate trade-off: the fake-user variant used to ship a
 * synthetic object that the backend rejected with 401, so the UI rendered
 * but every data fetch failed. Minting a real JWT fixes that at the cost
 * of (a) a single login round-trip on mount, and (b) the token expiring
 * after ACCESS_TOKEN_EXPIRE_MINUTES (refresh path below).
 *
 * Intended for poking around the UI while the OAuth-based permanent tunnel
 * setup is blocked on a manual `cloudflared tunnel login` step. Do NOT
 * enable in real production — anyone with the env flag set becomes admin.
 * The default (unset) keeps the real login flow.
 */
const DEV_AUTO_LOGIN =
  typeof process !== 'undefined' &&
  process.env.NEXT_PUBLIC_DEV_AUTO_LOGIN === 'true';

// Must match the seeded admin created in backend/app/main.py on first boot.
const DEV_ADMIN_EMAIL = 'admin@novamind.ai';
const DEV_ADMIN_PASSWORD = 'admin123';

/** localStorage key for the bypass marker, so a 401 can trigger one re-login. */
const DEV_BYPASS_KEY = 'novamind_dev_bypass';

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

  /**
   * Perform the dev bypass: log in as the seeded admin and stash the JWT.
   * Safe to call repeatedly — if a real (non-fake) token is already in
   * localStorage, this is a no-op. On 401 (expired token), we drop the
   * stale token and try once more.
   *
   * If both attempts fail (network down, tunnel rotated, etc.) we stash
   * the error message in localStorage so the /login page can show it in
   * a banner — silent redirects with no error context have been the #1
   * source of "I don't know why this isn't working" pain.
   */
  const devBypassLogin = useCallback(async (): Promise<User | null> => {
    if (typeof window === 'undefined') return null;
    // Drop any synthetic token left over from the old fake-user variant
    // so the next login starts clean.
    const existing = window.localStorage.getItem('token');
    if (existing === 'dev-bypass-token-not-valid') {
      window.localStorage.removeItem('token');
    }
    const recordError = (msg: string) => {
      try {
        window.localStorage.setItem('novamind_dev_bypass_error', msg);
      } catch {
        // localStorage quota / privacy mode — fine to swallow.
      }
    };
    const tryOnce = async (): Promise<User | null> => {
      const tok = await apiLogin(DEV_ADMIN_EMAIL, DEV_ADMIN_PASSWORD);
      window.localStorage.setItem('token', tok.access_token);
      window.localStorage.setItem(DEV_BYPASS_KEY, '1');
      window.localStorage.removeItem('novamind_dev_bypass_error');
      return await fetchMe();
    };
    try {
      return await tryOnce();
    } catch (err: any) {
      // First attempt failed — record what we tried so the user can see
      // it on /login if the retry also fails.
      const apiBase =
        (typeof process !== 'undefined' &&
          process.env.NEXT_PUBLIC_API_URL) ||
        '(unset)';
      recordError(
        `Couldn't reach the backend at ${apiBase}. ` +
          `The dev tunnel may have rotated — sign in manually below. ` +
          `(${err?.message || 'network error'})`
      );
      // 401 → token went bad, clear and retry once.
      window.localStorage.removeItem('token');
      try {
        return await tryOnce();
      } catch (err2: any) {
        // Both attempts failed. The user is about to land on /login
        // (or already there) — they need to see WHY.
        recordError(
          `Couldn't reach the backend at ${apiBase}. ` +
            `The dev tunnel may have rotated — sign in manually below. ` +
            `(${err2?.message || 'network error'})`
        );
        // eslint-disable-next-line no-console
        console.warn('[NovaMind dev bypass] login failed; falling through to /login.', err2);
        return null;
      }
    }
  }, []);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (typeof window === 'undefined') {
        setLoading(false);
        return;
      }
      if (DEV_AUTO_LOGIN) {
        const u = await devBypassLogin();
        if (!cancelled) {
          setUser(u);
          setLoading(false);
        }
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
  }, [devBypassLogin]);

  const value = React.useMemo<AuthContextType>(
    () => ({ user, loading, refresh, setUser }),
    [user, loading, refresh]
  );

  return React.createElement(AuthContext.Provider, { value }, children);
};

export const useAuth = () => useContext(AuthContext);
