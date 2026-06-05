/** Admin dashboard: login gate, inbox triage, three-way thread view, human replies. */

import "../styles/tokens.css";
import "../styles/components.css";
import "../styles/admin.css";

import {
  archiveConversation,
  archiveInactive,
  createFaq,
  deleteFaq,
  downloadArchive,
  downloadConversations,
  getArchivedConversation,
  getConfig,
  getConversationAdmin,
  getInstructions,
  listArchive,
  listConversations,
  listFaqs,
  login,
  me,
  postHumanMessage,
  resolveConversation,
  restoreConversation,
  saveInstructions,
  updateFaq,
} from "../lib/api.ts";
import type { ConversationSummary, ConversationThread, FaqItem, Message } from "../lib/types.ts";
import { initTheme, wireThemeToggle } from "../lib/theme.ts";
import { renderMarkdown } from "../lib/markdown.ts";
import { escapeHtml, icon } from "../lib/dom.ts";
import { formatShort, formatTime } from "../lib/time.ts";

const POLL_MS = 10_000;

type Section = "conversations" | "archive" | "instructions" | "faq";
const SECTIONS: readonly Section[] = ["conversations", "archive", "instructions", "faq"];
const SECTION_KEY = "avatar-admin-section";

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
  section: "conversations" as Section,
  conversations: [] as ConversationSummary[],
  activeId: null as string | null,
  thread: null as ConversationThread | null,
  faqs: [] as FaqItem[],
  archive: [] as ConversationSummary[],
};

const $ = <T extends HTMLElement>(id: string): T => document.getElementById(id) as T;

/** Mobile shows one pane at a time (master/detail); desktop ignores data-view. */
const mobileMq = window.matchMedia("(max-width: 640px)");
function setView(view: "list" | "thread"): void {
  $("dashboard").dataset.view = view;
}

/** Switch the active dashboard section; show only its panel, persist the choice. */
function setSection(section: Section): void {
  state.section = section;
  localStorage.setItem(SECTION_KEY, section);
  for (const tab of document.querySelectorAll<HTMLElement>(".nav-tab")) {
    const active = tab.dataset.section === section;
    tab.classList.toggle("is-active", active);
    if (active) tab.setAttribute("aria-current", "page");
    else tab.removeAttribute("aria-current");
  }
  for (const panel of document.querySelectorAll<HTMLElement>(".sections .section")) {
    panel.hidden = panel.dataset.section !== section;
  }
  if (section === "instructions") void loadInstructions();
  if (section === "faq") void loadFaqs();
  if (section === "archive") void loadArchive();
}

function wireNav(): void {
  for (const tab of document.querySelectorAll<HTMLElement>(".nav-tab")) {
    tab.addEventListener("click", () => setSection(tab.dataset.section as Section));
  }
  const saved = localStorage.getItem(SECTION_KEY) as Section | null;
  setSection(saved && SECTIONS.includes(saved) ? saved : "conversations");
}

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
  // Switch to the thread pane BEFORE rendering: on mobile the pane is hidden
  // until now, and scroll-to-latest needs it visible to measure scrollHeight.
  setView("thread");
  renderThread();
}

// ---- Back to inbox (mobile master/detail) ----

function wireBack(): void {
  $("threadBack").addEventListener("click", () => setView("list"));
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
    if (state.section !== "conversations") return;
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

// ---- Instructions editor ----

// Last value known to be on the server; lets loadInstructions avoid clobbering
// unsaved edits (textarea differs from this) when the tab is re-opened.
let instructionsServerValue: string | null = null;

async function loadInstructions(): Promise<void> {
  const input = $<HTMLTextAreaElement>("instructionsInput");
  const status = $("instructionsStatus");
  try {
    const { instructions } = await getInstructions();
    const dirty = instructionsServerValue !== null && input.value !== instructionsServerValue;
    if (!dirty) {
      input.value = instructions;
      status.textContent = "";
      status.className = "editor-status";
    }
    instructionsServerValue = instructions;
  } catch {
    // a failed load shouldn't clobber whatever is in the editor.
  }
  input.focus({ preventScroll: true });
}

function wireInstructions(): void {
  const input = $<HTMLTextAreaElement>("instructionsInput");
  const saveBtn = $<HTMLButtonElement>("instructionsSave");
  const status = $("instructionsStatus");

  const save = async (): Promise<void> => {
    if (saveBtn.disabled) return; // a save is already in flight
    saveBtn.disabled = true;
    status.textContent = "Saving…";
    status.className = "editor-status";
    try {
      const { instructions } = await saveInstructions(input.value);
      instructionsServerValue = instructions;
      status.textContent = "Saved";
      status.className = "editor-status is-saved";
    } catch {
      status.textContent = "Couldn't save — try again";
      status.className = "editor-status is-error";
    } finally {
      saveBtn.disabled = false;
    }
  };

  saveBtn.addEventListener("click", () => void save());
  input.addEventListener("input", () => {
    status.textContent = "";
    status.className = "editor-status";
  });
  // Cmd/Ctrl+S saves from anywhere in the Instructions section, not only while
  // the textarea holds focus (after a click, focus is on the Save button).
  document.addEventListener("keydown", (e) => {
    if (state.section !== "instructions") return;
    if ((e.metaKey || e.ctrlKey) && !e.shiftKey && e.key.toLowerCase() === "s") {
      e.preventDefault();
      void save();
    }
  });
}

// ---- FAQ editor ----

let faqEditingId: number | null = null; // null while adding a new FAQ
let faqDeleting = false; // guards against a double-click delete

async function loadFaqs(): Promise<void> {
  try {
    state.faqs = await listFaqs();
    renderFaqList();
  } catch {
    // transient; the list keeps its current contents.
  }
}

function renderFaqList(): void {
  const list = $("faqList");
  $("faqCount").textContent = String(state.faqs.length);
  list.replaceChildren();
  for (const faq of state.faqs) {
    const card = document.createElement("div");
    card.className = "faq-card";
    card.dataset.id = String(faq.id);
    card.innerHTML = `
      <span class="faq-num">Q${faq.id}</span>
      <div class="faq-card-text">
        <div class="faq-concise">${escapeHtml(faq.concise)}</div>
        <div class="faq-question">${escapeHtml(faq.question)}</div>
      </div>
      <div class="faq-card-actions">
        <button class="icon-btn" data-act="edit" title="Edit" aria-label="Edit Q${faq.id}"><svg class="icon icon--sm"><use href="/icons.svg#i-edit"/></svg></button>
        <button class="icon-btn" data-act="delete" title="Delete" aria-label="Delete Q${faq.id}"><svg class="icon icon--sm"><use href="/icons.svg#i-trash"/></svg></button>
      </div>`;
    card.querySelector('[data-act="edit"]')!.addEventListener("click", () => openFaqDialog(faq));
    card.querySelector('[data-act="delete"]')!.addEventListener("click", () => void removeFaq(faq));
    list.append(card);
  }
}

function openFaqDialog(faq: FaqItem | null): void {
  faqEditingId = faq?.id ?? null;
  $("faqDialogTitle").textContent = faq ? `Edit Q${faq.id}` : "Add FAQ";
  $<HTMLInputElement>("faqConcise").value = faq?.concise ?? "";
  $<HTMLTextAreaElement>("faqQuestion").value = faq?.question ?? "";
  $<HTMLTextAreaElement>("faqAnswer").value = faq?.answer ?? "";
  const status = $("faqDialogStatus");
  status.textContent = "";
  status.className = "editor-status";
  $<HTMLDialogElement>("faqDialog").showModal();
  $<HTMLInputElement>("faqConcise").focus();
}

async function saveFaq(): Promise<void> {
  const saveBtn = $<HTMLButtonElement>("faqSave");
  const status = $("faqDialogStatus");
  const body = {
    concise: $<HTMLInputElement>("faqConcise").value.trim(),
    question: $<HTMLTextAreaElement>("faqQuestion").value.trim(),
    answer: $<HTMLTextAreaElement>("faqAnswer").value.trim(),
  };
  if (!body.concise || !body.question || !body.answer) {
    status.textContent = "All three fields are required.";
    status.className = "editor-status is-error";
    $(!body.concise ? "faqConcise" : !body.question ? "faqQuestion" : "faqAnswer").focus();
    return;
  }
  if (saveBtn.disabled) return;
  saveBtn.disabled = true;
  status.textContent = "Saving…";
  status.className = "editor-status";
  try {
    if (faqEditingId === null) await createFaq(body);
    else await updateFaq(faqEditingId, body);
    $<HTMLDialogElement>("faqDialog").close();
    await loadFaqs();
  } catch {
    status.textContent = "Couldn't save — try again";
    status.className = "editor-status is-error";
  } finally {
    saveBtn.disabled = false;
  }
}

async function removeFaq(faq: FaqItem): Promise<void> {
  if (faqDeleting) return;
  const ok = confirm(`Delete Q${faq.id} ("${faq.concise}")?\n\nThis removes it from the FAQ, the Qn / ?q=${faq.id} shortcut and the Avatar's routing.`);
  if (!ok) return;
  faqDeleting = true;
  try {
    await deleteFaq(faq.id);
    await loadFaqs();
  } catch {
    // leave the list as-is on failure.
  } finally {
    faqDeleting = false;
  }
}

function wireFaq(): void {
  const dialog = $<HTMLDialogElement>("faqDialog");
  $("faqAddBtn").addEventListener("click", () => openFaqDialog(null));
  $("faqCancel").addEventListener("click", () => dialog.close());
  $("faqSave").addEventListener("click", () => void saveFaq());
  // Clear edit state however the dialog closes (Cancel, Esc, backdrop, save).
  dialog.addEventListener("close", () => {
    faqEditingId = null;
  });
}

// ---- Archive ----

let archiveViewId: string | null = null; // conversation open in the read-only dialog
let archiveBusy = false; // guards the thread Archive action against double-clicks
const restoringIds = new Set<string>(); // per-conversation restore guards (allow concurrent restores)

async function loadArchive(): Promise<void> {
  try {
    state.archive = await listArchive();
    renderArchiveList();
  } catch {
    // transient; the list keeps its current contents.
  }
}

function renderArchiveList(): void {
  const list = $("archiveList");
  $("archiveCount").textContent = String(state.archive.length);
  $<HTMLButtonElement>("downloadArchiveBtn").disabled = state.archive.length === 0;
  list.replaceChildren();
  if (!state.archive.length) {
    list.innerHTML = `<div class="convo-empty">No archived conversations yet.</div>`;
    return;
  }
  for (const convo of state.archive) {
    const card = document.createElement("div");
    card.className = "archive-card";
    card.dataset.id = convo.conversation_id;
    card.innerHTML = `
      <span class="avatar-initials">${escapeHtml(initialsOf(convo.conversation_name))}</span>
      <div class="convo-main">
        <div class="convo-top"><span class="convo-name">${escapeHtml(displayName(convo.conversation_name))}</span></div>
        <div class="convo-preview">${escapeHtml(convo.preview)}</div>
      </div>
      <div class="archive-card-side">
        <span class="msg-time">${escapeHtml(formatShort(convo.last_created_at))}</span>
        <button class="btn btn--secondary btn--sm" data-act="restore" aria-label="Restore conversation with ${escapeHtml(displayName(convo.conversation_name))}">
          <svg class="icon icon--sm"><use href="/icons.svg#i-reset"/></svg> <span class="btn-label">Restore</span>
        </button>
      </div>`;
    card.querySelector('[data-act="restore"]')!.addEventListener("click", (e) => {
      e.stopPropagation();
      void restoreFromArchive(convo.conversation_id);
    });
    card.addEventListener("click", () => void openArchiveView(convo.conversation_id));
    list.append(card);
  }
}

/** Read-only view of an archived thread (no state change server-side). */
async function openArchiveView(id: string): Promise<void> {
  archiveViewId = id;
  const dialog = $<HTMLDialogElement>("archiveDialog");
  const status = $("archiveDialogStatus");
  status.textContent = "";
  status.className = "editor-status";
  try {
    const thread = await getArchivedConversation(id);
    $("archiveInitials").textContent = initialsOf(thread.conversation_name);
    $("archiveDialogName").textContent = displayName(thread.conversation_name);
    const first = thread.messages[0];
    const started = first ? ` · started ${formatTime(first.created_at)}` : "";
    const count = thread.messages.length;
    $("archiveDialogSub").textContent = `${shortId(id)} · ${count} message${count === 1 ? "" : "s"}${started}`;
    const inner = $("archiveDialogThread");
    inner.replaceChildren();
    for (const message of thread.messages) inner.append(messageEl(message));
    dialog.showModal();
    inner.scrollTop = 0;
  } catch {
    archiveViewId = null;
  }
}

async function restoreFromArchive(id: string): Promise<void> {
  if (restoringIds.has(id)) return; // per-conversation, so distinct restores can overlap
  restoringIds.add(id);
  const headStatus = $("archiveStatus");
  try {
    await restoreConversation(id);
    if (archiveViewId === id) $<HTMLDialogElement>("archiveDialog").close();
    // Drop it locally first so a failed re-fetch can't leave a ghost card.
    state.archive = state.archive.filter((c) => c.conversation_id !== id);
    renderArchiveList();
    headStatus.textContent = "";
    headStatus.className = "editor-status";
    // Reconcile with the server and bring it back into the live inbox.
    await loadArchive();
    state.conversations = await listConversations();
    renderInbox();
  } catch {
    // Surface the failure wherever the owner is looking, and resync the list.
    const target = archiveViewId === id ? $("archiveDialogStatus") : headStatus;
    target.textContent = "Couldn't restore — try again";
    target.className = "editor-status is-error";
    await loadArchive();
  } finally {
    restoringIds.delete(id);
  }
}

/** Archive the currently open conversation (from the thread header). */
async function archiveActiveConversation(): Promise<void> {
  if (!state.activeId || archiveBusy) return;
  const id = state.activeId;
  const name = displayName(state.thread?.conversation_name ?? null);
  const ok = confirm(
    `Archive this conversation with ${name}?\n\nIt moves to the Archive and leaves the inbox. You can restore it later.`,
  );
  if (!ok) return;
  archiveBusy = true;
  try {
    await archiveConversation(id);
    state.conversations = state.conversations.filter((c) => c.conversation_id !== id);
    state.activeId = null;
    state.thread = null;
    $("threadView").hidden = true;
    $("threadEmpty").hidden = false;
    renderInbox();
    setView("list");
  } catch {
    // leave the thread open on failure.
  } finally {
    archiveBusy = false;
  }
}

async function bulkArchiveInactive(): Promise<void> {
  const btn = $<HTMLButtonElement>("archiveInactiveBtn");
  const status = $("archiveInactiveStatus");
  if (btn.disabled) return;
  const ok = confirm(
    "Archive ALL conversations with no activity in the last 72 hours?\n\nThey move to the Archive and can be restored.",
  );
  if (!ok) return;
  btn.disabled = true;
  status.textContent = "Archiving…";
  status.className = "editor-status";
  try {
    const { conversations } = await archiveInactive();
    status.textContent = conversations
      ? `Archived ${conversations} conversation${conversations === 1 ? "" : "s"}`
      : "Nothing inactive to archive";
    status.className = "editor-status is-saved";
    state.conversations = await listConversations();
    if (state.activeId && !state.conversations.some((c) => c.conversation_id === state.activeId)) {
      state.activeId = null;
      state.thread = null;
      $("threadView").hidden = true;
      $("threadEmpty").hidden = false;
    }
    renderInbox();
  } catch {
    status.textContent = "Couldn't archive — try again";
    status.className = "editor-status is-error";
  } finally {
    btn.disabled = false;
  }
}

/** Run a download, disabling its button and surfacing failures to a status line. */
async function runDownload(
  btn: HTMLButtonElement,
  status: HTMLElement,
  fn: () => Promise<void>,
): Promise<void> {
  if (btn.disabled) return;
  btn.disabled = true;
  try {
    await fn();
    status.textContent = "";
    status.className = "editor-status";
  } catch {
    status.textContent = "Couldn't download — try again";
    status.className = "editor-status is-error";
  } finally {
    btn.disabled = false;
  }
}

function wireDownloads(): void {
  $("downloadConvosBtn").addEventListener("click", () =>
    void runDownload($<HTMLButtonElement>("downloadConvosBtn"), $("downloadConvosStatus"), downloadConversations),
  );
  $("downloadArchiveBtn").addEventListener("click", () =>
    void runDownload($<HTMLButtonElement>("downloadArchiveBtn"), $("downloadArchiveStatus"), downloadArchive),
  );
}

function wireArchive(): void {
  $("archiveBtn").addEventListener("click", () => void archiveActiveConversation());
  $("archiveInactiveBtn").addEventListener("click", () => void bulkArchiveInactive());
  const dialog = $<HTMLDialogElement>("archiveDialog");
  $("archiveDialogX").addEventListener("click", () => dialog.close());
  $("archiveDialogClose").addEventListener("click", () => dialog.close());
  $("archiveDialogRestore").addEventListener("click", () => {
    if (archiveViewId) void restoreFromArchive(archiveViewId);
  });
  dialog.addEventListener("close", () => {
    archiveViewId = null;
  });
}

// ---- Polling ----

async function refresh(): Promise<void> {
  state.conversations = await listConversations();
  renderInbox();
  // Only re-fetch the open thread on the conversations section: getConversationAdmin
  // marks rows read server-side, so doing it while on a panel would silently clear a
  // visitor's unread/needs-you flag the human can't see.
  if (state.section === "conversations" && state.activeId) {
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
  wireBack();
  wireInstructions();
  wireFaq();
  wireArchive();
  wireDownloads();
  wireNav();

  state.conversations = await listConversations();
  renderInbox();
  // On a phone, land on the inbox; don't auto-open (which would mark a thread
  // read). On wider screens keep the side-by-side auto-selection, but only when
  // the conversations section is actually showing (a restored panel section must
  // not silently mark the top conversation read).
  if (!mobileMq.matches && state.section === "conversations" && state.conversations.length) {
    await selectConversation(state.conversations[0].conversation_id);
  }
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
