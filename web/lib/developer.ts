// Centralised helpers for the Developer Portal.
// The backend exposes:
//   GET    /api/v1/api-keys/                        (JWT auth, list keys)
//   POST   /api/v1/api-keys/                        (create)
//   POST   /api/v1/api-keys/{id}/rotate             (issue new secret)
//   PUT    /api/v1/api-keys/{id}                    (rename, disable, restrictions)
//   DELETE /api/v1/api-keys/{id}                    (delete)
//   GET    /api/v1/api-keys/usage/summary           (totals)
//   GET    /v1/models                               (bearer; the same shape OpenAI uses)
//   POST   /v1/chat/completions                     (bearer; OpenAI-compatible)
// In mock mode these hit mockBackend stubs that we'll add next to the page.

import { isMockMode } from './api';

const API_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';
const V1_BASE_URL =
  process.env.NEXT_PUBLIC_V1_URL || 'http://localhost:8000/v1';

function token(): string | null {
  if (typeof window === 'undefined') return null;
  return window.localStorage.getItem('token');
}

async function authed(path: string, init: RequestInit = {}) {
  const res = await fetch(`${API_URL}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token()}`,
      ...(init.headers || {}),
    },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

export interface ApiKey {
  id: number;
  key?: string; // only on creation
  name: string;
  description?: string | null;
  is_active: boolean;
  is_disabled: boolean;
  disable_reason?: string | null;
  expires_at?: string | null;
  last_used_at?: string | null;
  usage_count: number;
  tags?: string[] | null;
  organization?: string | null;
  ip_allowlist?: string[] | null;
  domain_allowlist?: string[] | null;
  monthly_token_limit?: number | null;
  monthly_request_limit?: number | null;
  monthly_token_count?: number;
  monthly_request_count?: number;
  monthly_cost_usd?: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface UsageSummary {
  total_requests: number;
  today_requests: number;
  month_requests: number;
  total_tokens_used: number;
  today_tokens_used: number;
  month_tokens_used: number;
  average_response_time_ms: number;
  top_endpoints: Array<{ endpoint: string; count: number }>;
}

export interface ModelInfo {
  id: string;
  object?: string;
  source: 'local' | 'ollama';
  created?: number | null;
}

// ------- API key CRUD -------

export async function listApiKeys(): Promise<ApiKey[]> {
  if (isMockMode) return [];
  return authed('/api-keys/');
}

export async function createApiKey(input: {
  name: string;
  description?: string;
  tags?: string[];
  organization?: string;
  monthly_token_limit?: number;
  monthly_request_limit?: number;
}): Promise<ApiKey> {
  if (isMockMode) {
    return {
      id: Math.floor(Math.random() * 1e9),
      key: 'nm_mock_' + Math.random().toString(36).slice(2),
      name: input.name,
      is_active: true,
      is_disabled: false,
      usage_count: 0,
      tags: input.tags || [],
      created_at: new Date().toISOString(),
    };
  }
  return authed('/api-keys/', { method: 'POST', body: JSON.stringify(input) });
}

export async function rotateApiKey(id: number): Promise<ApiKey> {
  if (isMockMode) {
    return {
      id,
      key: 'nm_mock_rotated_' + Math.random().toString(36).slice(2),
      name: 'rotated',
      is_active: true,
      is_disabled: false,
      usage_count: 0,
      created_at: new Date().toISOString(),
    };
  }
  return authed(`/api-keys/${id}/rotate`, { method: 'POST' });
}

export async function updateApiKey(
  id: number,
  patch: Partial<ApiKey>,
): Promise<ApiKey> {
  if (isMockMode) return { id, ...patch } as ApiKey;
  return authed(`/api-keys/${id}`, {
    method: 'PUT',
    body: JSON.stringify(patch),
  });
}

export async function deleteApiKey(id: number): Promise<void> {
  if (isMockMode) return;
  await authed(`/api-keys/${id}`, { method: 'DELETE' });
}

// ------- usage + models -------

export async function getUsageSummary(): Promise<UsageSummary | null> {
  if (isMockMode) return null;
  return authed('/api-keys/usage/summary');
}

export async function listModels(apiKey: string): Promise<ModelInfo[]> {
  if (isMockMode) return [{ id: 'NovaMind-local-v1', source: 'local' }];
  const res = await fetch(`${V1_BASE_URL}/models`, {
    headers: { Authorization: `Bearer ${apiKey}` },
  });
  if (!res.ok) throw new Error(await res.text());
  const data = await res.json();
  return data.data || [];
}

export async function sendChat(
  apiKey: string,
  body: { model: string; messages: { role: string; content: string }[]; max_tokens?: number; temperature?: number; stream?: boolean },
): Promise<any> {
  if (isMockMode) {
    return {
      id: 'chatcmpl-mock',
      model: body.model,
      choices: [{ message: { role: 'assistant', content: '(mock) echo: ' + body.messages.map(m => m.content).join(' ') } }],
      usage: { completion_tokens: 7, total_tokens: 7 },
    };
  }
  const res = await fetch(`${V1_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}