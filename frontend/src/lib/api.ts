/** Client for the Avatar backend. All URLs are relative (same-origin). */

import type {
  ChatEvent,
  Config,
  ConversationSummary,
  ConversationThread,
  FaqInput,
  FaqItem,
  Instructions,
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
    const message =
      res.status === 429
        ? "you're sending messages too quickly — please wait a moment and try again."
        : `${res.status} ${res.statusText}`;
    handlers.onError?.(message);
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

// ---- Archive ----

async function postOk(url: string): Promise<void> {
  const res = await fetch(url, { method: "POST", credentials: "same-origin" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}

export function listArchive(): Promise<ConversationSummary[]> {
  return fetch("/admin/archive", adminInit).then((r) => json<ConversationSummary[]>(r));
}

export function getArchivedConversation(id: string): Promise<ConversationThread> {
  return fetch(`/admin/archive/${id}`, adminInit).then((r) => json<ConversationThread>(r));
}

export function archiveConversation(id: string): Promise<void> {
  return postOk(`/admin/conversations/${id}/archive`);
}

export function restoreConversation(id: string): Promise<void> {
  return postOk(`/admin/archive/${id}/restore`);
}

export function archiveInactive(): Promise<{ conversations: number; messages: number }> {
  return fetch("/admin/archive-inactive", { method: "POST", credentials: "same-origin" }).then((r) =>
    json<{ conversations: number; messages: number }>(r),
  );
}

// ---- Export (download jsonl) ----

/** Fetch a jsonl export and save it, honouring the server's Content-Disposition filename. */
async function downloadJsonl(url: string, fallback: string): Promise<void> {
  const res = await fetch(url, adminInit);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  const disposition = res.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^"]+)"?/);
  const filename = match ? match[1] : fallback;
  const blob = await res.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
}

export function downloadConversations(): Promise<void> {
  return downloadJsonl("/admin/export/conversations", "conversations.jsonl");
}

export function downloadArchive(): Promise<void> {
  return downloadJsonl("/admin/export/archive", "archive.jsonl");
}

export function getInstructions(): Promise<Instructions> {
  return fetch("/admin/instructions", adminInit).then((r) => json<Instructions>(r));
}

export function saveInstructions(instructions: string): Promise<Instructions> {
  return fetch("/admin/instructions", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify({ instructions }),
  }).then((r) => json<Instructions>(r));
}

export function listFaqs(): Promise<FaqItem[]> {
  return fetch("/admin/faq", adminInit).then((r) => json<FaqItem[]>(r));
}

export function createFaq(body: FaqInput): Promise<FaqItem> {
  return fetch("/admin/faq", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  }).then((r) => json<FaqItem>(r));
}

export function updateFaq(id: number, body: FaqInput): Promise<FaqItem> {
  return fetch(`/admin/faq/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    credentials: "same-origin",
    body: JSON.stringify(body),
  }).then((r) => json<FaqItem>(r));
}

export async function deleteFaq(id: number): Promise<void> {
  const res = await fetch(`/admin/faq/${id}`, { method: "DELETE", credentials: "same-origin" });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
}
