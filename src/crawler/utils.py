"""
crawler/utils.py — Crawler utility functions.

Provides robots.txt checking, random user-agent selection, and polite delay helpers.
"""

from __future__ import annotations

import asyncio
import logging
import random
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from src.crawler.engine import USER_AGENTS

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ROBOTS_FETCH_TIMEOUT_S: float = 5.0

# ---------------------------------------------------------------------------
# Module-level cache
# ---------------------------------------------------------------------------

_robots_cache: dict[str, RobotFileParser] = {}

# ---------------------------------------------------------------------------
# Public functions
# ---------------------------------------------------------------------------


async def robots_txt_allowed(url: str, user_agent: str = "*") -> bool:
    """Check whether *url* is allowed for *user_agent* per the domain's robots.txt.

    Fetches and parses robots.txt once per domain, caching the result for
    subsequent calls.  Returns True (permissive) when robots.txt is absent,
    unreachable, times out, or is malformed.

    Args:
        url: The target URL to check.
        user_agent: The user-agent token to check against (default ``"*"``).

    Returns:
        True if crawling is allowed or robots.txt cannot be retrieved,
        False if explicitly disallowed.
    """
    parsed = urlparse(url)
    domain_key = f"{parsed.scheme}://{parsed.netloc}"

    if domain_key not in _robots_cache:
        robots_url = f"{domain_key}/robots.txt"
        rp = RobotFileParser()
        rp.set_url(robots_url)

        try:
            async with httpx.AsyncClient(timeout=ROBOTS_FETCH_TIMEOUT_S) as client:
                response = await client.get(robots_url)

            if response.status_code == 404:
                logger.debug("robots.txt not found for %s — allowing", domain_key)
                rp.allow_all = True
            else:
                response.raise_for_status()
                rp.parse(response.text.splitlines())

        except httpx.TimeoutException:
            logger.debug("Timeout fetching robots.txt for %s — allowing", domain_key)
            rp.allow_all = True
        except httpx.HTTPStatusError:
            logger.debug(
                "HTTP error fetching robots.txt for %s — allowing", domain_key
            )
            rp.allow_all = True
        except httpx.HTTPError as exc:
            logger.debug(
                "Connection error fetching robots.txt for %s: %s — allowing",
                domain_key,
                exc,
            )
            rp.allow_all = True
        except ValueError as exc:
            logger.debug(
                "Malformed robots.txt for %s: %s — allowing", domain_key, exc
            )
            rp.allow_all = True

        _robots_cache[domain_key] = rp

    rp = _robots_cache[domain_key]
    return rp.can_fetch(user_agent, url)


def get_random_user_agent() -> str:
    """Return a random user-agent string from the shared USER_AGENTS list.

    Returns:
        A randomly selected realistic browser user-agent string.
    """
    return random.choice(USER_AGENTS)


async def random_delay(min_s: float = 0.5, max_s: float = 2.0) -> None:
    """Await a random delay between *min_s* and *max_s* seconds.

    Args:
        min_s: Minimum sleep duration in seconds (inclusive).
        max_s: Maximum sleep duration in seconds (inclusive).

    Raises:
        ValueError: If *min_s* is greater than *max_s*.
    """
    if min_s > max_s:
        raise ValueError(
            f"min_s ({min_s}) must be less than or equal to max_s ({max_s})"
        )
    delay = random.uniform(min_s, max_s)
    await asyncio.sleep(delay)


def _extract_links(html: str, base_url: str) -> list[str]:
    """Extract and resolve href links from raw HTML.

    Uses a simple string-based approach to avoid a BeautifulSoup dependency
    inside this module.  Returns deduplicated absolute URLs with fragments
    stripped.
    """
    from html.parser import HTMLParser
    from typing import Optional

    class _LinkParser(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.hrefs: list[str] = []

        def handle_starttag(
            self, tag: str, attrs: list[tuple[str, Optional[str]]]
        ) -> None:
            if tag == "a":
                for attr_name, attr_value in attrs:
                    if attr_name == "href" and attr_value:
                        self.hrefs.append(attr_value)

    parser = _LinkParser()
    try:
        parser.feed(html)
    except Exception as exc:  # noqa: BLE001
        logger.debug("HTML parse error extracting links from %s: %s", base_url, exc)

    seen: set[str] = set()
    result: list[str] = []
    for href in parser.hrefs:
        if href.startswith(("mailto:", "tel:", "javascript:")):
            continue
        absolute = urljoin(base_url, href).split("#")[0]
        parsed = urlparse(absolute)
        if parsed.scheme not in ("http", "https"):
            continue
        if absolute not in seen:
            seen.add(absolute)
            result.append(absolute)

    return result
