"""DuckDuckGo HTML search + per-result page scraping."""
from __future__ import annotations

import asyncio
import logging
import urllib.parse

from bs4 import BeautifulSoup

from src.extractor.extractor import ContentExtractor

def _soup_text(html: str) -> str:
    """Fallback: extract all visible text via BeautifulSoup."""
    return BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)

logger = logging.getLogger(__name__)

DDGO_URL = "https://html.duckduckgo.com/html/"
_extractor = ContentExtractor()


async def search_web(
    engine,
    query: str,
    max_results: int = 5,
    output_format: str = "markdown",
    extractor=None,
) -> list[dict]:
    """
    Search DuckDuckGo HTML and scrape full content for each result URL.

    Returns a list of dicts: {url, title, snippet, content}.
    Never raises — failed pages get content="".
    """
    _ext = extractor or _extractor
    search_url = f"{DDGO_URL}?q={urllib.parse.quote_plus(query)}"
    search_result = await engine.crawl_url(search_url)

    if search_result["error"]:
        logger.warning("DuckDuckGo search failed: %s", search_result["error"])
        return []

    links = _parse_ddgo_results(search_result["html"], max_results)
    if not links:
        return []

    pages = await asyncio.gather(
        *[engine.crawl_url(item["url"]) for item in links],
        return_exceptions=False,
    )

    results = []
    for item, page in zip(links, pages):
        if page["error"]:
            content = ""
        elif output_format == "text":
            content = _ext.extract_text(page["html"]) or _soup_text(page["html"])
        else:
            content = _ext.extract_markdown(page["html"]) or _soup_text(page["html"])
        results.append({
            "url": item["url"],
            "title": item["title"],
            "snippet": item["snippet"],
            "content": content,
        })

    return results


def _parse_ddgo_results(html: str, max_results: int) -> list[dict]:
    """Parse DuckDuckGo HTML results page into a list of {url, title, snippet}."""
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for div in soup.select("div.result")[:max_results]:
        a = div.select_one("a.result__a")
        snippet_el = div.select_one("a.result__snippet")
        if not a or not a.get("href"):
            continue
        items.append({
            "url": a["href"],
            "title": a.get_text(strip=True),
            "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
        })
    return items
