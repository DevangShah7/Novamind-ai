export interface User {
  id: number;
  email: string | null;
  username: string | null;
  full_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  /**
   * Whether this account has admin privileges. Backend returns this
   * on the User schema (and on /users/me via the same User model).
   * Used by the admin panel for the "is_admin" toggle and to gate
   * admin-only routes in the AppShell.
   */
  is_admin?: boolean;
  google_id: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
}

/**
 * Result of a successful `register()` call. The backend now mints a
 * verification email instead of an immediate access token, so the
 * client UI shows a "check your inbox" screen and waits for the user
 * to click the link. The discriminator is the call shape, not the
 * type — a future "auto-verify in dev" path could return a Token
 * instead; for now this is the only branch.
 */
export type RegisterResult =
  | { requiresVerification: true; email: string }
  | { access_token: string; token_type: string };

export interface Chat {
  id: number;
  title: string;
  user_id: number;
  chat_type: string;
  status: string;
  settings: any;
  tags: string[] | null;
  created_at: string;
  updated_at: string;
  last_message_at: string | null;
  messages?: Message[];
}

export interface Message {
  id: number;
  content: string;
  message_type: string; // text, image, code, file
  is_ai: boolean;
  chat_id: number;
  user_id: number | null;
  // The API serialises this as either an object or a JSON string depending
  // on the column path it took. Tolerate both.
  meta_data?: string | {
    model?: string;
    tokens?: number;
    [key: string]: any;
    } | null;
  created_at: string;
}

/** Coerce the heterogeneous meta_data field into a plain object (or null). */
export function asMeta(md: Message['meta_data']): Record<string, any> | null {
  if (md == null) return null;
  if (typeof md === 'string') {
    try { return JSON.parse(md); } catch { return null; }
  }
  return md as Record<string, any>;
}

export interface ApiKey {
  id: number;
  key: string;
  name: string;
  description: string | null;
  is_active: boolean;
  /** True when an admin or the owner has explicitly disabled the key.
   *  `is_active === false` covers both "disabled" and "expired/never-active";
   *  `is_disabled` is the explicit-disable signal. */
  is_disabled?: boolean;
  disable_reason?: string | null;
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  ip_allowlist?: string[] | null;
  domain_allowlist?: string[] | null;
  tags?: string[] | null;
  organization?: string | null;
  monthly_token_limit?: number | null;
  monthly_request_limit?: number | null;
  monthly_token_count?: number;
  monthly_request_count?: number;
  monthly_cost_usd?: number;
  created_at: string;
  updated_at: string;
}

export interface ApiKeyUsageSummary {
  total_requests: number;
  today_requests: number;
  month_requests: number;
  total_tokens_used: number;
  today_tokens_used: number;
  month_tokens_used: number;
  average_response_time_ms: number;
  top_endpoints?: { endpoint: string; count: number }[];
}

export interface ApiKeyUsagePoint {
  date: string;
  requests: number;
  tokens: number;
  cost_usd: number;
}

export interface ApiKeyUsageEvent {
  id: number;
  user_id: number;
  api_key_id: number;
  endpoint: string;
  method: string;
  status_code: number;
  ip_address: string | null;
  user_agent: string | null;
  response_time_ms: number | null;
  tokens_used: number | null;
  model_used: string | null;
  created_at: string;
}

export type ApiKeyUsage = ApiKeyUsageEvent[];