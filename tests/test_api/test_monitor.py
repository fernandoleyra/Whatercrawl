"""Tests for POST /monitor/snapshot and POST /monitor/check endpoints."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

pytestmark = pytest.mark.asyncio

OLD_CONTENT = "# Page\n\nOriginal paragraph here."
NEW_CONTENT = "# Page\n\nOriginal paragraph here.\n\nNew paragraph added."


@pytest_asyncio.fixture
async def client():
    mock_crawler = MagicMock()
    mock_crawler.crawl_url = AsyncMock(return_value={
        "url": "https://example.com", "html": "<p>" + "word " * 30 + "</p>",
        "screenshot_b64": "", "status_code": 200, "error": None,
    })
    mock_crawler.close = AsyncMock()
    mock_extractor = MagicMock()
    mock_extractor.extract_markdown = MagicMock(return_value=OLD_CONTENT)
    mock_job_store = MagicMock()
    mock_job_store.init = AsyncMock()
    mock_job_store.close = AsyncMock()
    mock_job_store.create_job = AsyncMock(return_value="snap-001")
    mock_job_store.get_job = AsyncMock(return_value={
        "id": "snap-001", "status": "done",
        "result": [{"content": OLD_CONTENT, "url": "https://example.com"}],
        "params": '{"url": "https://example.com"}', "type": "monitor",
        "error": None, "worker_id": None,
        "created_at": "2026-06-24", "updated_at": "2026-06-24",
    })
    mock_job_store.update_job = AsyncMock()

    with (
        patch("src.api.app.CrawlerEngine", MagicMock(return_value=mock_crawler)),
        patch("src.api.app.JobStore", MagicMock(return_value=mock_job_store)),
        patch("src.api.app.ContentExtractor", MagicMock(return_value=mock_extractor)),
    ):
        from src.api.app import app
        async with app.router.lifespan_context(app):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                yield c


async def test_snapshot_creates_and_returns_id(client):
    response = await client.post("/monitor/snapshot", json={"url": "https://example.com"})
    assert response.status_code == 200
    body = response.json()
    assert body["snapshot_id"] == "snap-001"
    assert body["url"] == "https://example.com"


async def test_check_detects_no_change(client):
    response = await client.post("/monitor/check", json={"snapshot_id": "snap-001"})
    assert response.status_code == 200
    body = response.json()
    assert body["diff"]["changed"] is False


async def test_snapshot_returns_422_without_url(client):
    response = await client.post("/monitor/snapshot", json={})
    assert response.status_code == 422
