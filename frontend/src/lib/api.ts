/** Client for the Avatar backend. All URLs are relative (same-origin). */

import type {
  ChatEvent,
  Config,
  ConversationSummary,
  ConversationThread,
  Message,
} from "./types.ts";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json() as Promise<T>;
}

// ---- Public ----

export function getConfig(): Promise<Config> {
  return fetch("/api/config").then((r) => json<Config>(r));
}

export function getConversation(id: string, after?: number): Promise<ConversationThread> {
  const qs = after !== undefined ? `?after=${after}` : "";
  return fetch(`/api/conversations/${id}${qs}`).then((r) => json<ConversationThread>(r));
}

export interface ChatBody {
  conversation_id: string;
  message: string;
  visitor_name?: string;
}

export interface StreamHandlers {
  onTool?: (tool: string) => void;
  onToken?: (text: string) => void;
  onInstant?: (faq: number) => void;
  onDone?: (messageId: number, needsAttention: boolean) => void;
  onError?: (message: string) => void;
}

/** Dispatch a single parsed wire event to the matching handler. */
function dispatch(event: ChatEvent, h: StreamHandlers): void {
  switch (event.type) {
    case "tool":
      h.onTool?.(event.tool);
      break;
    case "token":
      h.onToken?.(event.text);
      break;
    case "instant":
      h.onInstant?.(event.faq);
      break;
    case "done":
      h.onDone?.(event.message_id, event.needs_attention);
      break;
    case "error":
      h.onError?.(event.message);
      break;
  }
}

/** POST a chat message and parse the SSE response manually (EventSource is GET-only). */
export async function streamChat(body: ChatBody, handlers: StreamHandlers): Promise<void> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok || !res.body) {
    handlers.onError?.(`${res.status} ${res.statusText}`);
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("");
      if (!data) continue; // keepalive comments (":...") and blank frames
      dispatch(JSON.parse(data) as ChatEvent, handlers);
    }
  }
}

// ---- Admin (cookie-authenticated) ----

const adminInit: RequestInit = { credentials: "same-origin" };

/** Log in with the admin password. Throws on 401. */
export async function login(password: string): Promise<void> {
  const res = await fetch("/admin/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ password }),
  });
  if (!res.ok) throw new Error("invalid password");
}

export async function logout(): Promise<void> {
  await fetch("/admin/logout", { method: "POST", credentials: "same-origin" });
}

/** True if the current session cookie is valid. */
export async function me(): Promise<boolean> {
  const res = await fetch("/admin/me", adminInit);
  return res.ok;
}

export function listConversations(): Promise<ConversationSummary[]> {
  return fetch("/admin/conversations", adminInit).then((r) => json<ConversationSummary[]>(r));
}

export function getConversationAdmin(id: string): Promise<ConversationThread> {
  return fetch(`/admin/conversations/${id}`, adminInit).then((r) => json<ConversationThread>(r));
}

export function postHumanMessage(id: string, content: string): Promise<Message> {
  return fetch(`/admin/conversations/${id}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ content }),
  }).then((r) => json<Message>(r));
}

export async function resolveConversation(id: string): Promise<void> {
  await fetch(`/admin/conversations/${id}/resolve`, {
    method: "POST",
    credentials: "same-origin",
  });
}
