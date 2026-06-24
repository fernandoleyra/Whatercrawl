"""
crawler/site_crawler.py — Site-wide crawl orchestration.

Provides crawl_site(), a standalone async function that drives CrawlerEngine
across all pages of a site while respecting depth, page, and domain limits.
"""

from __future__ import annotations

import asyncio
import urllib.robotparser
from urllib.parse import urlparse

import httpx

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


def _base_url(url: str) -> str:
    """Extract scheme://netloc from a URL."""
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _permissive_parser() -> urllib.robotparser.RobotFileParser:
    """Return a RobotFileParser that allows everything."""
    rp = urllib.robotparser.RobotFileParser()
    rp.parse(["User-agent: *", "Allow: /"])
    return rp


async def _fetch_robots(base_url: str) -> urllib.robotparser.RobotFileParser:
    """Fetch and parse robots.txt for a base URL. Returns a permissive parser on failure."""
    robots_url = base_url.rstrip("/") + "/robots.txt"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(robots_url)
            if resp.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(resp.text.splitlines())
                return rp
    except Exception:  # noqa: BLE001
        pass  # be permissive if robots.txt is unreachable
    return _permissive_parser()


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
    concurrency: int = 4,
) -> list[dict]:
    """Crawl an entire site starting from *url* using a concurrent worker pool.

    Args:
        engine: A CrawlerEngine instance used to crawl individual URLs.
        url: Seed URL.
        max_pages: Maximum number of pages to crawl.
        max_depth: Maximum link depth from the seed URL.
        allowed_domains: Additional domains to crawl.
        exclude_patterns: URL substrings to skip.
        concurrency: Number of pages to crawl in parallel (default 4).

    Returns:
        List of crawl result dicts (one per crawled URL).
    """
    seed_parsed = urlparse(url)
    seed_domain: str = seed_parsed.netloc

    permitted_domains: set[str] = {seed_domain}
    if allowed_domains:
        permitted_domains.update(allowed_domains)

    exclude: list[str] = exclude_patterns or []

    visited: set[str] = set()
    results: list[dict] = []
    robot_parsers: dict[str, urllib.robotparser.RobotFileParser] = {}

    async def _is_allowed(target_url: str) -> bool:
        domain = _base_url(target_url)
        if domain not in robot_parsers:
            robot_parsers[domain] = await _fetch_robots(domain)
        return robot_parsers[domain].can_fetch("*", target_url)

    # Queue entries: (url, depth)
    queue: asyncio.Queue[tuple[str, int]] = asyncio.Queue()
    await queue.put((url, 0))
    visited.add(url)

    sem = asyncio.Semaphore(concurrency)

    async def _process_one(current_url: str, depth: int) -> None:
        async with sem:
            if not await _is_allowed(current_url):
                results.append({
                    "url": current_url, "html": "", "screenshot_b64": "",
                    "status_code": 0, "error": "Blocked by robots.txt"
                })
                return

            result = await _crawl_with_retry(engine, current_url)
            results.append(result)

            if depth >= max_depth or result["error"] is not None:
                return

            links = _extract_links(result["html"], current_url)
            for link in links:
                if link in visited:
                    continue
                if len(visited) >= max_pages:
                    break
                link_domain = urlparse(link).netloc
                if link_domain not in permitted_domains:
                    continue
                if any(pat in link for pat in exclude):
                    continue
                visited.add(link)
                await queue.put((link, depth + 1))

    tasks: list[asyncio.Task] = []

    while not queue.empty() or any(not t.done() for t in tasks):
        # Drain queue into tasks up to max_pages
        while not queue.empty() and len(visited) <= max_pages:
            current_url, depth = await queue.get()
            task = asyncio.create_task(_process_one(current_url, depth))
            tasks.append(task)

        if not tasks:
            break

        # Wait for at least one task to finish before checking the queue again
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        tasks = list(pending)

        if len(results) >= max_pages:
            for t in tasks:
                t.cancel()
            break

    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)

    return results[:max_pages]
