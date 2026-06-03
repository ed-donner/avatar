/** Visitor chat page: theme, config, conversation cookie, streaming chat, and
 *  polling for async human messages. See BUILD-SPEC 11 and ux-flows A-F. */

import "../styles/tokens.css";
import "../styles/components.css";
import "../styles/visitor.css";

import { getConfig, getConversation, streamChat } from "../lib/api.ts";
import type { Message } from "../lib/types.ts";
import { initTheme, wireThemeToggle } from "../lib/theme.ts";
import { renderMarkdown } from "../lib/markdown.ts";
import { el, escapeHtml, icon } from "../lib/dom.ts";
import { formatTime } from "../lib/time.ts";

// ---- Element handles ----

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

const brandSub = $<HTMLElement>("brandSub");
const nameField = $<HTMLInputElement>("nameField");
const keepChat = $<HTMLInputElement>("keepChat");
const resetBtn = $<HTMLButtonElement>("resetBtn");
const themeToggle = $<HTMLElement>("themeToggle");
const convo = $<HTMLElement>("convo");
const convoInner = $<HTMLElement>("convoInner");
const intro = $<HTMLElement>("intro");
const introHeading = $<HTMLElement>("introHeading");
const introBody = $<HTMLElement>("introBody");
const suggestRow = $<HTMLElement>("suggestRow");
const composerInput = $<HTMLTextAreaElement>("composerInput");
const sendBtn = $<HTMLButtonElement>("sendBtn");

// ---- State ----

let ownerName = "the owner";
let conversationId = "";
let lastSeenId = 0;
const renderedIds = new Set<number>();
let streaming = false;

// ---- Cookies ----

const CID_COOKIE = "avatar_cid";
const KEEP_COOKIE = "avatar_keep";
const YEAR = 60 * 60 * 24 * 365;

function setCookie(name: string, value: string, maxAge: number): void {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAge}; SameSite=Lax`;
}

function deleteCookie(name: string): void {
  document.cookie = `${name}=; path=/; max-age=0; SameSite=Lax`;
}

function getCookie(name: string): string | null {
  const match = document.cookie
    .split("; ")
    .find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.slice(name.length + 1)) : null;
}

// ---- Visitor identity ----

/** Derive an initials token from a free-text name. Falls back to "You" when no
 *  name is known (friendlier than a bare "?"). */
function initialsFrom(raw: string | null | undefined): string {
  const name = (raw ?? "").trim();
  if (!name) return "You";
  const parts = name.split(/\s+/).filter(Boolean);
  const letters = parts.length === 1 ? parts[0].slice(0, 2) : parts[0][0] + parts[parts.length - 1][0];
  return letters.toUpperCase();
}

function visitorName(): string | undefined {
  const name = nameField.value.trim();
  return name || undefined;
}

// ---- Rendering ----

function scrollToLatest(): void {
  convo.scrollTop = convo.scrollHeight;
}

function hideIntro(): void {
  intro.style.display = "none";
}

/** Append a visitor bubble (escaped plain text), recording any backing id. */
function renderVisitor(content: string, time: string, id?: number, name?: string | null): HTMLElement {
  const initials = name !== undefined ? initialsFrom(name) : initialsFrom(nameField.value);
  const initialsClass = initials === "You" ? "avatar-initials is-you" : "avatar-initials";
  const row = el("div", { class: "msg msg--visitor" }, [
    el("span", { class: initialsClass }, [initials]),
    el("div", { class: "msg-body", html:
      `<div class="msg-meta"><span class="msg-time">${escapeHtml(time)}</span></div>` +
      `<div class="bubble"><p>${escapeHtml(content)}</p></div>` }),
  ]);
  if (id !== undefined) row.dataset.id = String(id);
  convoInner.append(row);
  return row;
}

/** Create an empty avatar row; the bubble and tool-status are filled as events arrive. */
function createAvatarRow(time: string, id?: number): HTMLElement {
  const row = el("div", { class: "msg msg--avatar" }, [
    el("div", { class: "avatar avatar-twin", style: "background-image:url('/avatar-robot-round.png')" }),
    el("div", { class: "msg-body", html:
      `<div class="msg-meta"><span class="msg-name">Avatar</span><span class="msg-time">${escapeHtml(time)}</span></div>` +
      `<div class="bubble"></div>` }),
  ]);
  if (id !== undefined) row.dataset.id = String(id);
  convoInner.append(row);
  return row;
}

/** Render a fully-known avatar message from history or polling. */
function renderAvatar(msg: Message): void {
  const row = createAvatarRow(formatTime(msg.created_at), msg.id);
  const bubble = row.querySelector<HTMLElement>(".bubble")!;
  bubble.innerHTML = renderMarkdown(msg.content);
  if (Array.isArray(msg.tool_calls)) {
    for (const call of msg.tool_calls as Array<Record<string, unknown>>) {
      if (call.type === "instant") {
        insertInstantTag(row, Number(call.faq));
      } else {
        const name = call.tool ?? call.name;
        if (typeof name === "string") {
          addToolStatus(row, name, true);
        }
      }
    }
  }
}

/** Render the human's live message (photo, ring, spark badge, "{owner} · live"). */
function renderHuman(msg: Message): void {
  const row = el("div", { class: "msg msg--human" }, [
    el("div", { class: "avatar avatar-human", style: "background-image:url('/avatar-human.png')", html:
      `<span class="spark-badge">${icon("spark")}</span>` }),
    el("div", { class: "msg-body", html:
      `<div class="msg-meta">` +
      `<span class="human-tag">${icon("live")} ${escapeHtml(ownerName)} &middot; live</span>` +
      `<span class="msg-time">${escapeHtml(formatTime(msg.created_at))}</span></div>` +
      `<div class="bubble">${renderMarkdown(msg.content)}</div>` }),
  ]);
  row.dataset.id = String(msg.id);
  convoInner.append(row);
}

/** Render any message row by role (used for restore + polling). */
function renderMessage(msg: Message): void {
  if (renderedIds.has(msg.id)) return;
  renderedIds.add(msg.id);
  lastSeenId = Math.max(lastSeenId, msg.id);
  if (msg.role === "visitor") {
    renderVisitor(msg.content, formatTime(msg.created_at), msg.id, msg.conversation_name);
  } else if (msg.role === "avatar") {
    renderAvatar(msg);
  } else {
    renderHuman(msg);
  }
}

// ---- Tool status + instant tag ----

const TOOL_LABELS: Record<string, { text: () => string; icon: string }> = {
  faq_tool: { text: () => "Looked up the FAQ &middot; faq_tool", icon: "check" },
  push_tool: { text: () => `Notified ${escapeHtml(ownerName)} &middot; push_tool`, icon: "mail" },
};

/** Add (or finalise) a tool-status line above the avatar bubble. */
function addToolStatus(row: HTMLElement, tool: string, done: boolean): void {
  const label = TOOL_LABELS[tool] ?? { text: () => escapeHtml(tool), icon: "tool" };
  const body = row.querySelector(".msg-body")!;
  const bubble = row.querySelector(".bubble")!;
  const status = el("div", { class: done ? "tool-status is-done" : "tool-status", html:
    `${icon(done ? label.icon : "tool")} ${label.text()}` });
  body.insertBefore(status, bubble);
}

function insertInstantTag(row: HTMLElement, faq: number): void {
  const meta = row.querySelector(".msg-meta")!;
  const time = meta.querySelector(".msg-time");
  const tag = el("span", { class: "instant-tag" }, [`instant · Q${faq}`]);
  meta.insertBefore(tag, time);
}

// ---- Typing indicator ----

function showTyping(): HTMLElement {
  const node = el("div", { class: "typing", html:
    `<span class="dots"><span></span><span></span><span></span></span> Avatar is typing` });
  convoInner.append(node);
  scrollToLatest();
  return node;
}

// ---- Send ----

function send(): void {
  const text = composerInput.value.trim();
  if (!text || streaming) return;

  hideIntro();
  const now = new Date().toISOString();
  renderVisitor(text, formatTime(now));
  composerInput.value = "";
  resizeComposer();
  composerInput.focus();
  scrollToLatest();
  resetPolling();

  streaming = true;
  let typing: HTMLElement | null = showTyping();
  let avatarRow: HTMLElement | null = null;
  let accumulated = "";

  const ensureRow = (): HTMLElement => {
    if (typing) {
      typing.remove();
      typing = null;
    }
    if (!avatarRow) avatarRow = createAvatarRow(formatTime(new Date().toISOString()));
    return avatarRow;
  };

  void streamChat(
    { conversation_id: conversationId, message: text, visitor_name: visitorName() },
    {
      onTool: (tool) => {
        addToolStatus(ensureRow(), tool, true);
        scrollToLatest();
      },
      onInstant: (faq) => {
        insertInstantTag(ensureRow(), faq);
        scrollToLatest();
      },
      onToken: (token) => {
        const bubble = ensureRow().querySelector<HTMLElement>(".bubble")!;
        accumulated += token;
        bubble.innerHTML = renderMarkdown(accumulated);
        scrollToLatest();
      },
      onDone: (messageId) => {
        const row = ensureRow();
        row.dataset.id = String(messageId);
        renderedIds.add(messageId);
        lastSeenId = Math.max(lastSeenId, messageId);
        streaming = false;
        composerInput.focus();
        scrollToLatest();
      },
      onError: (message) => {
        if (typing) {
          typing.remove();
          typing = null;
        }
        const target = avatarRow ?? convoInner;
        const where = avatarRow ? target.querySelector(".msg-body")! : target;
        where.append(el("div", { class: "stream-error" }, [`Something went wrong: ${message}`]));
        streaming = false;
        composerInput.focus();
        scrollToLatest();
      },
    },
  );
}

// ---- Composer behaviour ----

function resizeComposer(): void {
  composerInput.style.height = "auto";
  composerInput.style.height = `${composerInput.scrollHeight}px`;
}

/** A short one-line placeholder on phones; the fuller hint on wider screens. */
const composerMq = window.matchMedia("(max-width: 640px)");
function applyPlaceholder(): void {
  composerInput.placeholder = composerMq.matches
    ? `Message ${ownerName}'s twin…`
    : `Message ${ownerName}'s twin…  (type "Q2" for an instant answer)`;
}
composerMq.addEventListener("change", applyPlaceholder);

composerInput.addEventListener("input", resizeComposer);

composerInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    send();
  }
});

sendBtn.addEventListener("click", send);

for (const chip of suggestRow.querySelectorAll<HTMLButtonElement>(".chip")) {
  chip.addEventListener("click", () => {
    composerInput.value = chip.textContent ?? "";
    send();
  });
}

// ---- Conversation id + keep-chat ----

function persistCid(): void {
  if (keepChat.checked) setCookie(CID_COOKIE, conversationId, YEAR);
}

function newConversation(): void {
  conversationId = crypto.randomUUID();
  lastSeenId = 0;
  renderedIds.clear();
  persistCid();
}

async function restore(): Promise<void> {
  const thread = await getConversation(conversationId);
  if (thread.messages.length) {
    hideIntro();
    for (const msg of thread.messages) renderMessage(msg);
    scrollToLatest();
  }
}

keepChat.addEventListener("change", () => {
  if (keepChat.checked) {
    setCookie(KEEP_COOKIE, "1", YEAR);
    persistCid();
  } else {
    deleteCookie(KEEP_COOKIE);
    deleteCookie(CID_COOKIE);
  }
});

resetBtn.addEventListener("click", () => {
  convoInner.querySelectorAll(".msg, .typing, .day-sep").forEach((node) => node.remove());
  intro.style.display = "";
  newConversation();
  composerInput.focus();
});

// ---- Polling for async human messages ----

// Poll cadence ladder: fast right after activity, easing as the chat goes quiet,
// to reduce server load. "Activity" = a message sent or a human message received.
const FAST = 10_000;
const POLL_TIERS = [
  { idleAfter: 60 * 60_000, delay: 5 * 60_000 }, // quiet 1h  -> every 5 min
  { idleAfter: 10 * 60_000, delay: 2 * 60_000 }, // quiet 10m -> every 2 min
  { idleAfter: 2 * 60_000, delay: 30_000 },      // quiet 2m  -> every 30 s
];

let pollTimer: number | undefined;
let lastActivity = Date.now();

/** Delay until the next poll, based on how long since the last activity. */
function pollDelay(): number {
  const idle = Date.now() - lastActivity;
  for (const tier of POLL_TIERS) {
    if (idle >= tier.idleAfter) return tier.delay;
  }
  return FAST;
}

function resetPolling(): void {
  lastActivity = Date.now();
  schedulePoll(FAST);
}

function schedulePoll(delay: number): void {
  if (pollTimer !== undefined) clearTimeout(pollTimer);
  pollTimer = window.setTimeout(poll, delay);
}

async function poll(): Promise<void> {
  if (!streaming) {
    try {
      const thread = await getConversation(conversationId, lastSeenId);
      if (thread.messages.length && !streaming) {
        hideIntro();
        for (const msg of thread.messages) renderMessage(msg);
        lastActivity = Date.now();
        scrollToLatest();
      }
    } catch {
      // transient network error; keep polling on the next tick.
    }
  }
  schedulePoll(pollDelay());
}

// ---- Boot ----

async function boot(): Promise<void> {
  initTheme();
  wireThemeToggle(themeToggle);

  if (getCookie(KEEP_COOKIE) === null) {
    keepChat.checked = true;
    setCookie(KEEP_COOKIE, "1", YEAR);
  } else {
    keepChat.checked = getCookie(KEEP_COOKIE) === "1";
  }

  const existing = keepChat.checked ? getCookie(CID_COOKIE) : null;
  if (existing) {
    conversationId = existing;
    persistCid();
  } else {
    newConversation();
  }

  composerInput.focus();

  try {
    const config = await getConfig();
    ownerName = config.owner_name;
    brandSub.textContent = `${ownerName} · digital twin`;
    document.title = `Avatar · ${ownerName}`;
    introHeading.innerHTML =
      `I'm ${escapeHtml(ownerName)}'s <em>digital twin</em>.<br>Ask me anything &mdash; the real ${escapeHtml(ownerName)} might just chime in.`;
    introBody.textContent =
      `I know ${ownerName}'s background, courses, and curriculum. I can also put you in touch directly.`;
    applyPlaceholder();
  } catch {
    // config is best-effort; the page still works with default copy.
  }

  if (existing) {
    try {
      await restore();
    } catch {
      // a stale/invalid cid restores as an empty thread; ignore.
    }
  }

  schedulePoll(FAST);

  // Deep links submit a message on arrival, then drop the param so a reload won't
  // resubmit. ?q=N sends "QN" (e.g. /?q=2 -> instant FAQ answer); ?m=... sends free
  // text (e.g. /?m=whats+the+price -> asks the avatar). A valid ?q wins over ?m.
  // Both ride the page's own URL, including when embedded in an iframe whose src
  // carries the query string.
  const params = new URLSearchParams(location.search);
  const qParam = params.get("q");
  const mParam = params.get("m");
  const qn = qParam ? qParam.replace(/^[qQ]/, "") : "";
  if (qParam && /^\d{1,2}$/.test(qn)) {
    history.replaceState(null, "", location.pathname);
    composerInput.value = `Q${qn}`;
    send();
  } else if (mParam && mParam.trim()) {
    history.replaceState(null, "", location.pathname);
    composerInput.value = mParam.trim();
    send();
  }
}

void boot();
