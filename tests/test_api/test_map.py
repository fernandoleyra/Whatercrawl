"""Tests for POST /map endpoint."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

MOCK_URLS = ["https://example.com/", "https://example.com/about"]


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.close = AsyncMock()
    mock_job_store = MagicMock()
    mock_job_store.init = AsyncMock()
    mock_job_store.close = AsyncMock()

    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=MagicMock())),
        patch("src.api.app.map_site", AsyncMock(return_value=MOCK_URLS)),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_map_returns_urls(client):
    response = await client.post("/map", json={"url": "https://example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert "https://example.com/" in body["urls"]


async def test_map_returns_422_without_url(client):
    response = await client.post("/map", json={})
    assert response.status_code == 422
