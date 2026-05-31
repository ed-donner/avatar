/** Tiny DOM helpers shared by the visitor and admin pages. */

type Attrs = Record<string, string | number | boolean | undefined>;
type Child = Node | string;

/** Create an element, applying attributes and appending children. */
export function el<K extends keyof HTMLElementTagNameMap>(
  tag: K,
  attrs?: Attrs,
  children?: Child[],
): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [key, value] of Object.entries(attrs)) {
      if (value === undefined || value === false) continue;
      if (key === "class") node.className = String(value);
      else if (key === "html") node.innerHTML = String(value);
      else node.setAttribute(key, String(value));
    }
  }
  if (children) {
    for (const child of children) {
      node.append(typeof child === "string" ? document.createTextNode(child) : child);
    }
  }
  return node;
}

/** Escape a string for safe insertion into HTML text content. */
export function escapeHtml(s: string): string {
  return s
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

/** HTML string for an icon referencing the public sprite. */
export function icon(name: string, cls = "icon"): string {
  return `<svg class="${cls}"><use href="/icons.svg#i-${name}"/></svg>`;
}

/** Build an icon as a detached SVG element. */
export function iconEl(name: string, cls = "icon"): SVGSVGElement {
  const tpl = document.createElement("template");
  tpl.innerHTML = icon(name, cls);
  return tpl.content.firstElementChild as SVGSVGElement;
}
