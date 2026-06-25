"""Tests for POST /screenshot endpoint."""
from __future__ import annotations
import base64
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

FAKE_B64 = base64.standard_b64encode(b"fakepngbytes").decode()


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com", "html": "<p>content</p>",
        "screenshot_b64": FAKE_B64, "status_code": 200, "error": None,
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


async def test_screenshot_returns_base64(client):
    response = await client.post("/screenshot", json={"url": "https://example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["screenshot_b64"] == FAKE_B64
    assert body["url"] == "https://example.com"
    assert "width" in body
    assert "height" in body


async def test_screenshot_returns_422_without_url(client):
    response = await client.post("/screenshot", json={})
    assert response.status_code == 422
