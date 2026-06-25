/**
 * Mock backend — runs entirely in the browser using localStorage.
 * Mirrors the real FastAPI API contract so the rest of the frontend
 * doesn't need to know whether it's hitting a server or this shim.
 *
 * Activated when NEXT_PUBLIC_USE_MOCK === 'true'.
 *
 * Storage: single JSON blob per "table" under _mock_db_<name>.
 * Persistence: per-browser, per-origin. Cleared with browser data.
 * Security: NOT a real auth system — passwords are stored locally.
 * This is a demo backend, not for production use.
 */

import { User, Token, Chat, Message } from '../types';

const DB_PREFIX = '_mock_db_';
const TOKEN_KEY = 'token';

// ---------- low-level storage helpers ----------

const readTable = <T>(name: string): T[] => {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(DB_PREFIX + name);
    return raw ? (JSON.parse(raw) as T[]) : [];
  } catch {
    return [];
  }
};

const writeTable = <T>(name: string, rows: T[]): void => {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(DB_PREFIX + name, JSON.stringify(rows));
};

// ---------- internal extended types (with password + admin flag) ----------

type StoredUser = User & {
  password: string;
  is_admin?: boolean;
} & Record<string, unknown>;

type StoredChat = Chat & { id: number };
type StoredMessage = Message & { id: number; chat_id: number; is_ai: boolean } & Record<string, unknown>;

// ---------- utilities ----------

const nowIso = () => new Date().toISOString();

let _idCounter = 0;
const nextId = (existing: { id: number }[]): number => {
  _idCounter += 1;
  return existing.length ? Math.max(_idCounter, ...existing.map((x) => x.id)) + 1 : _idCounter;
};

// Encode a JWT-shaped token (header.payload.signature) so `auth.ts`
// can decode it the same way it decodes real backend tokens.
// NOT cryptographically secure — just base64 of JSON.
const mockSignJwt = (payload: Record<string, unknown>): string => {
  const header = { alg: 'none', typ: 'JWT' };
  const enc = (obj: unknown) =>
    btoa(JSON.stringify(obj))
      .replace(/=+$/, '')
      .replace(/\+/g, '-')
      .replace(/\//g, '_');
  return `${enc(header)}.${enc(payload)}.mock-signature`;
};

const requireAuth = (): StoredUser => {
  const token = typeof window !== 'undefined' ? localStorage.getItem(TOKEN_KEY) : null;
  if (!token) throw new Error('Not authenticated');
  const payload = JSON.parse(atob(token.split('.')[1]));
  const users = readTable<StoredUser>('users');
  const user = users.find((u) => u.id === payload.user_id);
  if (!user) throw new Error('User not found');
  return user;
};

const delay = (ms = 150) => new Promise((r) => setTimeout(r, ms));

// Seed the default admin user on first load, so the UI is explorable.
const seedIfEmpty = () => {
  const users = readTable<StoredUser>('users');
  if (users.length === 0) {
    const adminUser: StoredUser = {
      id: 1,
      email: 'admin@novamind.ai',
      username: 'admin',
      full_name: 'System Administrator',
      bio: 'Default admin (mock mode)',
      avatar_url: null,
      is_active: true,
      is_verified: true,
      google_id: null,
      is_admin: true,
      password: 'admin123',
    };
    writeTable('users', [adminUser]);
  }
};

// ---------- public demo-credentials helper ----------
// Surfaced by the UI so any page can pre-fill or hint at the demo login.
// Lives in mockBackend so the seed values live with the seed code.
export const DEMO_CREDENTIALS = Object.freeze({
  email: 'admin@novamind.ai',
  password: 'admin123',
});

export const getDemoCredentials = () => DEMO_CREDENTIALS;

if (typeof window !== 'undefined') {
  seedIfEmpty();
}

// ---------- auth ----------

export const mockRegister = async (email: string, password: string): Promise<Token> => {
  await delay();
  if (!email || !password) throw new Error('Email and password required');
  const users = readTable<StoredUser>('users');
  if (users.find((u) => u.email === email)) {
    throw new Error('Email already registered');
  }
  const newUser: StoredUser = {
    id: nextId(users),
    email,
    username: email.split('@')[0],
    full_name: null,
    bio: null,
    avatar_url: null,
    is_active: true,
    is_verified: false,
    google_id: null,
    is_admin: false,
    password,
  };
  users.push(newUser);
  writeTable('users', users);

  const token = mockSignJwt({
    sub: String(newUser.id),
    user_id: newUser.id,
    email: newUser.email,
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 8,
  });
  localStorage.setItem(TOKEN_KEY, token);
  return { access_token: token, token_type: 'bearer' };
};

export const mockLogin = async (email: string, password: string): Promise<Token> => {
  await delay();
  const users = readTable<StoredUser>('users');
  const user = users.find((u) => u.email === email && u.password === password);
  if (!user) throw new Error('Invalid email or password');
  const token = mockSignJwt({
    sub: String(user.id),
    user_id: user.id,
    email: user.email,
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 8,
  });
  localStorage.setItem(TOKEN_KEY, token);
  return { access_token: token, token_type: 'bearer' };
};

export const mockGoogleLogin = async (_token: string): Promise<{ access_token: string; user: any }> => {
  await delay();
  const email = 'demo.google@novamind.ai';
  const users = readTable<StoredUser>('users');
  let user = users.find((u) => u.email === email);
  if (!user) {
    user = {
      id: nextId(users),
      email,
      username: 'demo.google',
      full_name: 'Demo Google User',
      bio: null,
      avatar_url: null,
      is_active: true,
      is_verified: true,
      google_id: 'google_demo',
      is_admin: false,
      password: '',
    };
    users.push(user);
    writeTable('users', users);
  }
  const access = mockSignJwt({
    sub: `google_${user.id}`,
    user_id: user.id,
    email: user.email,
    exp: Math.floor(Date.now() / 1000) + 60 * 60 * 24 * 8,
  });
  localStorage.setItem(TOKEN_KEY, access);
  return { access_token: access, user };
};

// ---------- chats ----------

export const mockGetChats = async (): Promise<Chat[]> => {
  await delay();
  const user = requireAuth();
  return readTable<StoredChat>('chats')
    .filter((c) => c.user_id === user.id)
    .sort((a, b) => (b.updated_at || b.created_at || '').localeCompare(a.updated_at || a.created_at || ''));
};

export const mockCreateChat = async (title: string): Promise<Chat> => {
  await delay();
  const user = requireAuth();
  const chats = readTable<StoredChat>('chats');
  const chat: StoredChat = {
    id: nextId(chats),
    title: title || 'New chat',
    user_id: user.id,
    chat_type: 'private',
    status: 'active',
    settings: {},
    tags: null,
    created_at: nowIso(),
    updated_at: nowIso(),
    last_message_at: null,
  };
  chats.push(chat);
  writeTable('chats', chats);
  return chat;
};

export const mockDeleteChat = async (chatId: number): Promise<void> => {
  await delay();
  const user = requireAuth();
  writeTable(
    'chats',
    readTable<StoredChat>('chats').filter((c) => !(c.id === chatId && c.user_id === user.id)),
  );
  writeTable(
    'messages',
    readTable<StoredMessage>('messages').filter((m) => m.chat_id !== chatId),
  );
};

export const mockGetMessages = async (chatId: number): Promise<Message[]> => {
  await delay();
  requireAuth();
  return readTable<StoredMessage>('messages')
    .filter((m) => m.chat_id === chatId)
    .sort((a, b) => (a.created_at || '').localeCompare(b.created_at || ''));
};

// ---------- message-sending with a deterministic mock LLM ----------

const MOCK_REPLIES = [
  "That's an interesting point. Let me think about it...",
  "Here's how I'd approach that: start small, validate the idea, then iterate.",
  "I'm running in mock mode right now (no backend), but here's a thoughtful reply.",
  "Could you tell me more about what you're trying to achieve?",
  "Got it. In a real deployment I'd call the LLM service here — for now this is a placeholder.",
  "The NovaMind architecture is designed for exactly this kind of conversation.",
];

export const mockSendMessage = async (chatId: number, content: string): Promise<void> => {
  await delay(400);
  const user = requireAuth();
  const messages = readTable<StoredMessage>('messages');

  messages.push({
    id: nextId(messages),
    chat_id: chatId,
    user_id: user.id,
    content,
    message_type: 'text',
    is_ai: false,
    meta_data: {},
    created_at: nowIso(),
  });

  // Touch chat updated_at so list ordering follows latest activity.
  const chats = readTable<StoredChat>('chats');
  const chat = chats.find((c) => c.id === chatId);
  if (chat) {
    chat.updated_at = nowIso();
    chat.last_message_at = nowIso();
  }
  writeTable('chats', chats);
  writeTable('messages', messages);

  // Generate an assistant reply after a slightly longer delay (mimics LLM).
  setTimeout(() => {
    const allMessages = readTable<StoredMessage>('messages');
    const reply = MOCK_REPLIES[Math.floor(Math.random() * MOCK_REPLIES.length)];
    allMessages.push({
      id: nextId(allMessages),
      chat_id: chatId,
      user_id: null,
      content: reply,
      message_type: 'text',
      is_ai: true,
      meta_data: { model: 'mock-llm-v1', tokens: reply.length },
      created_at: nowIso(),
    });
    writeTable('messages', allMessages);

    // Fire a custom event the chat page listens for to refresh messages.
    if (typeof window !== 'undefined') {
      window.dispatchEvent(new CustomEvent('mock:message-added', { detail: { chatId } }));
    }
  }, 900);
};

// ---------- admin / utility ----------

export const mockResetData = async (): Promise<void> => {
  if (typeof window === 'undefined') return;
  Object.keys(window.localStorage)
    .filter((k) => k.startsWith(DB_PREFIX) || k === TOKEN_KEY)
    .forEach((k) => window.localStorage.removeItem(k));
  seedIfEmpty();
};

export const mockListUsers = async (): Promise<User[]> => {
  await delay();
  requireAuth();
  return readTable<StoredUser>('users').map(({ password: _p, is_admin: _a, ...u }) => u as User);
};

export const mockGetCurrentUser = async (): Promise<User> => {
  await delay();
  const u = requireAuth();
  const { password: _p, is_admin: _a, ...rest } = u;
  return rest as User;
};

export const mockLogout = (): void => {
  if (typeof window !== 'undefined') localStorage.removeItem(TOKEN_KEY);
};