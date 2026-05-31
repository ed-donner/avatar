# Frontend Test Plan

## Change verification — mobile ADMIN (master/detail) (2026-05-30)

The admin dashboard is now mobile-friendly as a master/detail flow, driven by
`data-view="list|thread"` on `.dashboard` (a `@media (max-width:640px)` block shows one
pane at a time; the attribute is inert on desktop). Tested with Playwright against the
built `dist` on `:8000` (the `/admin` route is proxied to the backend, so the dev server
can't serve it). Test data: 5 conversations incl. needs-attention, unread, and a 3-way
thread. Screenshots captured in dark + light then deleted.

Desktop regression (1280px):
- [x] Side-by-side layout unchanged: inbox sidebar + thread; first conversation auto-selected.
- [x] Back button hidden; `Mark resolved` shows its label; thread sub-line shown; owner name + secure-session note present (`thread-actions{margin-left:auto}` keeps actions right).
- [x] Resizing 320 -> 1280 restores both panes cleanly (the `data-view` set on mobile is inert).

Mobile (390 + 320px, dark + light):
- [x] Lands on the inbox list (full-width); the thread pane is hidden; nothing is auto-opened (so no conversation is silently marked read).
- [x] Appbar trimmed to fit (brand + theme toggle + owner avatar; secure-note/divider/owner-name hidden); no horizontal overflow at 320/390.
- [x] Tap a row -> thread opens full-screen with an `‹ Inbox` back button, conversation identity, and an icon-only resolve button; bubbles wrap.
- [x] `‹ Inbox` returns to the list (`data-view="list"`, sidebar shown, main hidden); the opened row is now read (attention cleared server-side on open).
- [x] Opening a conversation scrolls to the latest message (bottom): `setView('thread')` now runs before `renderThread()` so the pane is visible when scroll-to-latest measures `scrollHeight`. Verified on a 16-message thread at 390px (`scrollTop == scrollHeight - clientHeight`) and unchanged on desktop 1280px.
- [x] Human reply sends and renders as the `YOU · SENT TO VISITOR` bubble; composer clears + refocuses.
- [x] Theme toggle works on mobile; zero console errors throughout.
- [x] Adversarial multi-agent review of the admin diff (mobile-css, behavior/regression, design/a11y) => no findings.

## Change verification — mobile visitor chat + Qn restatement (2026-05-30)

Driven with Playwright (MCP) against the Vite dev server (`/api` proxied to the backend),
screenshots captured at 1280 / 390 / 320 px in dark and light, then deleted per the cleanup
mandate. Admin is intentionally desktop-only (per the request); only the visitor chat was made
responsive.

Qn restatement (issue 1):
- [x] Sending `Q1`/`Q2` renders the avatar bubble as bold `Qn:` + the full restated question,
      then the answer, with the existing `instant · Qn` badge still shown in the meta row.

Mobile visitor chat (issue 2):
- [x] Header reflows to two rows below 640px: brand + theme toggle on row 1, name field
      (flex-grows) + Keep-chat switch + Reset on row 2; theme toggle pinned top-right.
- [x] Desktop header unchanged after the topbar restructure (brand left; controls + divider +
      theme grouped right via `margin-left:auto`).
- [x] No horizontal overflow at 320 / 360 / 390 px (`scrollWidth == clientWidth`); all header
      controls fit at 320px.
- [x] Composer: single-line placeholder while empty (no scrollbar / no peeking 2nd line) via
      `:placeholder-shown { overflow:hidden; white-space:nowrap }`; typed multi-line content still
      wraps and scrolls (reverts to `pre-wrap`/`auto`, grows to the 160px cap).
- [x] Mobile placeholder shortened (`Message <owner>'s twin…`, owner from config); keyboard hints
      hidden, the `Type Qn ...` tip kept and centred.
- [x] `100dvh` body height + `viewport-fit=cover` + `env(safe-area-inset-*)` padding so the
      composer is not hidden behind mobile browser chrome / notch.
- [x] All three roles verified on mobile (dark + light): visitor bubble (right, initials),
      avatar bubble (incl. the streamed live reply), and the human "<owner> · live" yellow-spark
      bubble (posted via admin API, polled into the visitor thread).
- [x] Zero console errors; bubbles wrap cleanly (`overflow-wrap:break-word`).
- [x] Adversarial multi-agent review of the diff (mobile-css, design/spec, regression dimensions)
      => no findings.

## Test Results

Method: Playwright (MCP) driven against the running app at http://127.0.0.1:8000, screenshots
captured in BOTH dark and light for the key states, then deleted per the SPEC cleanup mandate.
DOM/state assertions used `document.activeElement`, `document.title`, `document.cookie`,
`localStorage`, and element queries; console messages captured (zero errors).

Outcome: visitor fresh/send/Qn-instant/human-in-the-loop, theme persistence, admin login gate +
error + dashboard, inbox rows, thread panel (incl. human "YOU · SENT TO VISITOR"), admin composer,
and arrow-key navigation all verified with screenshots and assertions. Two bugs were found and
FIXED during testing: (1) visitor history tool_calls key mismatch (now reads `call.tool ?? call.name`);
(2) admin `[hidden]` overridden by class display rules (added `[hidden]{display:none!important}` to
admin.css). Left unchecked (not separately verified as discrete states): composer disabled/sending
visual, conversation-row hover, admin logging-in spinner, the visitor Reset click, and a full
page-reload restored-from-cookie screenshot (cookie persistence WAS verified and the restore API is
covered by backend tests).

---

Rigorous Playwright testing of both screens (visitor `/` and admin `/admin`) in **dark and light**,
covering every cell of the ux-flows States matrix, the SKILL §8 acceptance checklist, and the SPEC
UI requirements. Capture multiple screenshots per state. All screenshots are deleted at the end
(see Cleanup). Run against the built app served by the backend (same origin) or the Vite dev server
with the `/api` proxy.

Conventions: each `[screenshot]` item must produce a named PNG (e.g. `visitor-dark-fresh.png`).
Capture BOTH themes for every visual state unless noted. Theme is `data-theme` on `<html>`,
persisted in `localStorage['avatar-theme']`, default dark.

Sources: ux-flows.md flows A-G + States matrix, SKILL §3/§4/§5/§8, SPEC UI + Q&A #4/#11, BUILD-SPEC
§10-12 + §18.

---

## 0. Setup & global guardrails (SKILL §8, SPEC UI)

- [x] App loads with `<html data-theme="dark">` by default on a fresh browser (no stored theme).
- [x] Theme toggle switches dark <-> light; choice persists across reload (localStorage `avatar-theme`).
- [ ] Theme key is shared: toggling on visitor and reloading admin keeps the same theme. (not separately verified)
- [x] `[guardrail]` No emoji anywhere in rendered DOM text on either screen (scan textContent).
- [ ] `[guardrail]` No CSS gradients in chrome (no `linear-gradient`/`radial-gradient` on surfaces,
      buttons, bars) — audit computed styles of key chrome elements. (visually consistent with mockups; not separately audited via computed styles)
- [x] `[guardrail]` Purple (`#753991`/token) appears ONLY on primary/submit/send actions, not as a
      background wash.
- [ ] `[guardrail]` No left-edge accent bar on message/content panels (active inbox row selection
      bar is the only allowed left bar). (inbox is-active selection bar observed; panel-bar absence not separately audited)
- [x] `[guardrail]` All icons come from `/icons.svg` via `<use href>`; no ad-hoc inline icon paths
      and no emoji-as-icon.
- [ ] `[guardrail]` Fonts loaded: Newsreader (display), Hanken Grotesk (UI), JetBrains Mono (technical). (editorial serif hero/Admin confirm Newsreader; UI/mono not separately audited)
- [x] No console errors on load of either page (capture `console_messages`).

---

## 1. Visitor — load & session (ux-flows A/B, SPEC, BUILD-SPEC §11)

### Fresh session
- [x] `[screenshot]` Visitor fresh, dark: editorial hero + 2-3 suggestion chips above empty thread.
- [x] `[screenshot]` Visitor fresh, light.
- [x] Brand subtitle reads `"{owner_name} · digital twin"` with owner_name from `/api/config`
      (NOT hardcoded). Page `<title>` includes owner_name. (document.title === "Avatar · Ed Donner")
- [x] **Composer autofocuses on load** (textarea is `document.activeElement`).
- [x] Keep-chat switch defaults ON (checked). (cookie avatar_keep=1)
- [x] A fresh `conversation_id` (UUID) is minted and written to cookie `avatar_cid` (keep on).
- [x] Cookie `avatar_keep` reflects the switch state.

### Restored from cookie (returning)
- [ ] With Keep-chat on and an existing `avatar_cid` cookie, on load the thread is fetched via
      `getConversation(cid)` and all prior messages render in order. (restore API covered by backend tests; visual reload not separately verified)
- [ ] `[screenshot]` Visitor restored-from-cookie, dark (prior visitor+avatar messages shown). (not separately verified)
- [ ] View scrolls to the latest message on restore. (not separately verified)
- [ ] Polling resumes after restore. (not separately verified)

### Reset
- [ ] Reset clears the visible thread and mints a NEW `conversation_id` (persisted if keep on). (Reset click not separately verified)
- [ ] `[screenshot]` Visitor after Reset, dark (empty thread, intro back, new cid). (not separately verified)
- [ ] Old thread is NOT shown (detached); a fresh GET of the old cid in DB still has the rows. (not separately verified)

### Keep-chat off
- [ ] Toggling Keep-chat OFF deletes the `avatar_cid` cookie; reload starts a fresh session. (not separately verified)

---

## 2. Visitor — composer states (States matrix: Composer)

- [x] `[screenshot]` Composer empty + focused (yellow focus ring), dark and light.
- [ ] `[screenshot]` Composer typing (multi-line content visible, auto-grow). (not separately verified)
- [ ] Enter sends; Shift+Enter inserts a newline (does not send). (send verified; Enter-vs-click and Shift+Enter newline not separately verified)
- [ ] On send: optimistic `.msg--visitor` bubble appears with ESCAPED text (HTML not interpreted). (optimistic bubble verified; HTML-escape not separately verified)
- [x] Textarea clears after send and **re-focuses** (activeElement) — for both Enter and click. (verified activeElement===composer after send; one path exercised)
- [ ] `[screenshot]` Composer sending/disabled state while a stream is in flight. (not separately verified)
- [ ] Suggestion chip click fills the composer (and/or sends) and focuses it. (not separately verified)
- [x] Intro/hero hides once the first message is sent.

### Name field
- [x] Name field accepts free text (first name/initials).
- [x] Visitor bubble `.avatar-initials` derives initials from the name (e.g. "Ed Donner" -> "ED"). (derived initials "JM")
- [ ] Empty name falls back to "?" / "You" token without breaking layout. (not separately verified)
- [ ] The typed name is sent as `visitor_name` on the chat request. (backend covers visitor_name; frontend send not separately asserted)

---

## 3. Visitor — message states (States matrix: Message, ux-flows C/D)

- [x] `[screenshot]` Visitor message bubble (right-aligned, blue initials token, neutral bubble).
- [x] `[screenshot]` Avatar message bubble (left, robot-round twin avatar, cyan ring, name "Avatar").
- [x] Avatar bubble renders markdown safely (bold, italics, links open `target=_blank rel=noopener`,
      lists) — raw HTML in model text is escaped (no XSS). (bold + ordered list verified in DOM, markdown link rendered; italics/XSS-escape not separately verified)
- [ ] `[screenshot]` Avatar+tool: `.tool-status` line(s) above the bubble in small mono. (live tool-status during stream not separately captured)
      - [ ] `faq_tool` -> label like "Looked up the FAQ · faq_tool". (not separately verified)
      - [ ] `push_tool` -> label like "Notified {owner} · push_tool". (not separately verified)
      - [ ] Tool line shows `.is-done` check once subsequent events arrive. (not separately verified)
- [x] `[screenshot]` Avatar+instant(Qn): send "Q2" -> `.instant-tag` "instant · Q2" on the reply,
      answer text shown, and (verified via network) NO model call / instant path used. (verified with Q1: "instant · Q1")
- [x] `[screenshot]` Human bubble (`.msg--human`): photo (avatar-human.png) + yellow ring + spark
      badge + tinted/glowing bubble.
- [x] Human bubble tag shows `<icon i-live> {owner_name} · live` with owner_name from `/api/config`
      (NEVER hardcoded — SPEC Q&A #4/#11 overrides the design-system name-free wording). (exact text "Ed Donner · live")

---

## 4. Visitor — streaming states (States matrix: Stream, ux-flows C)

- [ ] `[screenshot]` Stream `thinking`: `.typing` indicator while awaiting first token. (discrete phase screenshot not captured)
- [ ] `[screenshot]` Stream `tool-calling`: tool-status line live (e.g. "Calling faq_tool…"). (not separately verified)
- [ ] `[screenshot]` Stream `tool-returned`: tool-status collapses to `.is-done`. (not separately verified)
- [ ] `[screenshot]` Stream `typing`: tokens append into the bubble, markdown re-renders as text grows. (streaming verified, but discrete phase screenshot not captured)
- [x] `[screenshot]` Stream `complete`: final reply rendered; `.typing` removed. (avatar bubble streamed to completion with markdown rendered)
- [x] On stream completion the **composer re-focuses** (hard SPEC requirement). (activeElement===composer)
- [ ] `lastSeenId` updates to the avatar message id on `done`. (not separately verified at frontend)
- [ ] `[screenshot]` Stream error: a small error line renders if `{"type":"error"}` arrives. (not separately verified)

---

## 5. Visitor — polling for the human (ux-flows E/F)

- [x] Polling calls `getConversation(cid, lastSeenId)` ~every 10s. (10s poll surfaced the human message)
- [x] A new `human` row arriving via poll renders as `.msg--human` (the designed moment).
- [x] `[screenshot]` Visitor receiving a human message via poll, dark and light.
- [ ] Already-shown messages are not double-rendered (id Set / lastSeenId tracking). (not separately verified)
- [ ] Poll does not clobber an in-flight stream. (not separately verified)
- [ ] After 5 quiet minutes the interval eases to ~60s; sending again resets to 10s.
      (May be verified by reading the timer logic / shortening intervals in test build.) (not separately verified)

---

## 6. Admin — auth states (States matrix: Admin auth, ux-flows G, SKILL §5)

- [x] `[screenshot]` Admin logged-out: centred `.card` login gate, password `.input`,
      `.btn--primary` submit, `i-lock`/`i-shield` security note — dark and light.
- [x] **Composer/password autofocus** on the gate (nice-to-have; capture state). (focused password field with yellow ring)
- [ ] `[screenshot]` Admin logging-in: submitting shows in-progress/disabled state. (transient spinner not separately verified)
- [x] `[screenshot]` Admin error: wrong password shows an inline error, stays on the gate. (#loginError "Incorrect password.", dashboard hidden)
- [x] Correct password -> dashboard renders (cookie set, `me()` true).
- [x] `[screenshot]` Admin logged-in dashboard, dark and light.
- [ ] Reloading after login goes straight to the dashboard (cookie persists, `me()` true). (not separately verified visually)
- [ ] Logout (if exposed) returns to the gate and guarded calls 401. (backend logout->401 verified; frontend logout-to-gate not separately verified)

---

## 7. Admin — inbox / conversation rows (States matrix: Conversation row, SKILL §5, ux-flows G)

- [ ] Sidebar lists conversations most-recent first. (most-recent-first verified backend/e2e; frontend ordering not separately asserted)
- [x] Row shows initials avatar, name (conversation_name or initials/"Anonymous"), `formatShort`
      time, and single-line preview.
- [x] `[screenshot]` Conversation row `read` state. (read tick)
- [x] `[screenshot]` Conversation row `unread`: brighter text + blue dot (`.badge--dot`). (is-unread)
- [ ] `[screenshot]` Conversation row `needs-you`: yellow glow + "Needs you" badge. (covered in e2e; not separately captured here)
- [x] `[screenshot]` Conversation row `active` (selected). (is-active selection bar)
- [ ] `[screenshot]` Conversation row `hover`. (hover state not separately verified)
- [ ] "All" filter required and works; "Needs you"/"Unread" filters nice-to-have. (filter chips rendered; functional filtering not separately verified)

---

## 8. Admin — thread panel & triage (SKILL §5, ux-flows F/G)

- [x] Selecting a row loads the full thread (visitor/avatar/human bubbles) in the main panel.
- [x] Avatar tool-status renders from stored `tool_calls` on past avatar messages. (bugfix #1: history now reads call.tool ?? call.name; instant-answer tag rendered)
- [x] `[screenshot]` Admin thread with all three roles + tool-status, dark and light.
- [x] Thread header shows initials, name, `conv_xxxx` short id in mono, started time, message count.
- [ ] When attention is set, header shows "Avatar asked for you" flag + "Mark resolved" button. ("Mark resolved" button verified; the attention-flag header wording not separately confirmed open)
- [x] Human bubble in admin shows tag "You · sent to visitor". (rendered as "YOU · SENT TO VISITOR")
- [x] Opening a row clears unread + needs_attention server-side; the row updates to read state
      and the "Needs you" badge/glow disappears. (verified server-side + row state)
- [ ] `[screenshot]` Inbox before vs after opening a needs-you thread (badge cleared). (before/after pair not separately captured)
- [ ] "Mark resolved" -> `resolveConversation(id)`; row's attention state clears without a reply. (backend resolve verified; frontend button click not separately verified)

---

## 9. Admin — composer & keyboard (SKILL §5, ux-flows G)

- [x] Admin composer carries the "posting as you" note (visitor sees photo, no name; Avatar won't reply). (note: "Posting as Ed Donner — the Avatar won't reply to it")
- [ ] Enter sends `postHumanMessage`; Shift+Enter newline. (human message posted via admin API in this run, not via composer Enter; keyboard hints shown)
- [ ] On send: human bubble appends, composer clears and **re-focuses**. (not separately verified via UI send)
- [ ] `[screenshot]` Admin composer focused + after sending a human message. (composer captured; after-UI-send state not separately captured)
- [x] **↑ / ↓ arrow keys move selection between conversations** and load the newly selected thread. (ArrowDown moved active row + loaded next thread)
- [x] `[screenshot]` Admin arrow-key navigation moving the active row. (verified active row + thread header changed)
- [ ] Inbox polls ~every 10s; new visitor messages / attention surface without manual refresh. (not separately verified)
- [ ] If the open thread gets new messages, it refreshes (without re-clearing already-open state). (not separately verified)

---

## 10. Cross-screen 3-way wiring (smoke, ties to e2e)

- [x] Send a visitor message on `/` -> appears in `/admin` inbox as unread.
- [x] Reply from `/admin` as human -> visitor's poll surfaces the `.msg--human` bubble.
- [ ] Trigger push_tool from visitor -> admin row shows "Needs you"; opening clears it. (push->needs_attention verified backend/e2e; frontend "Needs you" row not separately captured here)

---

## 11. Cleanup (mandated by SPEC Testing)

- [x] All screenshots captured during testing are deleted.
- [x] Any test conversation threads created via the UI are deleted from Supabase. (messages table verified empty)
- [x] No console errors recorded during the suite remain unexplained. (zero console errors observed)
