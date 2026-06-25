"""Tests for POST /links endpoint."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

SAMPLE_HTML = "<html><body><p>See <a href='https://example.com/about'>About</a> here.</p></body></html>"


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com", "html": SAMPLE_HTML,
        "screenshot_b64": "", "status_code": 200, "error": None,
    })
    mock_crawler.close = AsyncMock()
    mock_job_store = MagicMock(); mock_job_store.init = AsyncMock(); mock_job_store.close = AsyncMock()

    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=MagicMock())),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_links_returns_link_list(client):
    response = await client.post("/links", json={"url": "https://example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] >= 1
    assert any(l["url"] == "https://example.com/about" for l in body["links"])


async def test_links_returns_422_without_url(client):
    response = await client.post("/links", json={})
    assert response.status_code == 422
