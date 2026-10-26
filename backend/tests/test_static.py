"""Tests for serving the frontend: pages are revalidated, and a page cached from an older release recovers."""

from fastapi.testclient import TestClient
from starlette.applications import Starlette
from starlette.routing import Mount

from app import main


def test_pages_must_be_revalidated(client, tmp_path, monkeypatch):
    """Without Cache-Control a browser reused the page for days after a deploy, with scripts that were gone."""
    for name in ("index.html", "admin.html"):
        (tmp_path / name).write_text("<html></html>")
    monkeypatch.setattr(main, "DIST", tmp_path)
    for page in ("/", "/admin"):
        response = client.get(page)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-cache"


def _assets_client(tmp_path) -> TestClient:
    (tmp_path / "main-current.js").write_text("console.log('current')")
    return TestClient(Starlette(routes=[Mount("/assets", main.AssetFiles(directory=tmp_path))]))


def test_existing_asset_is_served(tmp_path):
    response = _assets_client(tmp_path).get("/assets/main-current.js")
    assert response.status_code == 200
    assert response.text == "console.log('current')"


def test_missing_script_reloads_the_stale_page(tmp_path):
    """An older release's cached page asks for its own bundle and gets a script that loads the page afresh."""
    response = _assets_client(tmp_path).get("/assets/main-CqFiJY_5.js")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/javascript")
    assert response.headers["cache-control"] == "no-store"
    assert response.text == main.STALE_PAGE_SCRIPT
    assert 'searchParams.has("fresh")' in response.text  # reloads once, never in a loop


def test_other_missing_assets_still_404(tmp_path):
    client = _assets_client(tmp_path)
    assert client.get("/assets/main-old.css").status_code == 404
    assert client.get("/assets/nope.png").status_code == 404
