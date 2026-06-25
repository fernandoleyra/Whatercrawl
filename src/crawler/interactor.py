"""Execute Playwright action sequences on a page, then return content."""
from __future__ import annotations

import logging

from src.extractor.extractor import ContentExtractor

logger = logging.getLogger(__name__)

_extractor = ContentExtractor()


async def interact_and_scrape(
    engine,
    url: str,
    actions: list[dict],
    output_format: str = "markdown",
) -> dict:
    """
    Navigate to url, execute each action, then return page content.

    Action dict keys: type (click|fill|wait|scroll|press), selector, value, ms.
    Never raises — errors are returned in the 'error' key.

    Returns: {url, content, format, error}
    """
    browser = await engine._ensure_browser()
    page = await browser.new_page()
    try:
        await page.goto(url, wait_until="domcontentloaded")
        await page.wait_for_load_state("networkidle")

        for action in actions:
            action_type = action.get("type", "")
            selector = action.get("selector", "")
            value = action.get("value", "")
            ms = action.get("ms", 500)

            if action_type == "click":
                await page.click(selector)
            elif action_type == "fill":
                await page.fill(selector, value)
            elif action_type == "wait":
                await page.wait_for_timeout(ms)
            elif action_type == "scroll":
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
            elif action_type == "press":
                await page.keyboard.press(value or "Enter")

        html = await page.content()

        if output_format == "text":
            content = _extractor.extract_text(html)
        elif output_format == "html":
            content = _extractor.extract_raw(html)
        else:
            content = _extractor.extract_markdown(html)

        return {"url": url, "content": content, "format": output_format, "error": None}

    except Exception as exc:  # noqa: BLE001
        logger.error("interact_and_scrape failed for %s: %s", url, exc)
        return {"url": url, "content": "", "format": output_format, "error": str(exc)}
    finally:
        await page.close()
