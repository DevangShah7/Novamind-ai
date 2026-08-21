export interface User {
  id: number;
  email: string | null;
  username: string | null;
  full_name: string | null;
  bio: string | null;
  avatar_url: string | null;
  is_active: boolean;
  is_verified: boolean;
  google_id: string | null;
}

export interface Token {
  access_token: string;
  token_type: string;
}

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
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  created_at: string;
  updated_at: string;
}