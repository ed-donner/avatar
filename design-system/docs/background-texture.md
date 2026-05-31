# Background texture

The visitor page has a subtle HUD-style background texture (the admin dashboard does not). It is a faint, tiled mark that sits behind the conversation. The mark **colour follows the theme** (`--grid-line` in `tokens.css`: a cool tint on dark, a navy tint on light), so any variation works in both modes.

## How it's built

- `frontend/src/styles/tokens.css` defines `--grid-mark` — a tiny SVG (URL-encoded data URI) of a single mark.
- `frontend/src/styles/components.css` `.hud-grid::before` is a fixed, full-viewport overlay (`z-index:-1`) with `background: var(--grid-line)` **masked** by `--grid-mark`, tiled at `mask-size: 44px 44px`.

To change the texture, swap the SVG shape in `--grid-mark` (and optionally the `mask-size` spacing). The shape is drawn in white (`%23fff`) because it is used as an alpha/luminance mask; the visible colour comes from `--grid-line`.

## Variations

The default owner (Ed) picked **rings**. Other site owners may prefer the crosses or the original grid — all are "in the same family" (a fine, structured, low-contrast field).

**Rings / nodes (current).** A field of small hollow circles; reads as a network of nodes, no glyph.
```
--grid-mark: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='44'%20height='44'%3E%3Ccircle%20cx='22'%20cy='22'%20r='3'%20fill='none'%20stroke='%23fff'%20stroke-width='1'/%3E%3C/svg%3E");
```

**Registration crosses.** Small "+" marks (a crop-mark / reticle feel). Note: at a glance these read as plus-signs scattered across the page.
```
--grid-mark: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='44'%20height='44'%3E%3Cpath%20d='M22%2017.5v9M17.5%2022h9'%20stroke='%23fff'%20stroke-width='1.2'%20stroke-linecap='round'/%3E%3C/svg%3E");
```

**Dots.** The most minimal — small solid dots.
```
--grid-mark: url("data:image/svg+xml,%3Csvg%20xmlns='http://www.w3.org/2000/svg'%20width='44'%20height='44'%3E%3Ccircle%20cx='22'%20cy='22'%20r='1.4'%20fill='%23fff'/%3E%3C/svg%3E");
```

**Original blueprint grid.** A 44px line grid. This one is *not* a mask — restore the original `.hud-grid` rule (and you can drop the `.hud-grid::before` block and `--grid-mark`):
```css
.hud-grid {
  background-image:
    linear-gradient(var(--grid-line) 1px, transparent 1px),
    linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
  background-size: 44px 44px;
}
```

Tuning tips: increase `mask-size` for a sparser field, or nudge `--grid-line`'s alpha (in the dark/light theme blocks of `tokens.css`) if a mark needs to be a touch more or less visible.
