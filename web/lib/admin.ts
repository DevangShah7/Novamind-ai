import { ApiKey, User } from '../types';
import { getChats, createChat } from './api';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

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
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/admin/`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to fetch users');
  }
  return res.json();
};

export const createUser = async (userData: Partial<User>): Promise<User> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/admin/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(userData),
  });
  if (!res.ok) {
    throw new Error('Failed to create user');
  }
  return res.json();
};

export const updateUser = async (
  userId: number,
  userData: Partial<User>
): Promise<User> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/admin/${userId}`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(userData),
  });
  if (!res.ok) {
    throw new Error('Failed to update user');
  }
  return res.json();
};

export const deleteUser = async (userId: number): Promise<void> => {
  const token = localStorage.getItem('token');
  const res = await fetch(`${API_URL}/admin/${userId}`, {
    method: 'DELETE',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!res.ok) {
    throw new Error('Failed to delete user');
  }
};