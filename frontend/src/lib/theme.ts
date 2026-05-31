/** Theme handling: dark-first, persisted in localStorage, set via data-theme on <html>. */

const STORAGE_KEY = "avatar-theme";

type Theme = "dark" | "light";

function current(): Theme {
  return document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
}

/** Apply the stored theme (default dark) to <html>. */
export function initTheme(): void {
  const saved = localStorage.getItem(STORAGE_KEY);
  const theme: Theme = saved === "light" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", theme);
}

/** Flip between dark and light, persisting the choice. */
export function toggleTheme(): void {
  const next: Theme = current() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem(STORAGE_KEY, next);
}

/** Wire a toggle button: click flips the theme and syncs moon/sun icons (like the mockups). */
export function wireThemeToggle(btn: HTMLElement): void {
  const sync = () => {
    const dark = current() === "dark";
    const moon = btn.querySelector<HTMLElement>(".theme-moon");
    const sun = btn.querySelector<HTMLElement>(".theme-sun");
    if (moon) moon.style.display = dark ? "" : "none";
    if (sun) sun.style.display = dark ? "none" : "";
  };
  sync();
  btn.addEventListener("click", () => {
    toggleTheme();
    sync();
  });
}
