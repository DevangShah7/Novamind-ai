import { ApiKey, User } from '../types';
import { getChats, createChat } from './api';
import { extractErrorMessage } from './validation';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

/**
 * Body shape for `POST /admin/`. The backend's `UserAdminCreate`
 * schema is a superset of the public `UserCreate` — it adds
 * `is_admin` and accepts a password (required for new accounts).
 * `Partial<User>` is too narrow because `password` isn't a User
 * field (the User type only has `google_id`, etc., not the
 * plaintext credential).
 */
export interface AdminUserCreate {
  email: string;
  password: string;
  username?: string;
  full_name?: string;
  is_admin?: boolean;
}

/**
 * Body shape for `PUT /admin/{id}`. The `password` field is
 * optional — leaving it out means "don't change the password".
 * The backend hashes any non-empty value before persisting.
 */
export interface AdminUserUpdate {
  email?: string;
  username?: string | null;
  full_name?: string | null;
  password?: string;
  is_active?: boolean;
  is_verified?: boolean;
  is_admin?: boolean;
}

/** Authenticated admin fetch. Surfaces FastAPI's `detail` (string or
 *  422 validation list) as a useful Error. */
async function adminFetch(path: string, init?: RequestInit): Promise<Response> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('token') : null;
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      ...(init?.headers || {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });
  if (!res.ok) {
    throw new Error(await extractErrorMessage(res, `Request failed (${res.status})`));
  }
  return res;
}

export const getSystemStats = async (): Promise<any> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/admin/stats/`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch system stats');
  }
  return res.json();
};

export const getApiKeys = async (): Promise<ApiKey[]> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/api-keys/`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch API keys');
  }
  return res.json();
};

export const createApiKey = async (name: string, description?: string): Promise<ApiKey> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/api-keys/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify({ name, description }),
  });
  if (!res.ok) {
    throw new Error('Failed to create API key');
  }
  return res.json();
};

export const updateApiKey = async (
  keyId: number,
  updates: Partial<{ name: string; description: string; is_active: boolean; expires_at: string }>
): Promise<ApiKey> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/api-keys/${keyId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(updates),
  });
  if (!res.ok) {
    throw new Error('Failed to update API key');
  }
  return res.json();
};

export const deleteApiKey = async (keyId: number): Promise<void> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/api-keys/${keyId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to delete API key');
  }
};

export const validateApiKey = async (keyId: number): Promise<any> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/api-keys/${keyId}/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to validate API key');
  }
  return res.json();
};

// User management functions
export const getUsers = async (): Promise<User[]> => {
  const res = await adminFetch('/admin/');
  return res.json();
};

export const createUser = async (userData: AdminUserCreate): Promise<User> => {
  const res = await adminFetch('/admin/', {
    method: 'POST',
    body: JSON.stringify(userData),
  });
  return res.json();
};

export const updateUser = async (
  userId: number,
  userData: AdminUserUpdate
): Promise<User> => {
  const res = await adminFetch(`/admin/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(userData),
  });
  return res.json();
};

export const deleteUser = async (userId: number): Promise<void> => {
  await adminFetch(`/admin/${userId}`, { method: 'DELETE' });
};