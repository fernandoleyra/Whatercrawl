"""
crawler/engine.py — Core Playwright crawler engine.

Provides CrawlerEngine with async methods for single-URL crawling.
Never raises — all methods return structured dicts or lists of dicts.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import random
from typing import Optional

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
    Playwright,
    Response,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TIMEOUT_MS: int = 30_000
MAX_PAGES: int = 50
MAX_DEPTH: int = 3
MIN_DELAY_S: float = 0.5
MAX_DELAY_S: float = 2.0

LAUNCH_ARGS: list[str] = [
    "--no-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
    "--disable-extensions",
]

USER_AGENTS: list[str] = [
    # Chrome on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    # Chrome on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_4) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    # Chrome on Linux
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    # Firefox on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) Gecko/20100101 Firefox/124.0",
    # Safari on macOS
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    # Edge on Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
]

# ---------------------------------------------------------------------------
# Result helpers
# ---------------------------------------------------------------------------

def _ok_result(url: str, html: str, screenshot_b64: str, status_code: int) -> dict:
    return {
        "url": url,
        "html": html,
        "screenshot_b64": screenshot_b64,
        "status_code": status_code,
        "error": None,
    }


def _err_result(url: str, status_code: int, error: str) -> dict:
    return {
        "url": url,
        "html": "",
        "screenshot_b64": "",
        "status_code": status_code,
        "error": error,
    }


# ---------------------------------------------------------------------------
# CrawlerEngine
# ---------------------------------------------------------------------------

class CrawlerEngine:
    """Async Playwright-based crawler engine.

    Manages a single shared Chromium browser instance.  Call ``close()`` when
    done to release the browser and Playwright subprocess.
    """

    def __init__(self) -> None:
        self._playwright: Optional[Playwright] = None
        self._browser: Optional[Browser] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def _ensure_browser(self) -> Browser:
        """Start Playwright and Chromium if not already running."""
        if self._browser is not None:
            return self._browser

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=LAUNCH_ARGS,
        )
        logger.info("Chromium browser launched.")
        return self._browser

    async def close(self) -> None:
        """Close the browser and stop the Playwright subprocess."""
        if self._browser is not None:
            try:
                await self._browser.close()
            except PlaywrightError as exc:
                logger.warning("Error closing browser: %s", exc)
            self._browser = None

        if self._playwright is not None:
            try:
                await self._playwright.stop()
            except PlaywrightError as exc:
                logger.warning("Error stopping Playwright: %s", exc)
            self._playwright = None

        logger.info("CrawlerEngine closed.")

    # ------------------------------------------------------------------
    # Single-URL crawl
    # ------------------------------------------------------------------

    async def crawl_url(
        self,
        url: str,
        timeout_ms: int = TIMEOUT_MS,
        robots_allowed: bool = True,
        take_screenshot: bool = False,
        full_page: bool = True,
    ) -> dict:
        """Crawl a single URL and return a structured result dict.

        Never raises — exceptions are caught and returned in the ``error`` key.

        Args:
            url: The target URL.
            timeout_ms: Navigation timeout in milliseconds.
            robots_allowed: If False, navigation is skipped and an error is
                returned immediately (robots.txt enforcement handled upstream).

        Returns:
            Dict with keys: url, html, screenshot_b64, status_code, error.
        """
        if not robots_allowed:
            return _err_result(url, 0, "Blocked by robots.txt")

        try:
            browser = await self._ensure_browser()
        except (PlaywrightError, OSError) as exc:
            logger.error("Failed to launch browser for %s: %s", url, exc)
            return _err_result(url, 0, str(exc))

        context: Optional[BrowserContext] = None
        try:
            await asyncio.sleep(random.uniform(MIN_DELAY_S, MAX_DELAY_S))

            user_agent = random.choice(USER_AGENTS)
            context = await browser.new_context(user_agent=user_agent)
            page: Page = await context.new_page()

            response: Optional[Response] = await page.goto(
                url,
                timeout=timeout_ms,
                wait_until="domcontentloaded",
            )

            status_code: int = response.status if response is not None else 0

            if response is None or not response.ok:
                return _err_result(url, status_code, f"HTTP {status_code}")

            html: str = await page.content()
            screenshot_b64 = ""
            if take_screenshot:
                screenshot_bytes: bytes = await page.screenshot(
                    full_page=full_page, type="png"
                )
                screenshot_b64 = base64.standard_b64encode(screenshot_bytes).decode(
                    "utf-8"
                )

            return _ok_result(url, html, screenshot_b64, status_code)

        except PlaywrightTimeoutError as exc:
            logger.warning("Timeout crawling %s: %s", url, exc)
            return _err_result(url, 0, str(exc))
        except PlaywrightError as exc:
            logger.warning("Playwright error crawling %s: %s", url, exc)
            return _err_result(url, 0, str(exc))
        except Exception as exc:  # noqa: BLE001 — intentional broad catch, never re-raised
            logger.error("Unexpected error crawling %s: %s", url, exc)
            return _err_result(url, 0, str(exc))
        finally:
            if context is not None:
                try:
                    await context.close()
                except PlaywrightError as exc:
                    logger.warning("Error closing context for %s: %s", url, exc)

