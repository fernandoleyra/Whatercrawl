"""Unit tests for src/crawler/mapper.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock
import pytest

pytestmark = pytest.mark.asyncio

SITEMAP_XML = """<?xml version="1.0"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url><loc>https://example.com/</loc></url>
  <url><loc>https://example.com/about</loc></url>
  <url><loc>https://example.com/docs/api</loc></url>
</urlset>"""

HTML_WITH_LINKS = """<html><body>
  <a href="/page1">Page 1</a>
  <a href="https://example.com/page2">Page 2</a>
  <a href="https://other.com/external">External</a>
</body></html>"""


def _engine(sitemap_html="", page_html="", sitemap_error=None, page_error=None):
    mock = MagicMock()
    mock.crawl_url = AsyncMock(side_effect=[
        {"url": "https://example.com/sitemap.xml", "html": sitemap_html,
         "screenshot_b64": "", "status_code": 200 if not sitemap_error else 404,
         "error": sitemap_error},
        {"url": "https://example.com", "html": page_html,
         "screenshot_b64": "", "status_code": 200, "error": page_error},
    ])
    return mock


class TestMapSiteUseSitemap:
    async def test_returns_urls_from_sitemap(self):
        from src.crawler.mapper import map_site
        mock = MagicMock()
        mock.crawl_url = AsyncMock(return_value={
            "url": "https://example.com/sitemap.xml",
            "html": SITEMAP_XML, "screenshot_b64": "", "status_code": 200, "error": None,
        })
        urls = await map_site(mock, "https://example.com", max_urls=100)
        assert "https://example.com/" in urls
        assert "https://example.com/about" in urls
        assert "https://example.com/docs/api" in urls
        assert len(urls) == 3


class TestMapSiteFallsBackToLinkCrawl:
    async def test_falls_back_to_link_crawl_when_no_sitemap(self):
        from src.crawler.mapper import map_site
        mock = MagicMock()
        mock.crawl_url = AsyncMock(side_effect=[
            {"url": "https://example.com/sitemap.xml", "html": "",
             "screenshot_b64": "", "status_code": 404, "error": "404"},
            {"url": "https://example.com", "html": HTML_WITH_LINKS,
             "screenshot_b64": "", "status_code": 200, "error": None},
        ])
        urls = await map_site(mock, "https://example.com", max_urls=100)
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://other.com/external" not in urls


class TestMapSiteFiltersKeyword:
    async def test_keyword_filter_applied(self):
        from src.crawler.mapper import map_site
        mock = MagicMock()
        mock.crawl_url = AsyncMock(return_value={
            "url": "https://example.com/sitemap.xml",
            "html": SITEMAP_XML, "screenshot_b64": "", "status_code": 200, "error": None,
        })
        urls = await map_site(mock, "https://example.com", filter_keyword="docs")
        assert all("docs" in u for u in urls)
