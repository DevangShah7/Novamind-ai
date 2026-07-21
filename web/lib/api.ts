import { User, Token, RegisterResult, Chat, Message } from '../types';
import * as mock from './mockBackend';
import { extractErrorMessage } from './validation';

// Re-export so the UI can use a single import path for the demo creds.
export const getDemoCredentials = mock.getDemoCredentials;

// Toggle mock mode by setting NEXT_PUBLIC_USE_MOCK=true in .env.local / Vercel.
// When true, all API calls are intercepted by mockBackend.ts and run
// entirely in the browser using localStorage. No real server required.
const USE_MOCK =
  typeof process !== 'undefined' &&
  process.env.NEXT_PUBLIC_USE_MOCK === 'true';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// One-time mock-mode sanity check on the client. Catches the "stale localStorage"
// case where a previous session stored a token whose user no longer exists in
// the current seed. Without this, users hit a silent redirect loop on /chat.
if (typeof window !== 'undefined' && USE_MOCK) {
  try {
    const token = window.localStorage.getItem('token');
    const usersRaw = window.localStorage.getItem('_mock_db_users');
    if (token && (!usersRaw || JSON.parse(usersRaw).length === 0)) {
      // Token from a prior session, but the users table is empty (was cleared
      // or seed didn't run for some reason). Drop the orphan token so the user
      // lands on /login instead of looping.
      window.localStorage.removeItem('token');
      // eslint-disable-next-line no-console
      console.warn(
        '[NovaMind mock] Stale token detected and cleared. Please log in with',
        mock.getDemoCredentials(),
      );
    }
  } catch {
    /* localStorage may be unavailable (SSR / private mode); ignore. */
  }
}

export const register = async (
  email: string,
  password: string
): Promise<RegisterResult> => {
  if (USE_MOCK) return mock.mockRegister(email, password);
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    // FastAPI returns 422 with a list of validation objects when the
    // password fails the rules in `schemas/user.py`. The default
    // `await res.json()` then `error.detail` flow would push an array
    // straight into the UI as "[object Object]"; `extractErrorMessage`
    // flattens the list to a readable string ("Password must contain
    // at least one letter and one digit") so the user can act on it.
    throw new Error(await extractErrorMessage(res, 'Registration failed'));
  }
  // The backend now returns 202 + `MessageResponse` and emails a
  // verification link. The client UI shows "check your inbox"; the
  // user is NOT logged in until they click the link and call
  // /auth/verify-email (which redirects them to /login?registered=1).
  return { requiresVerification: true, email };
};

/**
 * Verify a user's email using the token from the verification link.
 * Returns true on success, throws on failure (expired / unknown token).
 */
export const verifyEmail = async (token: string): Promise<boolean> => {
  if (USE_MOCK) return true;
  const res = await fetch(`${API_URL}/auth/verify-email`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Email verification failed');
  }
  return true;
};

/**
 * Ask the backend to email a fresh verification link. Returns true if
 * the request was accepted (the backend always returns 200, even when
 * the address is unknown, so callers should treat errors as opaque).
 */
export const resendVerification = async (email: string): Promise<boolean> => {
  if (USE_MOCK) return true;
  const res = await fetch(`${API_URL}/auth/resend-verification`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Could not resend verification email');
  }
  return true;
};

/**
 * Start the "forgot password" flow. The backend always returns 200 to
 * avoid leaking which emails are registered — UI should show a
 * neutral "if the account exists, we sent a link" message either way.
 */
export const forgotPassword = async (email: string): Promise<boolean> => {
  if (USE_MOCK) return true;
  const res = await fetch(`${API_URL}/auth/forgot-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Could not start password reset');
  }
  return true;
};

/**
 * Complete the "forgot password" flow with the token from the reset
 * link and a new password. Returns true on success, throws on failure
 * (expired token, too-short password, etc.).
 */
export const resetPassword = async (token: string, newPassword: string): Promise<boolean> => {
  if (USE_MOCK) return true;
  const res = await fetch(`${API_URL}/auth/reset-password`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Password reset failed');
  }
  return true;
};

export const login = async (email: string, password: string): Promise<Token> => {
  if (USE_MOCK) return mock.mockLogin(email, password);
  // FastAPI's OAuth2PasswordRequestForm expects form-urlencoded with a
  // `username` field (the email) and `password`. Sending JSON yields 422.
  const body = new URLSearchParams({ username: email, password });
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  });
  if (!res.ok) {
    // Same pattern as `register` above: 422 returns a list of
    // validation objects, not a string. Flatten to a single message
    // so the login form can show something the user can act on.
    throw new Error(await extractErrorMessage(res, 'Login failed'));
  }
  return res.json();
};

export const googleLogin = async (token: string): Promise<{ access_token: string; user: any }> => {
  if (USE_MOCK) return mock.mockGoogleLogin(token);
  const res = await fetch(`${API_URL}/auth/google`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ token }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Google login failed');
  }
  return res.json();
};

export const getChats = async (): Promise<Chat[]> => {
  if (USE_MOCK) return mock.mockGetChats();
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/chats`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch chats');
  }
  return res.json();
};

export const createChat = async (title: string): Promise<Chat> => {
  if (USE_MOCK) return mock.mockCreateChat(title);
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/chats`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ title }),
  });
  if (!res.ok) {
    throw new Error('Failed to create chat');
  }
  return res.json();
};

export const getMessages = async (chatId: string): Promise<Message[]> => {
  if (USE_MOCK) return mock.mockGetMessages(Number(chatId));
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/chats/${chatId}/messages`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch messages');
  }
  return res.json();
};

export const sendMessage = async (chatId: string, content: string): Promise<void> => {
  if (USE_MOCK) return mock.mockSendMessage(Number(chatId), content);
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/chats/${chatId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ content }),
  });
  if (!res.ok) {
    throw new Error('Failed to send message');
  }
};

export const deleteChat = async (chatId: string): Promise<void> => {
  if (USE_MOCK) return mock.mockDeleteChat(Number(chatId));
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/chats/${chatId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok && res.status !== 404) {
    throw new Error('Failed to delete chat');
  }
};

export const logout = (): void => {
  if (USE_MOCK) return mock.mockLogout();
  localStorage.removeItem('token');
};

/**
 * Fetch the authenticated user's profile. Used by the session boot
 * path to populate the user object without trusting a client-side
 * JWT decode. A 401 here means the stored token is bad — the
 * caller should clear it and redirect to /login.
 */
export const fetchMe = async (): Promise<User> => {
  if (USE_MOCK) {
    // In mock mode, pull the user out of the seeded localStorage.
    // Returns a minimal "demo user" shape if no session exists, so
    // a cold boot doesn't crash — pages that need a real session
    // still gate on `localStorage.getItem('token')`.
    const token = localStorage.getItem('token');
    if (!token) {
      throw new Error('Not signed in');
    }
    return mock.mockGetCurrentUser();
  }
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/users/me`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    if (res.status === 401) {
      // Stored token is bad — clear it so the next page load is
      // a clean unauthenticated state.
      localStorage.removeItem('token');
    }
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Could not load profile');
  }
  return res.json();
};

/**
 * Change the authenticated user's password. Returns true on success
 * and throws on failure (current password wrong, new password too
 * short, etc.). The backend also bumps `token_version` so the user
 * has to sign in again on any other device.
 */
export const changePassword = async (
  currentPassword: string,
  newPassword: string
): Promise<boolean> => {
  if (USE_MOCK) return true;
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/users/me/change-password`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({
      current_password: currentPassword,
      new_password: newPassword,
    }),
  });
  if (!res.ok) {
    const error = await res.json().catch(() => ({}));
    throw new Error(error.detail || 'Could not change password');
  }
  return true;
};

// Re-export so other components can detect mock mode (e.g. to show a banner).
export const isMockMode = USE_MOCK;