"""Extract all links from HTML with anchor text and surrounding context."""
from __future__ import annotations

import urllib.parse

from bs4 import BeautifulSoup


def extract_links(html: str, base_url: str) -> list[dict]:
    """
    Return all unique links from HTML with their anchor text and surrounding sentence.

    Args:
        html:     Raw HTML string.
        base_url: Used to resolve relative URLs (e.g. "https://example.com").

    Returns:
        List of dicts: {url, text, context}. Deduped by URL, sorted by URL.
    """
    soup = BeautifulSoup(html, "html.parser")
    seen: set[str] = set()
    results: list[dict] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue

        resolved = _resolve(href, base_url)
        if resolved in seen:
            continue
        seen.add(resolved)

        text = a.get_text(strip=True)
        context = _surrounding_text(a)

        results.append({"url": resolved, "text": text, "context": context})

    return sorted(results, key=lambda x: x["url"])


def _resolve(href: str, base_url: str) -> str:
    return urllib.parse.urljoin(base_url, href)


def _surrounding_text(a_tag) -> str:
    parent = a_tag.parent
    if parent is None:
        return a_tag.get_text(strip=True)
    return parent.get_text(separator=" ", strip=True)[:200]
