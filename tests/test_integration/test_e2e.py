"""
tests/test_integration/test_e2e.py — End-to-end integration tests for the
full Webcrawl API flow.

Strategy: start the FastAPI app in-process using httpx.AsyncClient backed by
ASGITransport.  All external calls (Playwright via CrawlerEngine, SQLite via
JobStore, Claude API via ContentExtractor) are mocked at the constructor level,
matching the same pattern used in test_endpoints.py.

Each test is fully independent.
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Ensure ANTHROPIC_API_KEY is present before the app module is loaded.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Mock factories
# ---------------------------------------------------------------------------


def _make_mock_crawler() -> MagicMock:
    """Return a mock CrawlerEngine with a successful async crawl_url."""
    mock = MagicMock()
    mock.crawl_url = AsyncMock(
        return_value={
            "url": "http://example.com",
            "html": "<p>Test content here with enough words to pass</p>",
            "screenshot_b64": "abc123",
            "status_code": 200,
            "error": None,
        }
    )
    mock.close = AsyncMock()
    return mock


def _make_mock_extractor() -> MagicMock:
    """Return a mock ContentExtractor."""
    mock = MagicMock()
    mock.extract_with_fallback = AsyncMock(
        return_value="# Test\n\nContent here with enough words"
    )
    mock.extract_text = MagicMock(return_value="Test content here with enough words")
    mock.extract_raw = MagicMock(
        return_value="<p>Test content here with enough words to pass</p>"
    )
    return mock


def _make_mock_job_store() -> MagicMock:
    """Return a mock JobStore with async methods."""
    mock = MagicMock()
    mock.init = AsyncMock()
    mock.close = AsyncMock()
    mock.create_job = AsyncMock(return_value="e2e-job-001")
    mock.get_job = AsyncMock(return_value=None)
    mock.update_job = AsyncMock()
    return mock


# ---------------------------------------------------------------------------
# Shared async client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
async def client():
    """
    Build a single AsyncClient backed by the FastAPI app under test.

    All three external class constructors are patched at the module level so
    the lifespan never opens a real browser, SQLite connection, or Anthropic
    session.  The same client instance is shared across all tests that request
    this fixture.
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


async def test_e2e_scrape_full_flow(client: AsyncClient) -> None:
    """
    Full scrape flow: mock crawler + extractor, POST /scrape, verify shape.

    Expected response keys: url, content, format, crawled_at.
    content must be non-empty; format must equal "markdown".
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.crawler.crawl_url = AsyncMock(
        return_value={
            "url": "http://example.com",
            "html": "<p>Test content here with enough words to pass</p>",
            "screenshot_b64": "abc123",
            "status_code": 200,
            "error": None,
        }
    )
    app.state.extractor.extract_with_fallback = AsyncMock(
        return_value="# Test\n\nContent here with enough words"
    )

    response = await client.post("/scrape", json={"url": "http://example.com"})

    assert response.status_code == 200
    body = response.json()

    # Shape validation — all required keys must be present
    assert "url" in body
    assert "content" in body
    assert "format" in body
    assert "crawled_at" in body

    # Type validation
    assert isinstance(body["url"], str)
    assert isinstance(body["content"], str)
    assert isinstance(body["format"], str)
    assert isinstance(body["crawled_at"], str)

    # Value validation
    assert body["content"] != "", "content must be non-empty"
    assert body["format"] == "markdown"


async def test_e2e_crawl_full_flow(client: AsyncClient) -> None:
    """
    Full crawl submission flow: mock job_store.create_job, POST /crawl,
    verify job_id and status shape.
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.create_job = AsyncMock(return_value="e2e-job-001")

    response = await client.post(
        "/crawl", json={"url": "http://example.com", "max_pages": 1}
    )

    assert response.status_code == 200
    body = response.json()

    # Shape validation
    assert "job_id" in body
    assert "status" in body

    # Type validation
    assert isinstance(body["job_id"], str)
    assert isinstance(body["status"], str)

    # Value validation
    assert body["job_id"] == "e2e-job-001"
    assert body["status"] == "pending"


async def test_e2e_poll_crawl_status(client: AsyncClient) -> None:
    """
    Polling a completed crawl job: mock job_store.get_job returning a done
    job, GET /crawl/e2e-job-001, verify status and pages shape.
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.get_job = AsyncMock(
        return_value={
            "id": "e2e-job-001",
            "status": "done",
            "result": [
                {"url": "http://example.com", "content": "page text", "error": None}
            ],
            "params": "{}",
            "type": "crawl",
            "error": None,
            "worker_id": None,
            "created_at": "2026-03-24",
            "updated_at": "2026-03-24",
        }
    )

    response = await client.get("/crawl/e2e-job-001")

    assert response.status_code == 200
    body = response.json()

    # Shape validation
    assert "job_id" in body
    assert "status" in body
    assert "pages" in body

    # Type validation
    assert isinstance(body["status"], str)
    assert isinstance(body["pages"], list)

    # Value validation
    assert body["status"] == "done"
    assert len(body["pages"]) == 1
    assert "url" in body["pages"][0]


async def test_e2e_extract_returns_data(client: AsyncClient) -> None:
    """
    Structured extraction flow: mock crawler returning a success result,
    POST /extract, verify response has a "data" dict field.
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.crawler.crawl_url = AsyncMock(
        return_value={
            "url": "http://example.com",
            "html": "<p>Test content here with enough words to pass</p>",
            "screenshot_b64": "abc123",
            "status_code": 200,
            "error": None,
        }
    )

    response = await client.post(
        "/extract",
        json={
            "url": "http://example.com",
            "schema": {"title": "string", "price": "number"},
        },
    )

    assert response.status_code == 200
    body = response.json()

    # Shape validation
    assert "data" in body

    # Type validation
    assert isinstance(body["data"], dict), "data field must be a dict"


async def test_e2e_scrape_error_propagation(client: AsyncClient) -> None:
    """
    Error propagation: when crawler returns an error result for a dead URL,
    POST /scrape must return HTTP 502.
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.crawler.crawl_url = AsyncMock(
        return_value={
            "url": "http://dead.example.com",
            "html": "",
            "screenshot_b64": "",
            "status_code": 0,
            "error": "connection refused",
        }
    )

    response = await client.post(
        "/scrape", json={"url": "http://dead.example.com"}
    )

    assert response.status_code == 502


async def test_e2e_unknown_job_returns_404(client: AsyncClient) -> None:
    """
    Unknown job ID: when job_store.get_job returns None,
    GET /crawl/does-not-exist must return HTTP 404.
    """
    from src.api.app import app  # noqa: PLC0415

    app.state.job_store.get_job = AsyncMock(return_value=None)

    response = await client.get("/crawl/does-not-exist")

    assert response.status_code == 404
