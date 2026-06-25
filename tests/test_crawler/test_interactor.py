"""Unit tests for src/crawler/interactor.py."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
import pytest

pytestmark = pytest.mark.asyncio


def _make_mock_page(html: str = "<p>" + "word " * 30 + "</p>"):
    page = MagicMock()
    page.goto = AsyncMock()
    page.wait_for_load_state = AsyncMock()
    page.click = AsyncMock()
    page.fill = AsyncMock()
    page.wait_for_timeout = AsyncMock()
    page.evaluate = AsyncMock()
    page.keyboard = MagicMock()
    page.keyboard.press = AsyncMock()
    page.content = AsyncMock(return_value=html)
    page.close = AsyncMock()
    return page


def _make_engine(page):
    browser = MagicMock()
    browser.new_page = AsyncMock(return_value=page)
    engine = MagicMock()
    engine._ensure_browser = AsyncMock(return_value=browser)
    return engine


class TestInteractAndScrapeClick:
    async def test_click_action_is_called(self):
        from src.crawler.interactor import interact_and_scrape
        page = _make_mock_page()
        engine = _make_engine(page)
        actions = [{"type": "click", "selector": "button.submit", "value": "", "ms": 0}]
        await interact_and_scrape(engine, "https://example.com", actions)
        page.click.assert_called_once_with("button.submit")


class TestInteractAndScrapeFill:
    async def test_fill_action_is_called(self):
        from src.crawler.interactor import interact_and_scrape
        page = _make_mock_page()
        engine = _make_engine(page)
        actions = [{"type": "fill", "selector": "input#email", "value": "a@b.com", "ms": 0}]
        await interact_and_scrape(engine, "https://example.com", actions)
        page.fill.assert_called_once_with("input#email", "a@b.com")


class TestInteractAndScrapeReturnsContent:
    async def test_returns_markdown_content(self):
        from src.crawler.interactor import interact_and_scrape
        page = _make_mock_page("<p>" + "word " * 30 + "</p>")
        engine = _make_engine(page)
        result = await interact_and_scrape(engine, "https://example.com", [])
        assert isinstance(result["content"], str)
        assert result["url"] == "https://example.com"
