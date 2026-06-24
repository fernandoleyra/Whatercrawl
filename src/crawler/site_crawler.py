"""
crawler/site_crawler.py — Site-wide crawl orchestration.

Provides crawl_site(), a standalone async function that drives CrawlerEngine
across all pages of a site while respecting depth, page, and domain limits.
"""

from __future__ import annotations

import asyncio
from urllib.parse import urlparse

from src.crawler.engine import CrawlerEngine, MAX_PAGES, MAX_DEPTH
from src.crawler.utils import _extract_links

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _is_retryable(result: dict) -> bool:
    """Return True if the error is transient and worth retrying."""
    if result["error"] is None:
        return False
    # HTTP 4xx means the page doesn't exist — don't retry
    if result["status_code"] and 400 <= result["status_code"] < 500:
        return False
    return True


async def _crawl_with_retry(engine: "CrawlerEngine", url: str, max_attempts: int = 2) -> dict:
    """Attempt to crawl url up to max_attempts times; return last result on all failures."""
    result = await engine.crawl_url(url)
    if not _is_retryable(result):
        return result
    await asyncio.sleep(1.0)
    return await engine.crawl_url(url)


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------


async def crawl_site(
    engine: CrawlerEngine,
    url: str,
    max_pages: int = MAX_PAGES,
    max_depth: int = MAX_DEPTH,
    allowed_domains: list[str] | None = None,
    exclude_patterns: list[str] | None = None,
) -> list[dict]:
    """Crawl an entire site starting from *url*.

    Follows href links found on each page while respecting depth and page
    limits.  Only links belonging to the same domain (or *allowed_domains*)
    are followed.

    Args:
        engine: A CrawlerEngine instance used to crawl individual URLs.
        url: Seed URL.
        max_pages: Maximum number of pages to crawl.
        max_depth: Maximum link depth from the seed URL.
        allowed_domains: Additional domains to crawl.  If None, only the
            seed domain is followed.
        exclude_patterns: URL substrings; any link containing one of these
            strings is skipped.

    Returns:
        List of crawl_url result dicts (one per crawled URL).
    """
    seed_parsed = urlparse(url)
    seed_domain: str = seed_parsed.netloc

    permitted_domains: set[str] = {seed_domain}
    if allowed_domains:
        permitted_domains.update(allowed_domains)

    exclude: list[str] = exclude_patterns or []

    visited: set[str] = set()
    results: list[dict] = []

    # Queue entries: (url, depth)
    queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
    await queue.put((url, 0))

    while not queue.empty() and len(results) < max_pages:
        current_url, depth = await queue.get()

        if current_url in visited:
            continue
        visited.add(current_url)

        result = await _crawl_with_retry(engine, current_url)
        results.append(result)

        if depth >= max_depth or result["error"] is not None:
            continue

        links = _extract_links(result["html"], current_url)
        for link in links:
            if link in visited:
                continue
            if len(visited) + queue.qsize() >= max_pages:
                break

            link_domain = urlparse(link).netloc
            if link_domain not in permitted_domains:
                continue
            if any(pat in link for pat in exclude):
                continue

            await queue.put((link, depth + 1))

    return results
