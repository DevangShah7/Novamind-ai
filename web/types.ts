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
  meta_data: {
    model?: string;
    tokens?: number;
    [key: string]: any;
  };
  created_at: string;
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