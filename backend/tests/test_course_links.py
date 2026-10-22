"""Tests for the live course coupon links read from the curriculum page."""

import pytest
import requests

from app import agent, course_links
from app.config import get_settings

# A cut-down curriculum page: the two script blocks the page uses to build its Udemy buttons,
# plus its course data (names), with made-up coupon codes.
SAMPLE_PAGE = """
<script>
  window.EDC_CONFIG = {
    coupons: {
      default: "DEFAULT_CODE",
      builder: "BUILDER_CODE",
      fde: "FDE_CODE"
    },
    fdeUrl: "https://www.udemy.com/course/ai-fde-sample/",
    youtubeId: "abc"
  };
</script>
<script>
    const CFG = (window.EDC_CONFIG && typeof window.EDC_CONFIG === "object") ? window.EDC_CONFIG : {};
    const BASE = {
      builder: "https://www.udemy.com/course/ai-builder-sample/",
      core: "https://www.udemy.com/course/core-sample/"
    };
    const PHASES = [
      { courses: [
          { key: "builder", n: 1, name: "AI Builder", track: "" },
          { key: "core", n: 4, name: "AI Engineer", track: "Core Track" }
      ] }
    ];
</script>
"""


def test_parse_links_mirrors_the_page_with_ai_fde_first():
    assert course_links.parse_links(SAMPLE_PAGE) == [
        ("AI FDE", "https://www.udemy.com/course/ai-fde-sample/?couponCode=FDE_CODE"),
        ("AI Builder", "https://www.udemy.com/course/ai-builder-sample/?couponCode=BUILDER_CODE"),
        # no coupon of its own, so the default one, as on the page
        ("AI Engineer Core Track", "https://www.udemy.com/course/core-sample/?couponCode=DEFAULT_CODE"),
    ]


def test_parse_links_rejects_a_redesigned_page():
    with pytest.raises(ValueError):
        course_links.parse_links("<html><body>No course script here</body></html>")


def test_failed_refresh_keeps_last_good_links_and_alerts_once(monkeypatch):
    good = [("AI FDE", "https://www.udemy.com/course/ai-fde-sample/?couponCode=FDE_CODE")]
    monkeypatch.setattr(course_links, "_links", good)
    monkeypatch.setattr(course_links, "_failing", False)
    alerts = []
    monkeypatch.setattr(course_links, "notify_error", lambda summary, **kwargs: alerts.append(summary))

    def down(*args, **kwargs):
        raise requests.ConnectionError("site down")

    monkeypatch.setattr(course_links.requests, "get", down)
    course_links.refresh()
    course_links.refresh()
    assert course_links._links == good  # the last good links are kept
    assert len(alerts) == 1  # one alert per outage, not one per refresh


def test_prompt_lists_the_links(monkeypatch):
    link = "https://www.udemy.com/course/ai-fde-sample/?couponCode=FDE_CODE"
    monkeypatch.setattr(course_links, "_links", [("AI FDE", link)])
    prompt = agent.build_system_prompt()
    assert "### Enrollment links" in prompt
    assert f"- AI FDE: {link}" in prompt


def test_prompt_has_no_links_section_without_links(monkeypatch):
    monkeypatch.setattr(course_links, "_links", [])
    assert "### Enrollment links" not in agent.build_system_prompt()


@pytest.mark.skipif(not get_settings().curriculum_url, reason="CURRICULUM_URL is not set")
def test_live_curriculum_page_still_parses():
    """Fails if the curriculum page is redesigned so its coupon links can no longer be read."""
    response = requests.get(get_settings().curriculum_url, timeout=course_links.TIMEOUT_SECONDS)
    links = course_links.parse_links(response.text)
    names = [name for name, _ in links]
    assert names[0] == "AI FDE"
    assert len(links) == 7
    assert all("couponCode=" in link for _, link in links)
