"""Tests for POST /batch endpoint."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

URLS = ["https://example.com/1", "https://example.com/2"]


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com/1", "html": "<p>" + "word " * 30 + "</p>",
        "screenshot_b64": "", "status_code": 200, "error": None,
    })
    mock_crawler.close = AsyncMock()
    mock_extractor = MagicMock()
    mock_extractor.extract_markdown = MagicMock(return_value="# Page content")
    mock_extractor.extract_text = MagicMock(return_value="Page content")
    mock_extractor.extract_raw = MagicMock(return_value="<p>Page content</p>")
    mock_job_store = MagicMock(); mock_job_store.init = AsyncMock(); mock_job_store.close = AsyncMock()

    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=mock_extractor)),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_batch_returns_results_for_each_url(client):
    response = await client.post("/batch", json={"urls": URLS})
    assert response.status_code == 200
    body = response.json()
    assert len(body["results"]) == 2
    for r in body["results"]:
        assert "url" in r
        assert "content" in r


async def test_batch_returns_422_without_urls(client):
    response = await client.post("/batch", json={})
    assert response.status_code == 422


async def test_batch_empty_urls_returns_empty(client):
    response = await client.post("/batch", json={"urls": []})
    assert response.status_code == 200
    assert response.json()["results"] == []
