"""Unit tests for src/extractor/links.py."""
from __future__ import annotations
import pytest


class TestExtractLinksBasic:
    def test_returns_link_with_text(self):
        from src.extractor.links import extract_links
        html = "<html><body><p>See <a href='https://example.com/about'>About us</a> here.</p></body></html>"
        links = extract_links(html, "https://example.com")
        assert len(links) == 1
        assert links[0]["url"] == "https://example.com/about"
        assert links[0]["text"] == "About us"
        assert "About us" in links[0]["context"]


class TestExtractLinksRelative:
    def test_resolves_relative_links(self):
        from src.extractor.links import extract_links
        html = "<html><body><a href='/docs'>Docs</a></body></html>"
        links = extract_links(html, "https://example.com")
        assert links[0]["url"] == "https://example.com/docs"


class TestExtractLinksSkipsEmpty:
    def test_skips_anchors_without_href(self):
        from src.extractor.links import extract_links
        html = "<html><body><a>No href</a><a href=''>Empty</a><a href='#section'>Hash</a></body></html>"
        links = extract_links(html, "https://example.com")
        assert all(not u["url"].startswith("#") and u["url"] for u in links)


class TestExtractLinksDeduplicates:
    def test_deduplicates_same_url(self):
        from src.extractor.links import extract_links
        html = "<html><body><a href='https://example.com/page'>P</a><a href='https://example.com/page'>P2</a></body></html>"
        links = extract_links(html, "https://example.com")
        urls = [l["url"] for l in links]
        assert len(urls) == len(set(urls))
