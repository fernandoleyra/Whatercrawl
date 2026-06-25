"""
tests/conftest.py — Session-level fixture that pre-imports src.api.app so that
unittest.mock.patch("src.api.app.*") can resolve the module attribute on Python 3.14+.

In Python 3.14, mock.patch uses pkgutil.resolve_name which requires the target
module to already be an attribute of its parent package (not just in sys.modules).
"""
import importlib
import os
import sys

# Ensure the API key is present before any module import triggers StructuredExtractor init.
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")


def pytest_configure(config):
    """Pre-import src.api.app and wire it as an attribute on src.api."""
    try:
        import src.api  # noqa: F401 — ensure parent package is imported
        app_module = importlib.import_module("src.api.app")
        # Python 3.14 pkgutil.resolve_name requires the submodule to be an attribute
        # of its parent package. Set it explicitly if not already present.
        import src.api as _src_api
        if not hasattr(_src_api, "app"):
            setattr(_src_api, "app", app_module)
    except Exception:
        # If import fails, tests will surface the error themselves.
        pass
