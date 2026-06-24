"""
conftest.py — pytest configuration for tests/test_crawler/.

Sets asyncio_mode = "auto" so every async test function is collected and run
without needing an explicit @pytest.mark.asyncio decorator.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


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
