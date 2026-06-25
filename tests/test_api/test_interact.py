"""Tests for POST /interact endpoint."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

MOCK_RESULT = {"url": "https://example.com", "content": "# Page content", "format": "markdown", "error": None}


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock(); mock_crawler.close = AsyncMock()
    mock_job_store = MagicMock(); mock_job_store.init = AsyncMock(); mock_job_store.close = AsyncMock()
    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=MagicMock())),
        patch("src.api.app.interact_and_scrape", AsyncMock(return_value=MOCK_RESULT)),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_interact_returns_content(client):
    response = await client.post("/interact", json={
        "url": "https://example.com",
        "actions": [{"type": "click", "selector": "button#load-more", "value": "", "ms": 500}],
    })
    assert response.status_code == 200
    body = response.json()
    assert body["content"] == "# Page content"
    assert body["format"] == "markdown"


async def test_interact_returns_422_without_url(client):
    response = await client.post("/interact", json={"actions": []})
    assert response.status_code == 422
