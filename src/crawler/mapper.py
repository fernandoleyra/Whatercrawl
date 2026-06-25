"""Site URL discovery: sitemap.xml first, link-crawl fallback."""
from __future__ import annotations

import logging
import urllib.parse

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


async def map_site(
    engine,
    url: str,
    max_urls: int = 200,
    filter_keyword: str = "",
) -> list[str]:
    """
    Return all URLs found on a domain, up to max_urls.

    Strategy:
      1. Fetch <root>/sitemap.xml — parse <loc> tags.
      2. If sitemap is empty/missing, scrape the root page and collect same-domain links.

    Args:
        engine:         CrawlerEngine instance.
        url:            Root URL of the site (e.g. "https://example.com").
        max_urls:       Maximum number of URLs to return.
        filter_keyword: If non-empty, only return URLs containing this string.

    Returns:
        Sorted list of unique URLs.
    """
    origin = _origin(url)
    sitemap_url = f"{origin}/sitemap.xml"

    result = await engine.crawl_url(sitemap_url)
    urls = _parse_sitemap(result["html"]) if not result["error"] else []

    if not urls:
        logger.debug("No sitemap — falling back to link crawl of %s", url)
        page = await engine.crawl_url(url)
        if not page["error"]:
            urls = _extract_same_domain_links(page["html"], origin)

    if filter_keyword:
        urls = [u for u in urls if filter_keyword in u]

    return sorted(set(urls))[:max_urls]


def _origin(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}"


def _parse_sitemap(html: str) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    return [tag.get_text(strip=True) for tag in soup.find_all("loc")]


def _extract_same_domain_links(html: str, origin: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if href.startswith("/"):
            href = origin + href
        if href.startswith(origin):
            urls.append(href)
    return urls
