import { User, Token, Chat, Message } from '../types';
import * as mock from './mockBackend';

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

export const register = async (email: string, password: string): Promise<Token> => {
  if (USE_MOCK) return mock.mockRegister(email, password);
  const res = await fetch(`${API_URL}/auth/register`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Registration failed');
  }
  return res.json();
};

export const login = async (email: string, password: string): Promise<Token> => {
  if (USE_MOCK) return mock.mockLogin(email, password);
  const res = await fetch(`${API_URL}/auth/login`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const error = await res.json();
    throw new Error(error.detail || 'Login failed');
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

// Re-export so other components can detect mock mode (e.g. to show a banner).
export const isMockMode = USE_MOCK;