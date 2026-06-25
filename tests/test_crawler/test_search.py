"""Unit tests for src/crawler/search.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

pytestmark = pytest.mark.asyncio

DDGO_HTML = """
<html><body>
<div class="result">
  <a class="result__a" href="https://example.com/page1">Example Title 1</a>
  <a class="result__snippet">A snippet about the result one.</a>
</div>
<div class="result">
  <a class="result__a" href="https://example.com/page2">Example Title 2</a>
  <a class="result__snippet">A snippet about result two.</a>
</div>
</body></html>
"""


def _make_engine(html: str = "<p>Article content here with words</p>", error=None):
    mock = MagicMock()
    mock.crawl_url = AsyncMock(return_value={
        "url": "https://example.com",
        "html": html,
        "screenshot_b64": "",
        "status_code": 200,
        "error": error,
    })
    return mock


class TestSearchWebReturnsResults:
    async def test_returns_list_of_results(self):
        from src.crawler.search import search_web
        engine = _make_engine()
        engine.crawl_url = AsyncMock(side_effect=[
            {"url": "https://html.duckduckgo.com/html/", "html": DDGO_HTML,
             "screenshot_b64": "", "status_code": 200, "error": None},
            {"url": "https://example.com/page1", "html": "<p>" + "word " * 30 + "</p>",
             "screenshot_b64": "", "status_code": 200, "error": None},
            {"url": "https://example.com/page2", "html": "<p>" + "word " * 30 + "</p>",
             "screenshot_b64": "", "status_code": 200, "error": None},
        ])
        results = await search_web(engine, "test query", max_results=2)
        assert len(results) == 2
        assert results[0]["url"] == "https://example.com/page1"
        assert results[0]["title"] == "Example Title 1"
        assert isinstance(results[0]["content"], str)


class TestSearchWebSkipsErroredPages:
    async def test_errored_page_gets_empty_content(self):
        from src.crawler.search import search_web
        engine = MagicMock()
        engine.crawl_url = AsyncMock(side_effect=[
            {"url": "https://html.duckduckgo.com/html/", "html": DDGO_HTML,
             "screenshot_b64": "", "status_code": 200, "error": None},
            {"url": "https://example.com/page1", "html": "", "screenshot_b64": "",
             "status_code": 0, "error": "connection refused"},
            {"url": "https://example.com/page2", "html": "<p>" + "word " * 30 + "</p>",
             "screenshot_b64": "", "status_code": 200, "error": None},
        ])
        results = await search_web(engine, "query", max_results=2)
        assert results[0]["content"] == ""
        assert results[1]["content"] != ""
