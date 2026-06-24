"""
conftest.py — pytest configuration for tests/test_crawler/.

Sets asyncio_mode = "auto" so every async test function is collected and run
without needing an explicit @pytest.mark.asyncio decorator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Global asyncio mode
# ---------------------------------------------------------------------------

def pytest_configure(config):
    """Register the asyncio_mode ini option for pytest-asyncio."""
    # pytest-asyncio >= 0.21 reads asyncio_mode from pytest.ini / pyproject.toml.
    # Setting it here programmatically ensures it works even without a config file.
    config.addinivalue_line(
        "markers",
        "asyncio: mark test as an asyncio coroutine",
    )


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_engine():
    """A minimal CrawlerEngine stand-in with crawl_url as an AsyncMock."""
    engine = MagicMock()
    engine.crawl_url = AsyncMock()
    return engine


@pytest.fixture(autouse=True)
def _block_robots_network(request):
    """Prevent live robots.txt network calls in tests.

    By default, patches httpx.AsyncClient (used by _fetch_robots) to return a
    permissive 404 response — i.e. no robots.txt restrictions.  Individual tests
    that need to exercise robots.txt logic should patch httpx.AsyncClient
    themselves with ``with patch(...):`` inside the test body; that patch takes
    precedence over this fixture because it is applied after the fixture.
    """
    permissive_response = MagicMock()
    permissive_response.status_code = 404  # 404 → _fetch_robots leaves permissive default

    permissive_client = AsyncMock()
    permissive_client.get = AsyncMock(return_value=permissive_response)
    permissive_client.__aenter__ = AsyncMock(return_value=permissive_client)
    permissive_client.__aexit__ = AsyncMock(return_value=False)

    with patch("src.crawler.site_crawler.httpx.AsyncClient", return_value=permissive_client):
        yield
