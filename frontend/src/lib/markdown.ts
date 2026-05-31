/** Minimal, SAFE markdown -> HTML for avatar/human message text.
 *
 * Strategy: escape ALL html first, then convert a small whitelist of markdown
 * (headings, lists, bold, italic, inline code, links). There is NO raw-html
 * passthrough, so model- or human-authored text cannot inject markup.
 */

import { escapeHtml } from "./dom.ts";

/** Private-use sentinels wrapping a stashed-slot index. They cannot occur in
 *  user text or escaped HTML, so restoration never collides with content. */
const SLOT_OPEN = "\uE000";
const SLOT_CLOSE = "\uE001";
const SLOT_RE = new RegExp(`${SLOT_OPEN}(\\d+)${SLOT_CLOSE}`, "g");

/** Convert inline spans (code, bold, italic, links) on already-escaped text. */
function renderInline(text: string): string {
  // Stash code and links into slots so later passes (bold/italic, autolink)
  // can't transform their contents and URLs are never double-linked.
  const slots: string[] = [];
  const stash = (html: string): string => `${SLOT_OPEN}${slots.push(html) - 1}${SLOT_CLOSE}`;
  let out = text.replace(/`([^`]+)`/g, (_m, code: string) => stash(`<code>${code}</code>`));

  // Markdown links [text](url) where url is http/https/mailto only.
  out = out.replace(
    /\[([^\]]+)\]\((https?:\/\/[^\s)]+|mailto:[^\s)]+)\)/g,
    (_m, label: string, href: string) =>
      stash(`<a href="${href}" target="_blank" rel="noopener noreferrer">${label}</a>`),
  );

  // Bare URLs -> clickable links, so links are always clickable even if the
  // model emits a plain URL. Peel trailing sentence punctuation, keeping a
  // closing paren only when it is unbalanced (so URLs with (parens) survive).
  out = out.replace(/(^|[\s(])(https?:\/\/[^\s<]+)/g, (_m, pre: string, url: string) => {
    let href = url;
    let tail = "";
    for (;;) {
      const last = href[href.length - 1];
      const unbalancedParen =
        last === ")" && (href.match(/\)/g) ?? []).length > (href.match(/\(/g) ?? []).length;
      if (".,;:!?".includes(last) || unbalancedParen) {
        tail = last + tail;
        href = href.slice(0, -1);
      } else {
        break;
      }
    }
    return `${pre}${stash(`<a href="${href}" target="_blank" rel="noopener noreferrer">${href}</a>`)}${tail}`;
  });

  out = out.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
  out = out.replace(/(^|[^*])\*([^*\n]+)\*/g, "$1<em>$2</em>");
  out = out.replace(/(^|[^_])_([^_\n]+)_/g, "$1<em>$2</em>");

  // Restore stashed code/link slots.
  out = out.replace(SLOT_RE, (_m, i: string) => slots[Number(i)]);
  return out;
}

/** Render a small whitelist of markdown to safe HTML. */
export function renderMarkdown(md: string): string {
  const escaped = escapeHtml(md.replace(/\r\n/g, "\n"));
  const lines = escaped.split("\n");
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listOrdered = false;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${renderInline(paragraph.join("<br>"))}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (listItems.length) {
      const tag = listOrdered ? "ol" : "ul";
      const items = listItems.map((i) => `<li>${renderInline(i)}</li>`).join("");
      blocks.push(`<${tag}>${items}</${tag}>`);
      listItems = [];
    }
  };

  for (const line of lines) {
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);

    if (heading) {
      flushParagraph();
      flushList();
      blocks.push(`<h3>${renderInline(heading[2])}</h3>`);
    } else if (bullet) {
      flushParagraph();
      if (listOrdered) flushList();
      listOrdered = false;
      listItems.push(bullet[1]);
    } else if (ordered) {
      flushParagraph();
      if (!listOrdered) flushList();
      listOrdered = true;
      listItems.push(ordered[1]);
    } else if (line.trim() === "") {
      flushParagraph();
      flushList();
    } else {
      flushList();
      paragraph.push(line);
    }
  }
  flushParagraph();
  flushList();
  return blocks.join("");
}
