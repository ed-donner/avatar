"""Live Udemy enrollment links, read from the owner's curriculum page (CURRICULUM_URL).

The curriculum page builds its Udemy buttons in JavaScript: `window.EDC_CONFIG` holds the
current coupon for each course (plus the featured AI FDE course URL), and the page script's
`BASE` map holds the other course URLs. The fetch tool doesn't run JavaScript, so it never
sees those links. Instead this module reads the same two blocks from the page HTML and builds
the links the way the page does, so the avatar can give a working coupon link straight away.

A background task (see main.lifespan) refreshes the links every REFRESH_SECONDS, so a chat
turn never waits on the page. If the page can't be read or parsed, the last good links are
kept and the owner is alerted once until it recovers. Off when CURRICULUM_URL is unset.
"""

import asyncio
import re
import time

import requests

from app.config import get_settings
from app.push import notify_error

REFRESH_SECONDS = 15 * 60
TIMEOUT_SECONDS = 10

CONFIG_RE = re.compile(r"window\.EDC_CONFIG\s*=\s*\{(.*?)\};", re.S)
COUPONS_RE = re.compile(r"coupons\s*:\s*\{(.*?)\}", re.S)
FDE_URL_RE = re.compile(r"fdeUrl\s*:\s*\"(https://[^\"]+)\"")
BASE_RE = re.compile(r"const BASE\s*=\s*\{(.*?)\};", re.S)
PAIR_RE = re.compile(r"(\w+)\s*:\s*\"([^\"]*)\"")
NAME_RE = re.compile(r"key:\s*\"(\w+)\",\s*n:\s*\d+,\s*name:\s*\"([^\"]*)\",\s*track:\s*\"([^\"]*)\"")
FDE_NAME = "AI FDE"  # the page features this course through EDC_CONFIG.fdeUrl, outside its course data

_links: list[tuple[str, str]] = []  # (course name, link with coupon), AI FDE first
_last_attempt: float | None = None
_failing = False


def parse_links(html: str) -> list[tuple[str, str]]:
    """Build each course's name and coupon link from the page's EDC_CONFIG and BASE blocks.

    Mirrors the page script: a course uses its own coupon, else the default one. Names come
    from the page's course data (falling back to its short key). Raises ValueError if either
    block is missing, so a page redesign is noticed.
    """
    config = CONFIG_RE.search(html)
    base = BASE_RE.search(html)
    if not config or not base:
        raise ValueError("EDC_CONFIG or the BASE course map is missing from the page")
    coupons_block = COUPONS_RE.search(config.group(1))
    coupons = dict(PAIR_RE.findall(coupons_block.group(1))) if coupons_block else {}
    courses = []
    if fde_url := FDE_URL_RE.search(config.group(1)):
        courses.append(("fde", fde_url.group(1)))
    courses += [(key, url) for key, url in PAIR_RE.findall(base.group(1)) if url.startswith("https://")]
    if not courses:
        raise ValueError("no course URLs found on the page")
    names = {key: f"{name} {track}".strip() for key, name, track in NAME_RE.findall(html)}
    names["fde"] = FDE_NAME
    links = []
    for key, url in courses:
        code = coupons.get(key) or coupons.get("default")
        links.append((names.get(key, key), f"{url}{'&' if '?' in url else '?'}couponCode={code}" if code else url))
    return links


def refresh() -> None:
    """Re-read the curriculum page, keeping the last good links if that fails."""
    global _links, _last_attempt, _failing
    url = get_settings().curriculum_url
    _last_attempt = time.monotonic()
    try:
        response = requests.get(url, timeout=TIMEOUT_SECONDS)
        response.raise_for_status()
        links = parse_links(response.text)
    except (requests.RequestException, ValueError) as exc:
        if not _failing:
            notify_error(f"Couldn't read the course coupon links from {url}: {exc}", category="course_links")
        _failing = True
        return
    _links, _failing = links, False


async def keep_fresh() -> None:
    """Refresh now (unless done recently) and then every REFRESH_SECONDS; runs as a background task."""
    if not get_settings().curriculum_url:
        return
    while True:
        if _last_attempt is not None:
            wait = _last_attempt + REFRESH_SECONDS - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
        await asyncio.to_thread(refresh)


def prompt_text() -> str:
    """The links as a section for the system prompt's owner profile, or "" if there are none."""
    if not _links:
        return ""
    lines = "\n".join(f"- {name}: {link}" for name, link in _links)
    return f"""
### Enrollment links

These are the Udemy links to my courses, each carrying my current coupon, exactly as they are right now on
my curriculum page ({get_settings().curriculum_url}). Give the exact link when someone asks how to enroll
or about prices, discounts or coupons. Never change a coupon code or make one up.

{lines}
"""
