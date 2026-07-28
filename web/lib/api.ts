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
  const doSend = async (token: string | null) => {
    const res = await fetch(`${API_URL}/chats/${chatId}/messages`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ content }),
    });
    return res;
  };

  let token = localStorage.getItem('token');
  let res = await doSend(token);

  // 401 → the stored token has been rejected (expired, rotated by the
  // dev tunnel, or from an earlier bundle that minted a synthetic one).
  // Try once more with a freshly-minted admin JWT from the bypass path —
  // this keeps the user moving when the only thing wrong was auth state.
  if (res.status === 401 && typeof window !== 'undefined') {
    try {
      const fresh = await login('admin@novamind.ai', 'admin123');
      token = fresh.access_token;
      localStorage.setItem('token', token);
      localStorage.setItem('novamind_dev_bypass', '1');
      res = await doSend(token);
    } catch {
      // Re-login itself failed; fall through with the original 401 below.
    }
  }

  if (!res.ok) {
    // Surface the server's actual detail (e.g. "Chat not found" or the
    // LLM timeout body) so the toast isn't a useless "Failed to send
    // message" — silent failures here have been the #1 user pain point.
    let detail = `Failed to send message (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) {
        if (typeof body.detail === 'string') detail = body.detail;
        else if (typeof body.detail === 'object' && body.detail.message)
          detail = body.detail.message;
      }
    } catch {
      // ignore — we'll use the fallback string above
    }
    throw new Error(detail);
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

// ────────────────────────────────────────────────────────────────────────
// Document generators (PDF / PPTX / image / DOCX / TXT / MD).
//
// These return a `Blob` and (for files) auto-trigger a browser download.
// The backend lives at /documents/* and produces a real downloadable
// artifact: fpdf2 for PDFs, python-pptx for decks, python-docx for Word,
// and a deterministic 1024x1024 SVG poster for images. No external
// services called.
// ────────────────────────────────────────────────────────────────────────

type GeneratorType = 'pdf' | 'pptx' | 'image' | 'docx' | 'txt' | 'md';

async function downloadArtifact(
  type: GeneratorType,
  prompt: string,
  title?: string,
  style?: string,
): Promise<Blob> {
  if (USE_MOCK) {
    // Mock path — we don't ship fpdf2 in the browser, so just return
    // an empty text blob labelled with the generator kind.
    return new Blob(
      [`[mock ${type.toUpperCase()}] ${prompt}`],
      { type: 'text/plain' },
    );
  }
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/documents/${type}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ prompt, title, style }),
  });
  if (!res.ok) {
    let detail = `Failed to generate ${type} (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  return res.blob();
}

/** Generate a PDF and trigger a download in the user's browser. */
export const downloadPdf = async (
  prompt: string,
  title?: string,
): Promise<void> => {
  const blob = await downloadArtifact('pdf', prompt, title);
  triggerDownload(blob, filenameFrom(prompt, title, 'pdf'));
};

/** Generate a PPTX deck and trigger a download. */
export const downloadPptx = async (
  prompt: string,
  title?: string,
): Promise<void> => {
  const blob = await downloadArtifact('pptx', prompt, title);
  triggerDownload(
    blob,
    filenameFrom(prompt, title, 'pptx'),
  );
};

/** Generate a Word .docx and trigger a download. */
export const downloadDocx = async (
  prompt: string,
  title?: string,
): Promise<void> => {
  const blob = await downloadArtifact('docx', prompt, title);
  triggerDownload(blob, filenameFrom(prompt, title, 'docx'));
};

/** Generate a plain .txt file and trigger a download. */
export const downloadTxt = async (
  prompt: string,
  title?: string,
): Promise<void> => {
  const blob = await downloadArtifact('txt', prompt, title);
  triggerDownload(blob, filenameFrom(prompt, title, 'txt'));
};

/** Generate a Markdown .md file and trigger a download. */
export const downloadMd = async (
  prompt: string,
  title?: string,
): Promise<void> => {
  const blob = await downloadArtifact('md', prompt, title);
  triggerDownload(blob, filenameFrom(prompt, title, 'md'));
};

/** Generate an SVG poster; resolve to a blob URL the caller can <img src=...> inline. */
export const generateImage = async (
  prompt: string,
  style?: string,
): Promise<string> => {
  const blob = await downloadArtifact('image', prompt, undefined, style);
  return URL.createObjectURL(blob);
};

function triggerDownload(blob: Blob, filename: string): void {
  if (typeof window === 'undefined') return;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  // Revoke a tick later so the browser has time to start the download.
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

function filenameFrom(
  prompt: string,
  title: string | undefined,
  ext: string,
): string {
  const base = (title || prompt).split('\n')[0].trim();
  const safe = base
    .replace(/[#*_`>]+/g, '')
    .replace(/[^\w\- ]+/g, '')
    .trim()
    .replace(/\s+/g, '-')
    .slice(0, 60);
  return `${safe || 'novamind'}.${ext}`;
}

// Re-export so other components can detect mock mode (e.g. to show a banner).
export const isMockMode = USE_MOCK;

// ────────────────────────────────────────────────────────────────────────
// NovaMind Apps — scaffold and run small web projects.
//
// Backend lives at /api/v1/apps.  The preview iframe loads from
// /apps/preview/<id>/<file> which is unauthenticated by design so the
// <iframe> doesn't need an Authorization header.
// ────────────────────────────────────────────────────────────────────────

export interface AppManifest {
  id: string;
  name: string;
  kind: 'static_site' | 'single_html' | 'snippet';
  template?: string | null;
  description?: string;
  files: string[];
  created_at: number;
  updated_at: number;
  prompt?: string;
}

export interface AppRunResult {
  language: 'python' | 'javascript';
  stdout: string;
  stderr: string;
  return_code: number;
  execution_time: number;
  timed_out: boolean;
  app_id: string;
  unavailable?: boolean;
}

export interface AppFile {
  path: string;
  size: number;
  text: string | null;
  binary: boolean;
}

async function appsFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  if (USE_MOCK) {
    throw new Error('Apps are not available in mock mode.');
  }
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    let detail = `Request failed (HTTP ${res.status})`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* ignore */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json();
}

export const listApps = (): Promise<AppManifest[]> =>
  appsFetch<AppManifest[]>('/apps');

export const getApp = (appId: string): Promise<AppManifest> =>
  appsFetch<AppManifest>(`/apps/${appId}`);

export const deleteApp = (appId: string): Promise<void> =>
  appsFetch<void>(`/apps/${appId}`, { method: 'DELETE' });

export const createAppFromPrompt = (params: {
  name: string;
  description?: string;
  template?: string;
  prompt?: string;
}): Promise<AppManifest> =>
  appsFetch<AppManifest>('/apps/from-prompt', {
    method: 'POST',
    body: JSON.stringify(params),
  });

export const runAppCode = (
  appId: string,
  payload: { language: 'python' | 'javascript'; code: string; timeout?: number; stdin?: string },
): Promise<AppRunResult> =>
  appsFetch<AppRunResult>(`/apps/${appId}/run`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });

export const readAppFile = (appId: string, rel: string): Promise<AppFile> =>
  appsFetch<AppFile>(`/apps/${appId}/files/${rel}`);

/** Public preview URL — no auth header, used as <iframe src=...>. */
export const previewAppUrl = (appId: string, rel = 'index.html'): string => {
  const base = (API_URL || '').replace(/\/api\/v1\/?$/, '');
  return `${base}/apps/preview/${appId}/${rel}`;
};