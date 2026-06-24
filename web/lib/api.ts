import { User, Token, Chat, Message } from '../types';
import * as mock from './mockBackend';

// Toggle mock mode by setting NEXT_PUBLIC_USE_MOCK=true in .env.local / Vercel.
// When true, all API calls are intercepted by mockBackend.ts and run
// entirely in the browser using localStorage. No real server required.
const USE_MOCK =
  typeof process !== 'undefined' &&
  process.env.NEXT_PUBLIC_USE_MOCK === 'true';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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