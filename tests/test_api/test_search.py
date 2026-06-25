"""Tests for POST /search endpoint."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

MOCK_RESULTS = [
    {"url": "https://ex.com/1", "title": "T1", "snippet": "S1", "content": "# Content 1"},
]


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.close = AsyncMock()
    mock_extractor = MagicMock()
    mock_extractor.extract_markdown = MagicMock(return_value="# Content")
    mock_job_store = MagicMock()
    mock_job_store.init = AsyncMock()
    mock_job_store.close = AsyncMock()

    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=mock_extractor)),
        patch("src.api.app.search_web", AsyncMock(return_value=MOCK_RESULTS)),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_search_returns_results(client):
    response = await client.post("/search", json={"query": "test query"})
    assert response.status_code == 200
    body = response.json()
    assert body["query"] == "test query"
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 1
    assert body["results"][0]["url"] == "https://ex.com/1"


async def test_search_returns_422_without_query(client):
    response = await client.post("/search", json={})
    assert response.status_code == 422
