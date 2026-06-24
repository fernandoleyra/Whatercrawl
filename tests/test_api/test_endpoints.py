"""
tests/test_api/test_endpoints.py — Pytest suite for all FastAPI endpoints in
src/api/app.py.

Strategy: patch the three class constructors (CrawlerEngine, JobStore,
ContentExtractor) inside src.api.app so the lifespan never touches Playwright,
SQLite, or the Anthropic API.  Each test is fully independent.
"""

from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure ANTHROPIC_API_KEY is set before the app module is imported/used
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Shared mock factories
# ---------------------------------------------------------------------------

def _make_mock_crawler() -> MagicMock:
    """Return a mock CrawlerEngine instance with async crawl_url."""
    mock = MagicMock()
    mock.crawl_url = AsyncMock(
        return_value={
            "url": "http://example.com",
            "html": "<p>Hello world content here</p>",
            "screenshot_b64": "abc",
            "status_code": 200,
            "error": None,
        }
    )
    mock.close = AsyncMock()
    return mock


def _make_mock_extractor() -> MagicMock:
    """Return a mock ContentExtractor instance."""
    mock = MagicMock()
    mock.extract_with_fallback = AsyncMock(return_value="# Hello\n\nworld content")
    mock.extract_text = MagicMock(return_value="Hello world content")
    mock.extract_raw = MagicMock(return_value="<p>Hello world content here</p>")
    return mock


def _make_mock_job_store() -> MagicMock:
    """Return a mock JobStore instance with async methods."""
    mock = MagicMock()
    mock.init = AsyncMock()
    mock.close = AsyncMock()
    mock.create_job = AsyncMock(return_value="test-job-123")
    mock.get_job = AsyncMock(return_value=None)
    mock.update_job = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# Fixture: async HTTP client with all external deps mocked
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """
    Build an AsyncClient backed by the FastAPI app under test.

    All three external class constructors are patched at the module level so
    the lifespan never opens a real browser, SQLite connection, or Anthropic
    session.
    """
    mock_crawler = _make_mock_crawler()
    mock_extractor = _make_mock_extractor()
    mock_job_store = _make_mock_job_store()

    mock_crawler_cls = MagicMock(return_value=mock_crawler)
    mock_extractor_cls = MagicMock(return_value=mock_extractor)
    mock_job_store_cls = MagicMock(return_value=mock_job_store)

    with (
        patch("src.api.app.CrawlerEngine", mock_crawler_cls),
        patch("src.api.app.JobStore", mock_job_store_cls),
        patch("src.api.app.ContentExtractor", mock_extractor_cls),
    ):
        from src.api.app import app  # noqa: PLC0415

        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as c:
            yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_scrape_returns_markdown(client: AsyncClient) -> None:
    """POST /scrape should return 200 with markdown content."""
    response = await client.post("/scrape", json={"url": "http://example.com"})

    assert response.status_code == 200
    body = response.json()
    assert "content" in body
    assert body["content"] == "# Hello\n\nworld content"
    assert body["format"] == "markdown"


async def test_scrape_returns_502_on_crawl_error(client: AsyncClient) -> None:
    """POST /scrape should return 502 when the crawler reports an error."""
    # Overwrite the crawler mock on app.state for this specific test
    from src.api.app import app  # noqa: PLC0415

    original = app.state.crawler.crawl_url

    app.state.crawler.crawl_url = AsyncMock(
        return_value={
            "url": "http://example.com",
            "html": "",
            "screenshot_b64": "",
            "status_code": 404,
            "error": "HTTP 404",
        }
    )

    try:
        response = await client.post("/scrape", json={"url": "http://example.com"})
        assert response.status_code == 502
    finally:
        app.state.crawler.crawl_url = original


async def test_crawl_returns_job_id(client: AsyncClient) -> None:
    """POST /crawl should return 200 with a job_id and status 'pending'."""
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.create_job = AsyncMock(return_value="test-job-123")

    response = await client.post(
        "/crawl", json={"url": "http://example.com", "max_pages": 5}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["job_id"] == "test-job-123"
    assert body["status"] == "pending"


async def test_get_crawl_status_returns_job(client: AsyncClient) -> None:
    """GET /crawl/{job_id} should return 200 with status and pages list."""
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.get_job = AsyncMock(
        return_value={
            "id": "test-job-123",
            "status": "done",
            "result": [
                {"url": "http://example.com", "content": "text", "error": None}
            ],
            "params": "{}",
            "type": "crawl",
            "error": None,
            "worker_id": None,
            "created_at": "2026-03-24T00:00:00",
            "updated_at": "2026-03-24T00:01:00",
        }
    )

    response = await client.get("/crawl/test-job-123")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "done"
    assert isinstance(body["pages"], list)


async def test_get_crawl_status_404_for_unknown(client: AsyncClient) -> None:
    """GET /crawl/{job_id} should return 404 when the job is not found."""
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.get_job = AsyncMock(return_value=None)

    response = await client.get("/crawl/nonexistent-id")

    assert response.status_code == 404


async def test_extract_returns_placeholder(client: AsyncClient) -> None:
    """POST /extract should return 200 with a 'data' field."""
    response = await client.post(
        "/extract",
        json={"url": "http://example.com", "schema": {"title": "string"}},
    )

    assert response.status_code == 200
    body = response.json()
    assert "data" in body


async def test_docs_endpoint_accessible(client: AsyncClient) -> None:
    """GET /docs should return 200 (OpenAPI Swagger UI is served)."""
    response = await client.get("/docs")

    assert response.status_code == 200
