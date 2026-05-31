/** Admin dashboard: login gate, inbox triage, three-way thread view, human replies. */

import "../styles/tokens.css";
import "../styles/components.css";
import "../styles/admin.css";

import {
  getConfig,
  getConversationAdmin,
  listConversations,
  login,
  me,
  postHumanMessage,
  resolveConversation,
} from "../lib/api.ts";
import type { ConversationSummary, ConversationThread, Message } from "../lib/types.ts";
import { initTheme, wireThemeToggle } from "../lib/theme.ts";
import { renderMarkdown } from "../lib/markdown.ts";
import { escapeHtml, icon } from "../lib/dom.ts";
import { formatShort, formatTime } from "../lib/time.ts";

const POLL_MS = 10_000;

/** Tool-status labels keyed by stored tool name (owner injected at render time). */
function toolLabel(tool: string, owner: string): { icon: string; text: string } {
  if (tool === "faq_tool") return { icon: "check", text: "faq_tool · looked up the FAQ" };
  if (tool === "push_tool") return { icon: "mail", text: `push_tool · notified ${owner}` };
  if (tool === "instant") return { icon: "check", text: "instant answer" };
  return { icon: "tool", text: tool };
}

/** Derive up to two uppercase initials from a free-text name. */
function initialsOf(name: string | null): string {
  const trimmed = (name ?? "").trim();
  if (!trimmed) return "??";
  const parts = trimmed.split(/\s+/);
  const letters = parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0];
  return letters.toUpperCase();
}

/** Display name for a conversation, falling back to "Anonymous". */
function displayName(name: string | null): string {
  return (name ?? "").trim() || "Anonymous";
}

/** Short id token, e.g. conv_b3f2a9. */
function shortId(conversationId: string): string {
  return `conv_${conversationId.replace(/-/g, "").slice(0, 6)}`;
}

const state = {
  owner: "the owner",
  conversations: [] as ConversationSummary[],
  activeId: null as string | null,
  thread: null as ConversationThread | null,
};

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

function showDashboard(): void {
  $("loginGate").hidden = true;
  $("dashboard").hidden = false;
}

// ---- Login gate ----

function wireLogin(): void {
  const gate = $("loginGate");
  const form = $<HTMLFormElement>("loginForm");
  const password = $<HTMLInputElement>("loginPassword");
  const error = $("loginError");
  const submit = $<HTMLButtonElement>("loginSubmit");

  gate.hidden = false;
  password.focus();

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    error.hidden = true;
    submit.disabled = true;
    try {
      await login(password.value);
      showDashboard();
      await startDashboard();
    } catch {
      error.hidden = false;
      password.select();
    } finally {
      submit.disabled = false;
    }
  });
}

// ---- Inbox ----

function renderInbox(): void {
  const list = $("convoList");
  $("convoCount").textContent = String(state.conversations.length);
  list.replaceChildren();

  for (const convo of state.conversations) {
    const row = document.createElement("div");
    row.className = "convo-item";
    row.dataset.id = convo.conversation_id;
    if (convo.conversation_id === state.activeId) row.classList.add("is-active");
    if (convo.unread) row.classList.add("is-unread");
    if (convo.needs_attention) row.classList.add("is-attention");

    const side = convo.needs_attention
      ? `<span class="badge badge--attention">${icon("spark", "icon")} Needs you</span>`
      : convo.unread
        ? `<span class="badge badge--dot"></span>`
        : `<svg class="icon icon--sm" style="color:var(--positive)"><use href="/icons.svg#i-check2"/></svg>`;

    row.innerHTML = `
      <span class="avatar-initials">${escapeHtml(initialsOf(convo.conversation_name))}</span>
      <div class="convo-main">
        <div class="convo-top"><span class="convo-name">${escapeHtml(displayName(convo.conversation_name))}</span></div>
        <div class="convo-preview">${escapeHtml(convo.preview)}</div>
      </div>
      <div class="convo-side">
        <span class="msg-time">${escapeHtml(formatShort(convo.last_created_at))}</span>
        ${side}
      </div>`;

    row.addEventListener("click", () => void selectConversation(convo.conversation_id));
    list.append(row);
  }
}

// ---- Thread view ----

function bubbleHtml(content: string): string {
  return `<div class="bubble">${renderMarkdown(content)}</div>`;
}

function toolStatusHtml(message: Message): string {
  if (!message.tool_calls) return "";
  return message.tool_calls
    .map((call) => {
      const name = (call as { tool?: string; type?: string }).tool ?? (call as { type?: string }).type ?? "";
      if (!name) return "";
      const label = toolLabel(name, state.owner);
      return `<div class="tool-status is-done">${icon(label.icon, "icon")} ${escapeHtml(label.text)}</div>`;
    })
    .join("");
}

function messageEl(message: Message): HTMLElement {
  const wrap = document.createElement("div");
  const time = formatTime(message.created_at);

  if (message.role === "visitor") {
    wrap.className = "msg msg--visitor";
    wrap.innerHTML = `
      <span class="avatar-initials">${escapeHtml(initialsOf(message.conversation_name))}</span>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-time">${escapeHtml(time)}</span></div>
        <div class="bubble"><p>${escapeHtml(message.content)}</p></div>
      </div>`;
  } else if (message.role === "avatar") {
    wrap.className = "msg msg--avatar";
    wrap.innerHTML = `
      <div class="avatar avatar-twin" style="background-image:url('/avatar-robot-round.png')"></div>
      <div class="msg-body">
        <div class="msg-meta"><span class="msg-name">Avatar</span><span class="msg-time">${escapeHtml(time)}</span></div>
        ${toolStatusHtml(message)}
        ${bubbleHtml(message.content)}
      </div>`;
  } else {
    wrap.className = "msg msg--human";
    wrap.innerHTML = `
      <div class="avatar avatar-human" style="background-image:url('/avatar-human.png')">
        <span class="spark-badge">${icon("spark", "icon")}</span>
      </div>
      <div class="msg-body">
        <div class="msg-meta">
          <span class="human-tag">${icon("live", "icon")} You · sent to visitor</span>
          <span class="msg-time">${escapeHtml(time)}</span>
        </div>
        ${bubbleHtml(message.content)}
      </div>`;
  }
  return wrap;
}

function renderThread(): void {
  const thread = state.thread;
  if (!thread) return;

  $("threadEmpty").hidden = true;
  $("threadView").hidden = false;

  const name = displayName(thread.conversation_name);
  $("threadInitials").textContent = initialsOf(thread.conversation_name);
  $("threadName").textContent = name;

  const first = thread.messages[0];
  const started = first ? formatTime(first.created_at) : "";
  const count = thread.messages.length;
  $("threadSub").textContent = `${shortId(thread.conversation_id)} · started ${started} · ${count} message${count === 1 ? "" : "s"}`;

  const attention = thread.messages.some((m) => m.needs_attention);
  $("attnFlag").hidden = !attention;
  $("postingAsName").textContent = state.owner;

  const inner = $("threadInner");
  inner.replaceChildren();
  for (const message of thread.messages) inner.append(messageEl(message));
  scrollThreadToLatest();

  const composer = $<HTMLTextAreaElement>("adminComposerInput");
  composer.placeholder = `Write a message to ${name === "Anonymous" ? "the visitor" : name}…`;
  composer.focus({ preventScroll: true });
}

function scrollThreadToLatest(): void {
  const thread = $("thread");
  thread.scrollTop = thread.scrollHeight;
}

/** Load a conversation (clears unread + attention server-side) and render it. */
async function selectConversation(id: string): Promise<void> {
  state.activeId = id;
  state.thread = await getConversationAdmin(id);
  const local = state.conversations.find((c) => c.conversation_id === id);
  if (local) {
    local.unread = false;
    local.needs_attention = false;
  }
  renderInbox();
  renderThread();
}

// ---- Arrow-key navigation ----

function moveSelection(delta: number): void {
  if (!state.conversations.length) return;
  const index = state.conversations.findIndex((c) => c.conversation_id === state.activeId);
  const next = index === -1 ? 0 : Math.min(state.conversations.length - 1, Math.max(0, index + delta));
  void selectConversation(state.conversations[next].conversation_id);
}

function wireArrowKeys(): void {
  document.addEventListener("keydown", (e) => {
    const target = e.target as HTMLElement;
    if (target instanceof HTMLTextAreaElement || target instanceof HTMLInputElement) return;
    if (e.key === "ArrowDown") {
      e.preventDefault();
      moveSelection(1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      moveSelection(-1);
    }
  });
}

// ---- Composer (human reply) ----

function wireComposer(): void {
  const input = $<HTMLTextAreaElement>("adminComposerInput");
  const send = $<HTMLButtonElement>("adminSendBtn");

  const submit = async () => {
    const content = input.value.trim();
    if (!content || !state.activeId) return;
    const id = state.activeId;
    input.value = "";
    const created = await postHumanMessage(id, content);
    if (state.thread && state.thread.conversation_id === id) {
      state.thread.messages.push(created);
      $("threadInner").append(messageEl(created));
      scrollThreadToLatest();
    }
    input.focus({ preventScroll: true });
  };

  send.addEventListener("click", () => void submit());
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      void submit();
    }
  });
}

function wireResolve(): void {
  $("resolveBtn").addEventListener("click", async () => {
    if (!state.activeId) return;
    const id = state.activeId;
    await resolveConversation(id);
    $("attnFlag").hidden = true;
    const local = state.conversations.find((c) => c.conversation_id === id);
    if (local) local.needs_attention = false;
    renderInbox();
  });
}

// ---- Polling ----

async function refresh(): Promise<void> {
  state.conversations = await listConversations();
  renderInbox();
  if (state.activeId) {
    const summary = state.conversations.find((c) => c.conversation_id === state.activeId);
    if (summary && (!state.thread || summary.last_id !== state.thread.messages.at(-1)?.id)) {
      state.thread = await getConversationAdmin(state.activeId);
      summary.unread = false;
      summary.needs_attention = false;
      renderInbox();
      renderThread();
    }
  }
}

function startPolling(): void {
  setInterval(() => void refresh().catch(() => {}), POLL_MS);
}

// ---- Boot ----

async function startDashboard(): Promise<void> {
  const config = await getConfig();
  state.owner = config.owner_name;
  $("ownerName").textContent = config.owner_name;
  $("postingAsName").textContent = config.owner_name;

  wireComposer();
  wireResolve();
  wireArrowKeys();

  state.conversations = await listConversations();
  renderInbox();
  if (state.conversations.length) await selectConversation(state.conversations[0].conversation_id);
  startPolling();
}

async function main(): Promise<void> {
  initTheme();
  wireThemeToggle($("themeToggle"));

  if (await me()) {
    showDashboard();
    await startDashboard();
  } else {
    wireLogin();
  }
}

void main();
