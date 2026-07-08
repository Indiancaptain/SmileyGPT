/**
 * Thin fetch wrapper around the FastAPI backend. Routed through Next's
 * rewrite (/api/backend/*) in the browser so the real backend origin
 * never needs to be exposed to client-side code.
 */
const BASE = "/api/backend";

function authHeaders(): HeadersInit {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(body.detail || "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export const api = {
  async register(email: string, password: string, display_name?: string) {
    const res = await fetch(`${BASE}/v1/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password, display_name }),
    });
    return handle<{ access_token: string; refresh_token: string }>(res);
  },

  async login(email: string, password: string) {
    const res = await fetch(`${BASE}/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    return handle<{ access_token: string; refresh_token: string }>(res);
  },

  async logout() {
    const refreshToken = typeof window !== "undefined" ? localStorage.getItem("refresh_token") : null;
    const res = await fetch(`${BASE}/v1/auth/logout`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return handle<void>(res);
  },

  async me() {
    const res = await fetch(`${BASE}/v1/users/me`, { headers: authHeaders() });
    return handle<any>(res);
  },

  async listConversations(q?: string) {
    const qs = q ? `?q=${encodeURIComponent(q)}` : "";
    const res = await fetch(`${BASE}/v1/conversations${qs}`, { headers: authHeaders() });
    return handle<any[]>(res);
  },

  async createConversation(title?: string) {
    const res = await fetch(`${BASE}/v1/conversations`, {
      method: "POST",
      headers: { "Content-Type": "application/json", ...authHeaders() },
      body: JSON.stringify({ title }),
    });
    return handle<any>(res);
  },

  async getMessages(conversationId: string) {
    const res = await fetch(`${BASE}/v1/conversations/${conversationId}/messages`, { headers: authHeaders() });
    return handle<any[]>(res);
  },

  async deleteConversation(conversationId: string) {
    const res = await fetch(`${BASE}/v1/conversations/${conversationId}`, {
      method: "DELETE",
      headers: authHeaders(),
    });
    return handle<void>(res);
  },

  async uploadFile(file: File) {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/v1/files/upload`, {
      method: "POST",
      headers: authHeaders(),
      body: form,
    });
    return handle<any>(res);
  },

  streamChatUrl() {
    return `${BASE}/v1/chat/stream`;
  },

  authHeaders,
};
