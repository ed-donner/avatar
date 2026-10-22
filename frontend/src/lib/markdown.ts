/** Minimal, SAFE markdown -> HTML for avatar/human message text.
 *
 * Strategy: escape ALL html first, then convert a small whitelist of markdown
 * (headings, lists, bold, italic, inline code, links, fenced code blocks, pipe
 * tables). There is NO raw-html passthrough, so model- or human-authored text
 * cannot inject markup.
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

/** A ``` fence opening a code block: optional indent, optional info string (e.g. a language). */
const FENCE_OPEN_RE = /^(\s*)```[^`]*$/;
const FENCE_CLOSE_RE = /^\s*```\s*$/;

/** Split a pipe-table row into trimmed cells. Outer pipes are optional; "\|" is a literal pipe. */
function splitRow(line: string): string[] {
  let row = line.trim();
  if (row.startsWith("|")) row = row.slice(1);
  if (row.endsWith("|") && !row.endsWith("\\|")) row = row.slice(0, -1);
  const cells: string[] = [];
  let cell = "";
  for (let i = 0; i < row.length; i++) {
    if (row[i] === "\\" && row[i + 1] === "|") {
      cell += "|";
      i++;
    } else if (row[i] === "|") {
      cells.push(cell.trim());
      cell = "";
    } else {
      cell += row[i];
    }
  }
  cells.push(cell.trim());
  return cells;
}

/** Column alignments if `line` is a table delimiter row (e.g. "| :--- | ---: |"), else null. */
function delimiterAlignments(line: string): string[] | null {
  if (!line.includes("|")) return null;
  const cells = splitRow(line);
  if (!cells.every((c) => /^:?-+:?$/.test(c))) return null;
  return cells.map((c) =>
    c.startsWith(":") && c.endsWith(":") ? "center" : c.endsWith(":") ? "right" : c.startsWith(":") ? "left" : "",
  );
}

/** Render a pipe table, scrollable on narrow screens. An all-empty header row (a common
 *  artifact of pasting from a doc) is dropped rather than shown as a blank band. */
function renderTable(header: string[], align: string[], rows: string[][]): string {
  const row = (tag: "th" | "td", cells: string[]) =>
    `<tr>${align
      .map((a, i) => `<${tag}${a ? ` style="text-align:${a}"` : ""}>${renderInline(cells[i] ?? "")}</${tag}>`)
      .join("")}</tr>`;
  const head = header.some((c) => c) ? `<thead>${row("th", header)}</thead>` : "";
  return `<div class="md-table"><table>${head}<tbody>${rows.map((r) => row("td", r)).join("")}</tbody></table></div>`;
}

/** Render a small whitelist of markdown to safe HTML. */
export function renderMarkdown(md: string): string {
  const escaped = escapeHtml(md.replace(/\r\n/g, "\n"));
  const lines = escaped.split("\n");
  const blocks: string[] = [];
  let paragraph: string[] = [];
  let listItems: string[] = [];
  let listOrdered = false;
  let listStart = 1;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push(`<p>${renderInline(paragraph.join("<br>"))}</p>`);
      paragraph = [];
    }
  };
  const flushList = () => {
    if (listItems.length) {
      const tag = listOrdered ? "ol" : "ul";
      // Keep the author's numbering when a blank line or code block splits a numbered list.
      const start = listOrdered && listStart !== 1 ? ` start="${listStart}"` : "";
      const items = listItems.map((i) => `<li>${renderInline(i)}</li>`).join("");
      blocks.push(`<${tag}${start}>${items}</${tag}>`);
      listItems = [];
    }
  };

  for (let n = 0; n < lines.length; n++) {
    const line = lines[n];
    const fence = FENCE_OPEN_RE.exec(line);
    const align = line.includes("|") ? delimiterAlignments(lines[n + 1] ?? "") : null;
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*]\s+(.*)$/.exec(line);
    const ordered = /^\s*(\d+)\.\s+(.*)$/.exec(line);

    if (fence) {
      flushParagraph();
      flushList();
      // Code is shown verbatim (already escaped, no inline formatting). A fence indented inside
      // a list item has that indent removed from its lines. An unclosed fence runs to the end,
      // as it does mid-stream.
      const indent = new RegExp(`^ {0,${fence[1].length}}`);
      const code: string[] = [];
      while (++n < lines.length && !FENCE_CLOSE_RE.test(lines[n])) code.push(lines[n].replace(indent, ""));
      blocks.push(`<pre><code>${code.join("\n")}</code></pre>`);
    } else if (align && splitRow(line).length === align.length) {
      flushParagraph();
      flushList();
      const rows: string[][] = [];
      n += 2; // past the header and delimiter rows
      for (; n < lines.length && lines[n].includes("|"); n++) rows.push(splitRow(lines[n]));
      n--; // the loop's n++ moves on to the line after the table
      blocks.push(renderTable(splitRow(line), align, rows));
    } else if (heading) {
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
      if (!listItems.length) listStart = Number(ordered[1]);
      listOrdered = true;
      listItems.push(ordered[2]);
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
