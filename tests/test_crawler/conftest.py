"""
conftest.py — pytest configuration for tests/test_crawler/.

Sets asyncio_mode = "auto" so every async test function is collected and run
without needing an explicit @pytest.mark.asyncio decorator.
"""

import pytest


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
