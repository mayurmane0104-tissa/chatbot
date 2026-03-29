/**
 * src/lib/api.ts
 * Full API client connected to TissaTech FastAPI backend.
 * Handles JWT auth, token refresh, and all endpoints.
 */

const DEFAULT_API_URL = 'http://localhost:8000';

function getApiUrl(): string {
  const envUrl = process.env.NEXT_PUBLIC_API_URL ?? '';

  if (typeof window === 'undefined') {
    return (envUrl || DEFAULT_API_URL).replace(/\/+$/, '');
  }

  const params = new URLSearchParams(window.location.search);
  const queryUrl = params.get('apiBase') ?? '';
  const globalUrl = (window as Window & { __TISSA_API_URL?: string }).__TISSA_API_URL ?? '';
  const storedUrl = localStorage.getItem('tisaa_api_url') ?? '';

  const resolved = queryUrl || globalUrl || storedUrl || envUrl || DEFAULT_API_URL;

  if (queryUrl) {
    localStorage.setItem('tisaa_api_url', queryUrl);
    (window as Window & { __TISSA_API_URL?: string }).__TISSA_API_URL = queryUrl;
  }

  return resolved.replace(/\/+$/, '');
}

// ── Token management ────────────────────────────────────────────────────────
export function getAccessToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('tt_access_token');
}
export function getRefreshToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('tt_refresh_token');
}
export function setTokens(access: string, refresh: string) {
  localStorage.setItem('tt_access_token', access);
  localStorage.setItem('tt_refresh_token', refresh);
}
export function clearTokens() {
  localStorage.removeItem('tt_access_token');
  localStorage.removeItem('tt_refresh_token');
  localStorage.removeItem('tt_user');
}

// ── Base fetch ───────────────────────────────────────────────────────────────
export class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function apiFetch<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;

  let res = await fetch(`${getApiUrl()}${path}`, { ...options, headers });

  // Auto-refresh on 401
  if (res.status === 401) {
    const refreshed = await tryRefresh();
    if (refreshed) {
      headers['Authorization'] = `Bearer ${getAccessToken()}`;
      res = await fetch(`${getApiUrl()}${path}`, { ...options, headers });
    } else {
      clearTokens();
      if (typeof window !== 'undefined') window.location.href = '/login';
      throw new ApiError(401, 'Session expired');
    }
  }

  if (!res.ok) {
    let detail = 'Unknown error';
    try { detail = (await res.json()).detail ?? detail; } catch {}
    throw new ApiError(res.status, detail);
  }

  if (res.status === 204) return undefined as T;
  return res.json();
}

async function tryRefresh(): Promise<boolean> {
  const rt = getRefreshToken();
  if (!rt) return false;
  try {
    const res = await fetch(`${getApiUrl()}/api/v1/auth/refresh?refresh_token=${encodeURIComponent(rt)}`, { method: 'POST' });
    if (!res.ok) return false;
    const data = await res.json();
    setTokens(data.access_token, data.refresh_token);
    return true;
  } catch { return false; }
}

// ── Types ────────────────────────────────────────────────────────────────────
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  workspace_id: string;
}

export interface Analytics {
  total_conversations: number;
  total_messages: number;
  satisfaction_rate: number | null;
  avg_latency_ms: number;
  thumbs_up: number;
  thumbs_down: number;
  period_days: number;
  kb_status: string;
  kb_trained_url: string | null;
}

export interface Conversation {
  id: string;
  title: string | null;
  status: string;
  message_count: number;
  channel: string;
  created_at: string;
  updated_at?: string;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  created_at: string;
}

export interface RoleSuggestionsResponse {
  role: string;
  suggestions: string[];
}

export interface WidgetConfig {
  id?: string;
  bot_name: string;
  greeting_message: string;
  primary_color: string;
  secondary_color: string;
  placeholder_text: string;
  avatar_url?: string;
  position: string;
}

export interface Document {
  id: string;
  title: string;
  file_name?: string;
  file_size?: number;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface CrawlStatus {
  task_id: string;
  celery_state: string;
  celery_error: string | null;
  kb_status: string;
  kb_error: string | null;
  kb_trained_url: string | null;
  bedrock_kb_id: string | null;
  bedrock_agent_id: string | null;
  bedrock_agent_alias_id: string | null;
}

// ── Auth API ─────────────────────────────────────────────────────────────────
export const authApi = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const body = new URLSearchParams({ username: email, password });
    const res = await fetch(`${getApiUrl()}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Login failed' }));
      throw new ApiError(res.status, err.detail);
    }
    return res.json();
  },

  async register(data: {
    email: string;
    password: string;
    full_name: string;
    workspace_slug: string;
    company_name?: string;
  }): Promise<TokenResponse> {
    return apiFetch('/api/v1/auth/register', { method: 'POST', body: JSON.stringify(data) });
  },

  async me(): Promise<User> {
    return apiFetch('/api/v1/auth/me');
  },

  async logout(): Promise<void> {
    const rt = getRefreshToken();
    if (rt) {
      await apiFetch(`/api/v1/auth/logout?refresh_token=${encodeURIComponent(rt)}`, { method: 'POST' }).catch(() => {});
    }
    clearTokens();
  },
};

// ── Admin API ────────────────────────────────────────────────────────────────
export const adminApi = {
  getAnalytics: (days = 30): Promise<Analytics> =>
    apiFetch(`/api/v1/admin/analytics/overview?days=${days}`),

  getConversations: (page = 1): Promise<Conversation[]> =>
    apiFetch(`/api/v1/admin/conversations?page=${page}&page_size=50`),

  getDocuments: (): Promise<Document[]> =>
    apiFetch('/api/v1/admin/documents'),

  uploadDocument: async (file: File, title: string): Promise<Document> => {
    const form = new FormData();
    form.append('file', file);
    form.append('title', title || file.name);
    const token = getAccessToken();
    const res = await fetch(`${getApiUrl()}/api/v1/admin/documents`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: form,
    });
    if (!res.ok) throw new ApiError(res.status, 'Upload failed');
    return res.json();
  },

  deleteDocument: (id: string): Promise<void> =>
    apiFetch(`/api/v1/admin/documents/${id}`, { method: 'DELETE' }),

  /**
   * Trigger the crawl-and-train pipeline for the current workspace.
   * Returns { task_id, status, url, max_pages }
   */
  triggerCrawl: (url: string, maxPages = 100) =>
    apiFetch('/api/v1/admin/crawl', {
      method: 'POST',
      body: JSON.stringify({ url, max_pages: maxPages }),
    }),

  /**
   * Poll crawl + KB training progress.
   * Call every 3-5 seconds after triggerCrawl().
   */
  getCrawlStatus: (taskId: string): Promise<CrawlStatus> =>
    apiFetch(`/api/v1/admin/crawl-status/${taskId}`),

  /**
   * Get current workspace Bedrock settings (KB status, agent IDs, etc.)
   */
  getWorkspaceSettings: () =>
    apiFetch('/api/v1/admin/workspace-settings'),
};

// ── Widget Config API ─────────────────────────────────────────────────────────
export const widgetApi = {
  getConfig: (): Promise<WidgetConfig> =>
    apiFetch('/api/v1/widget/config'),

  saveConfig: (config: Partial<WidgetConfig>): Promise<WidgetConfig> =>
    apiFetch('/api/v1/admin/widget-config', { method: 'POST', body: JSON.stringify(config) }),

  // Generates a RAW widget API key (not hashed). The raw key must be embedded
  // in `data-bot-id` and sent back as `X-API-Key` by the widget frontend.
  createApiKey: (): Promise<{ api_key: string; prefix: string }> =>
    apiFetch('/api/v1/admin/widget-api-key', { method: 'POST' }),

  getPublicConfig: async (apiKey?: string): Promise<WidgetConfig> => {
    const headers: Record<string, string> = {};
    if (apiKey) headers['X-API-Key'] = apiKey;
    const res = await fetch(`${getApiUrl()}/api/v1/widget/config`, { headers });
    if (!res.ok) return {
      bot_name: 'Tissa', greeting_message: 'Hi! How can I help you today?',
      primary_color: '#E65C5C', secondary_color: '#c0392b',
      placeholder_text: 'Type a message...', position: 'bottom-right',
    };
    return res.json();
  },
};

// ── Chat API ──────────────────────────────────────────────────────────────────
export const chatApi = {
  getConversations: (): Promise<Conversation[]> =>
    apiFetch('/api/v1/chat/conversations'),

  getMessages: (conversationId: string): Promise<ChatMessage[]> =>
    apiFetch(`/api/v1/chat/conversations/${conversationId}/messages`),

  submitFeedback: (messageId: string, type: 'thumbs_up' | 'thumbs_down') =>
    apiFetch(`/api/v1/chat/messages/${messageId}/feedback`, {
      method: 'POST',
      body: JSON.stringify({ feedback_type: type }),
    }),

  getRoleSuggestions: async (
    role: string,
    widgetApiKey?: string,
    limit = 5,
  ): Promise<RoleSuggestionsResponse> => {
    const params = new URLSearchParams({ role, limit: String(limit) });
    const token = getAccessToken();
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers.Authorization = `Bearer ${token}`;
    if (widgetApiKey) headers['X-API-Key'] = widgetApiKey;

    const res = await fetch(`${getApiUrl()}/api/v1/chat/suggestions?${params.toString()}`, {
      method: 'GET',
      headers,
    });
    if (!res.ok) {
      return { role: role.toLowerCase(), suggestions: [] };
    }
    return res.json();
  },
};

// ── SSE Chat Streaming ────────────────────────────────────────────────────────
export interface StreamChunk {
  content?: string;
  conversation_id?: string;
  message_id?: string;
  tokens_used?: number;
  latency_ms?: number;
  error?: string;
}

export async function* streamChatMessage(
  message: string,
  conversationId?: string | null,
  sessionId?: string,
  userProfile?: Record<string, string>,
  widgetApiKey?: string,
): AsyncGenerator<StreamChunk> {
  const token = getAccessToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    Accept: 'text/event-stream',
  };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  if (widgetApiKey) headers['X-API-Key'] = widgetApiKey;

  const body: Record<string, unknown> = { message, session_id: sessionId };
  if (conversationId) body.conversation_id = conversationId;
  if (userProfile) body.user_profile = userProfile;

  const res = await fetch(`${getApiUrl()}/api/v1/chat/message`, {
    method: 'POST', headers, body: JSON.stringify(body),
  });

  if (!res.ok || !res.body) {
    yield { error: `HTTP ${res.status}` };
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const lines = buffer.split('\n');
    buffer = lines.pop() ?? '';
    for (const line of lines) {
      if (!line.startsWith('data: ')) continue;
      try { yield JSON.parse(line.slice(6)); } catch {}
    }
  }
}
