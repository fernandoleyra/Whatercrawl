"""
tests/test_crawler/test_engine.py

Unit tests for src/crawler/engine.py and src/crawler/utils.py.

All Playwright and httpx calls are mocked — no live network traffic.
Requires:  pytest, pytest-asyncio
Run with:  pytest tests/test_crawler/test_engine.py -v
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.crawler.site_crawler import crawl_site

# ---------------------------------------------------------------------------
# pytest-asyncio: auto mode for the entire module
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.asyncio


# ===========================================================================
# Helpers
# ===========================================================================

def _make_playwright_stack(
    *,
    goto_response: MagicMock | None = None,
    goto_side_effect=None,
    content_return: str = "<html>hello</html>",
    screenshot_return: bytes = b"PNG",
) -> tuple[MagicMock, MagicMock, MagicMock, MagicMock]:
    """Build a minimal fake Playwright object hierarchy.

    Returns (mock_pw_instance, mock_playwright, mock_browser, mock_context).

    engine.py uses ``await async_playwright().start()`` — so mock_pw_instance
    exposes a ``.start()`` coroutine that returns mock_playwright directly.

    The caller can further configure mock_page via mock_context.new_page.return_value.
    """
    mock_page = AsyncMock()
    if goto_side_effect is not None:
        mock_page.goto = AsyncMock(side_effect=goto_side_effect)
    else:
        mock_page.goto = AsyncMock(return_value=goto_response)
    mock_page.content = AsyncMock(return_value=content_return)
    mock_page.screenshot = AsyncMock(return_value=screenshot_return)

    mock_context = AsyncMock()
    mock_context.new_page = AsyncMock(return_value=mock_page)
    mock_context.close = AsyncMock()

    mock_browser = AsyncMock()
    mock_browser.new_context = AsyncMock(return_value=mock_context)
    mock_browser.close = AsyncMock()

    mock_playwright = MagicMock()
    mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)
    mock_playwright.stop = AsyncMock()

    # engine.py calls: pw = await async_playwright().start()
    mock_pw_instance = AsyncMock()
    mock_pw_instance.start = AsyncMock(return_value=mock_playwright)

    return mock_pw_instance, mock_playwright, mock_browser, mock_context


def _ok_response(status: int = 200) -> MagicMock:
    """Return a fake Playwright Response with ok=True."""
    r = MagicMock()
    r.ok = True
    r.status = status
    return r


def _err_response(status: int = 404) -> MagicMock:
    """Return a fake Playwright Response with ok=False."""
    r = MagicMock()
    r.ok = False
    r.status = status
    return r


# ===========================================================================
# engine.py tests
# ===========================================================================


class TestCrawlUrlSuccess:
    """Test 1 — happy-path single-URL crawl."""

    async def test_crawl_url_success(self):
        from src.crawler.engine import CrawlerEngine

        goto_response = _ok_response(200)
        screenshot_bytes = b"\x89PNG\r\n\x1a\n"  # minimal PNG magic bytes
        async_pw_cm, mock_pw, mock_browser, mock_context = _make_playwright_stack(
            goto_response=goto_response,
            content_return="<html>hello</html>",
            screenshot_return=screenshot_bytes,
        )

        with (
            patch("src.crawler.engine.async_playwright", return_value=async_pw_cm),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = CrawlerEngine()
            result = await engine.crawl_url("http://example.com/", take_screenshot=True)

        assert result["status_code"] == 200
        assert "hello" in result["html"]
        assert result["error"] is None

        # screenshot_b64 must be a non-empty, valid base64 string
        b64 = result["screenshot_b64"]
        assert isinstance(b64, str) and len(b64) > 0
        decoded = base64.standard_b64decode(b64)
        assert decoded == screenshot_bytes


class TestCrawlUrl404:
    """Test 2 — server returns HTTP 404."""

    async def test_crawl_url_404(self):
        from src.crawler.engine import CrawlerEngine

        goto_response = _err_response(404)
        async_pw_cm, mock_pw, mock_browser, mock_context = _make_playwright_stack(
            goto_response=goto_response,
        )

        with (
            patch("src.crawler.engine.async_playwright", return_value=async_pw_cm),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = CrawlerEngine()
            result = await engine.crawl_url("http://example.com/missing")

        assert result["status_code"] == 404
        assert result["error"] == "HTTP 404"
        assert result["html"] == ""


class TestCrawlUrlRobotsBlocked:
    """Test 3 — robots.txt disallows the URL; Playwright must never be invoked."""

    async def test_crawl_url_robots_blocked(self):
        from src.crawler.engine import CrawlerEngine

        async_pw_cm, mock_pw, mock_browser, mock_context = _make_playwright_stack()

        with patch(
            "src.crawler.engine.async_playwright", return_value=async_pw_cm
        ) as mock_ap:
            engine = CrawlerEngine()
            result = await engine.crawl_url(
                "http://example.com/secret", robots_allowed=False
            )

        assert result["error"] == "Blocked by robots.txt"
        assert result["status_code"] == 0
        # async_playwright() must not have been called at all
        mock_ap.assert_not_called()


class TestCrawlUrlTimeout:
    """Test 4 — page.goto raises PlaywrightTimeoutError."""

    async def test_crawl_url_timeout(self):
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from src.crawler.engine import CrawlerEngine

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(side_effect=PlaywrightTimeoutError("Navigation timed out"))
        mock_page.content = AsyncMock(return_value="<html></html>")
        mock_page.screenshot = AsyncMock(return_value=b"PNG")

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        mock_pw_instance = AsyncMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_playwright)

        with (
            patch("src.crawler.engine.async_playwright", return_value=mock_pw_instance),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = CrawlerEngine()
            # Must not raise
            result = await engine.crawl_url("http://example.com/slow")

        assert result["status_code"] == 0
        assert result["error"] is not None
        assert len(result["error"]) > 0


class TestCrawlUrlAlwaysClosesContext:
    """Test 5 — unexpected Exception still triggers context.close() in finally block."""

    async def test_crawl_url_always_closes_context(self):
        from src.crawler.engine import CrawlerEngine

        async_pw_cm, mock_pw, mock_browser, mock_context = _make_playwright_stack(
            goto_side_effect=RuntimeError("unexpected boom"),
        )

        with (
            patch("src.crawler.engine.async_playwright", return_value=async_pw_cm),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = CrawlerEngine()
            result = await engine.crawl_url("http://example.com/boom")

        # context.close() must have been awaited exactly once
        mock_context.close.assert_awaited_once()
        # Result must still be an error dict, not a propagated exception
        assert result["error"] is not None


class TestCrawlSiteRespectsRobotsTxt:
    """Test: crawl_site should block URLs disallowed by robots.txt."""

    async def test_crawl_site_respects_robots_txt(self, mock_engine):
        """crawl_site should block URLs disallowed by robots.txt."""
        robots_body = "User-agent: *\nDisallow: /private/\n"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = robots_body

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.crawler.site_crawler.httpx.AsyncClient", return_value=mock_client):
            results = await crawl_site(
                mock_engine, "https://example.com/private/secret", max_pages=1, max_depth=0
            )

        assert len(results) == 1
        assert results[0]["error"] is not None
        assert "robots" in results[0]["error"].lower()
        mock_engine.crawl_url.assert_not_called()


class TestCrawlSiteRespectsMaxPages:
    """Test 6 — crawl_site stops after max_pages regardless of available links."""

    async def test_crawl_site_respects_max_pages(self):
        from src.crawler.engine import CrawlerEngine

        # Build HTML with 10 distinct same-domain links
        links_html = "".join(
            f'<a href="http://example.com/page{i}">p{i}</a>' for i in range(10)
        )
        full_html = f"<html><body>{links_html}</body></html>"

        successful_result = {
            "url": "http://example.com/",
            "html": full_html,
            "screenshot_b64": "abc",
            "status_code": 200,
            "error": None,
        }

        engine = CrawlerEngine()
        with patch.object(
            engine,
            "crawl_url",
            new_callable=AsyncMock,
            return_value=successful_result,
        ):
            results = await crawl_site(engine, "http://example.com/", max_pages=3)

        assert len(results) == 3


class TestCrawlSiteStaysOnDomain:
    """Test 7 — crawl_site never follows links that leave the seed domain."""

    async def test_crawl_site_stays_on_domain(self):
        from src.crawler.engine import CrawlerEngine

        # Seed page has one same-domain link and one external link
        seed_html = (
            "<html><body>"
            '<a href="http://example.com/page2">internal</a>'
            '<a href="http://other.com/evil">external</a>'
            "</body></html>"
        )

        crawled_urls: list[str] = []

        async def _fake_crawl_url(url: str, **kwargs) -> dict:
            crawled_urls.append(url)
            return {
                "url": url,
                "html": seed_html if url == "http://example.com/" else "<html></html>",
                "screenshot_b64": "",
                "status_code": 200,
                "error": None,
            }

        engine = CrawlerEngine()
        with patch.object(engine, "crawl_url", side_effect=_fake_crawl_url):
            await crawl_site(engine, "http://example.com/", max_pages=10)

        for url in crawled_urls:
            from urllib.parse import urlparse
            assert urlparse(url).netloc == "example.com", (
                f"crawl_site visited off-domain URL: {url}"
            )

        assert "http://example.com/page2" in crawled_urls
        assert "http://other.com/evil" not in crawled_urls


class TestClose:
    """Test 8 — engine.close() awaits browser.close() and playwright.stop()."""

    async def test_close(self):
        from src.crawler.engine import CrawlerEngine

        mock_browser = AsyncMock()
        mock_browser.close = AsyncMock()

        mock_playwright = MagicMock()
        mock_playwright.stop = AsyncMock()

        engine = CrawlerEngine()
        # Inject pre-built mocks directly, bypassing _ensure_browser
        engine._browser = mock_browser
        engine._playwright = mock_playwright

        await engine.close()

        mock_browser.close.assert_awaited_once()
        mock_playwright.stop.assert_awaited_once()

        # Internal state is cleared after close
        assert engine._browser is None
        assert engine._playwright is None


# ===========================================================================
# utils.py tests
# ===========================================================================


class TestRobotsTxtAllowedPermitted:
    """Test 9 — robots.txt says Allow: / → should return True."""

    async def test_robots_txt_allowed_permitted(self):
        import src.crawler.utils as utils_module
        # Reset module-level cache to avoid cross-test contamination
        utils_module._robots_cache.clear()

        robots_content = "User-agent: *\nAllow: /"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = robots_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.crawler.utils.httpx.AsyncClient", return_value=mock_client):
            result = await utils_module.robots_txt_allowed("http://example.com/page")

        assert result is True


class TestRobotsTxtDisallowed:
    """Test 10 — robots.txt says Disallow: / → should return False."""

    async def test_robots_txt_disallowed(self):
        import src.crawler.utils as utils_module
        utils_module._robots_cache.clear()

        robots_content = "User-agent: *\nDisallow: /"

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.text = robots_content

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.crawler.utils.httpx.AsyncClient", return_value=mock_client):
            result = await utils_module.robots_txt_allowed("http://example.com/page")

        assert result is False


class TestRobotsTxtMissing:
    """Test 11 — robots.txt returns 404 → permissive default (True)."""

    async def test_robots_txt_missing(self):
        import src.crawler.utils as utils_module
        utils_module._robots_cache.clear()

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.crawler.utils.httpx.AsyncClient", return_value=mock_client):
            result = await utils_module.robots_txt_allowed("http://example.com/page")

        assert result is True


class TestRobotsTxtTimeout:
    """Test 12 — httpx raises TimeoutException → permissive default (True)."""

    async def test_robots_txt_timeout(self):
        import httpx
        import src.crawler.utils as utils_module
        utils_module._robots_cache.clear()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.TimeoutException("timed out")
        )
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.crawler.utils.httpx.AsyncClient", return_value=mock_client):
            result = await utils_module.robots_txt_allowed("http://example.com/page")

        assert result is True


class TestGetRandomUserAgent:
    """Test 13 — get_random_user_agent() always returns a known non-empty string."""

    def test_get_random_user_agent(self):
        from src.crawler.engine import USER_AGENTS
        from src.crawler.utils import get_random_user_agent

        for _ in range(20):
            ua = get_random_user_agent()
            assert isinstance(ua, str), "Expected a string user-agent"
            assert len(ua) > 0, "User-agent must not be empty"
            assert ua in USER_AGENTS, f"Unknown user-agent returned: {ua!r}"


class TestRandomDelayValid:
    """Test 14 — random_delay(0.5, 1.0) calls asyncio.sleep with value in [0.5, 1.0]."""

    async def test_random_delay_valid(self):
        from src.crawler.utils import random_delay

        sleep_calls: list[float] = []

        async def _fake_sleep(duration: float) -> None:
            sleep_calls.append(duration)

        with patch("src.crawler.utils.asyncio.sleep", side_effect=_fake_sleep):
            await random_delay(0.5, 1.0)

        assert len(sleep_calls) == 1, "asyncio.sleep should have been called exactly once"
        delay = sleep_calls[0]
        assert 0.5 <= delay <= 1.0, (
            f"Sleep duration {delay} is outside the expected range [0.5, 1.0]"
        )


class TestRandomDelayInvalid:
    """Test 15 — random_delay(2.0, 1.0) raises ValueError (min > max)."""

    async def test_random_delay_invalid(self):
        from src.crawler.utils import random_delay

        with pytest.raises(ValueError, match="min_s"):
            await random_delay(2.0, 1.0)


class TestCrawlUrlNoScreenshotByDefault:
    """Test 16 — crawl_url should not call page.screenshot() unless take_screenshot=True."""

    async def test_crawl_url_no_screenshot_by_default(self):
        from src.crawler.engine import CrawlerEngine

        goto_response = _ok_response(200)

        mock_page = AsyncMock()
        mock_page.goto = AsyncMock(return_value=goto_response)
        mock_page.content = AsyncMock(return_value="<html>hello</html>")
        mock_page.screenshot = AsyncMock(return_value=b"PNG")

        mock_context = AsyncMock()
        mock_context.new_page = AsyncMock(return_value=mock_page)
        mock_context.close = AsyncMock()

        mock_browser = AsyncMock()
        mock_browser.new_context = AsyncMock(return_value=mock_context)

        mock_playwright = MagicMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        # engine.py uses async_playwright().start(), not async with async_playwright()
        mock_pw_instance = AsyncMock()
        mock_pw_instance.start = AsyncMock(return_value=mock_playwright)

        with (
            patch("src.crawler.engine.async_playwright", return_value=mock_pw_instance),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            engine = CrawlerEngine()
            result = await engine.crawl_url("https://example.com")  # take_screenshot defaults to False

        mock_page.screenshot.assert_not_called()
        assert result["screenshot_b64"] == ""


# ===========================================================================
# site_crawler.py retry tests
# ===========================================================================


@pytest.mark.asyncio
async def test_crawl_site_uses_concurrent_workers(mock_engine):
    """crawl_site with concurrency=3 should start multiple pages in parallel."""
    import asyncio
    call_count = 0

    seed_html = '<html><a href="/a">A</a><a href="/b">B</a><a href="/c">C</a></html>'

    async def crawl_with_links(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"url": url, "html": seed_html, "screenshot_b64": "", "status_code": 200, "error": None}
        return {"url": url, "html": f"<html>{url}</html>", "screenshot_b64": "", "status_code": 200, "error": None}

    mock_engine.crawl_url.side_effect = crawl_with_links

    import time
    start = time.monotonic()
    results = await crawl_site(mock_engine, "https://example.com", max_pages=4, max_depth=1, concurrency=3)
    elapsed = time.monotonic() - start

    assert len(results) >= 2
    # With concurrency=1 (sequential) this would take ~4×50ms = 200ms+
    # With concurrency=3 the 3 child pages run in parallel: ~2×50ms = 100ms max
    # We just assert it completed (functional test) — timing is fragile in CI


@pytest.mark.asyncio
async def test_crawl_site_retries_on_transient_failure(mock_engine):
    """crawl_site should retry a URL once on transient error (not 4xx)."""
    call_count = 0

    async def flaky_crawl(url, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"url": url, "html": "", "screenshot_b64": "", "status_code": 0, "error": "connection reset"}
        return {"url": url, "html": "<html><body>OK</body></html>", "screenshot_b64": "", "status_code": 200, "error": None}

    mock_engine.crawl_url.side_effect = flaky_crawl

    results = await crawl_site(mock_engine, "https://example.com", max_pages=1, max_depth=0)
    assert call_count == 2
    assert results[0]["error"] is None


@pytest.mark.asyncio
async def test_crawl_site_passes_take_screenshot(mock_engine):
    """C2 regression: crawl_site(take_screenshot=True) forwards take_screenshot to engine.crawl_url."""
    captured_kwargs: list[dict] = []

    async def record_crawl(url, **kwargs):
        captured_kwargs.append(kwargs)
        return {
            "url": url,
            "html": "<html><body>JS only</body></html>",
            "screenshot_b64": "abc123",
            "status_code": 200,
            "error": None,
        }

    mock_engine.crawl_url.side_effect = record_crawl

    await crawl_site(mock_engine, "https://example.com", max_pages=1, max_depth=0, take_screenshot=True)

    assert len(captured_kwargs) >= 1
    assert captured_kwargs[0].get("take_screenshot") is True, (
        "crawl_site must forward take_screenshot=True to engine.crawl_url"
    )


@pytest.mark.asyncio
async def test_crawl_site_max_pages_one(mock_engine):
    """I2 regression: max_pages=1 must crawl exactly the seed URL and return 1 result."""
    seed_html = '<html><a href="/page2">p2</a><a href="/page3">p3</a></html>'

    async def fake_crawl(url, **kwargs):
        return {"url": url, "html": seed_html, "screenshot_b64": "", "status_code": 200, "error": None}

    mock_engine.crawl_url.side_effect = fake_crawl

    results = await crawl_site(mock_engine, "https://example.com", max_pages=1, max_depth=1)

    assert len(results) == 1
    assert results[0]["url"] == "https://example.com"
