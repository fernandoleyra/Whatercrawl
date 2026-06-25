"""
tests/test_extractor/test_extractor.py

Unit tests for src/extractor/extractor.py.

All trafilatura and Anthropic API calls are mocked — no live network traffic.
Requires:  pytest, pytest-asyncio
Run with:  pytest tests/test_extractor/test_extractor.py -v
"""

from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# pytest-asyncio: auto mode for the entire module
# ---------------------------------------------------------------------------
pytestmark = pytest.mark.asyncio


# ===========================================================================
# Helpers
# ===========================================================================

def _make_extractor(api_key: str = "test-key") -> "ContentExtractor":
    """Instantiate ContentExtractor with a dummy API key injected into env."""
    from src.extractor.extractor import ContentExtractor

    with patch.dict(os.environ, {"ANTHROPIC_API_KEY": api_key}):
        extractor = ContentExtractor()
    return extractor


def _words(n: int) -> str:
    """Return a string containing exactly *n* whitespace-separated words."""
    return " ".join(f"word{i}" for i in range(n))


# ===========================================================================
# Test 1 — extract_markdown returns content when trafilatura succeeds
# ===========================================================================


class TestExtractMarkdownReturnsContent:
    """Test 1 — extract_markdown returns non-empty string for 30+ word output."""

    def test_extract_markdown_returns_content(self):
        extractor = _make_extractor()
        long_text = _words(35)  # 35 words — above MIN_WORD_COUNT=20

        with patch("src.extractor.extractor.trafilatura.extract", return_value=long_text):
            result = extractor.extract_markdown("<html>...</html>")

        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# Test 2 — extract_markdown returns "" for short content (below MIN_WORD_COUNT)
# ===========================================================================


class TestExtractMarkdownReturnsEmptyOnShortContent:
    """Test 2 — extract_markdown returns "" when word count is below threshold."""

    def test_extract_markdown_returns_empty_on_short_content(self):
        extractor = _make_extractor()
        short_text = _words(5)  # 5 words — below MIN_WORD_COUNT=20

        with patch("src.extractor.extractor.trafilatura.extract", return_value=short_text):
            result = extractor.extract_markdown("<html>...</html>")

        assert result == ""


# ===========================================================================
# Test 3 — extract_markdown returns "" when trafilatura returns None
# ===========================================================================


class TestExtractMarkdownReturnsEmptyOnNone:
    """Test 3 — extract_markdown returns "" when trafilatura returns None."""

    def test_extract_markdown_returns_empty_on_none(self):
        extractor = _make_extractor()

        with patch("src.extractor.extractor.trafilatura.extract", return_value=None):
            result = extractor.extract_markdown("<html>...</html>")

        assert result == ""


# ===========================================================================
# Test 4 — extract_text returns content when trafilatura succeeds
# ===========================================================================


class TestExtractTextReturnsContent:
    """Test 4 — extract_text returns non-empty string for 25+ word output."""

    def test_extract_text_returns_content(self):
        extractor = _make_extractor()
        text = _words(25)  # 25 words — sufficiently long

        with patch("src.extractor.extractor.trafilatura.extract", return_value=text):
            result = extractor.extract_text("<html>...</html>")

        assert isinstance(result, str)
        assert len(result) > 0


# ===========================================================================
# Test 5 — extract_raw strips noise tags but preserves real content
# ===========================================================================


class TestExtractRawStripsNoiseTags:
    """Test 5 — extract_raw removes nav/footer/script/style/aside but keeps <p>."""

    def test_extract_raw_strips_noise_tags(self):
        extractor = _make_extractor()

        html = (
            "<html><body>"
            "<nav>Navigation Menu</nav>"
            "<footer>Footer Content</footer>"
            "<script>alert('js');</script>"
            "<style>.hidden { display: none; }</style>"
            "<aside>Sidebar Aside</aside>"
            "<p>Real article paragraph content here.</p>"
            "</body></html>"
        )

        result = extractor.extract_raw(html)

        # Noise tag text must NOT appear in the output
        assert "Navigation Menu" not in result
        assert "Footer Content" not in result
        assert "alert('js');" not in result
        assert ".hidden" not in result
        assert "Sidebar Aside" not in result

        # Real paragraph content MUST be preserved
        assert "Real article paragraph content here." in result


# ===========================================================================
# Test 6 — vision_fallback returns markdown from Claude API response
# ===========================================================================


class TestVisionFallbackReturnsMarkdown:
    """Test 6 — vision_fallback returns text from a mocked Claude response."""

    async def test_vision_fallback_returns_markdown(self):
        mock_block = MagicMock()
        mock_block.type = "text"
        mock_block.text = "# Hello\nSome content"

        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(return_value=mock_response)

        mock_client_instance = MagicMock()
        mock_client_instance.messages = mock_messages

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("src.extractor.extractor.anthropic.AsyncAnthropic", return_value=mock_client_instance),
        ):
            from src.extractor.extractor import ContentExtractor

            extractor = ContentExtractor()
            result = await extractor.vision_fallback("base64data")

        assert result == "# Hello\nSome content"


# ===========================================================================
# Test 7 — vision_fallback returns "" when the API raises APIError
# ===========================================================================


class TestVisionFallbackReturnsEmptyOnApiError:
    """Test 7 — vision_fallback swallows APIError and returns ""."""

    async def test_vision_fallback_returns_empty_on_api_error(self):
        import httpx
        import anthropic as anthropic_lib

        # Construct a real anthropic.APIError instance using a mock httpx.Request
        fake_request = MagicMock(spec=httpx.Request)
        api_error = anthropic_lib.APIError(
            message="simulated API error",
            request=fake_request,
            body=None,
        )

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=api_error)

        mock_client_instance = MagicMock()
        mock_client_instance.messages = mock_messages

        with (
            patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
            patch("src.extractor.extractor.anthropic.AsyncAnthropic", return_value=mock_client_instance),
        ):
            from src.extractor.extractor import ContentExtractor

            extractor = ContentExtractor()
            result = await extractor.vision_fallback("base64data")

        assert result == ""


# ===========================================================================
# Test 8 — extract_with_fallback uses DOM result when it is sufficient
# ===========================================================================


class TestExtractWithFallbackUsesDomWhenSufficient:
    """Test 8 — extract_with_fallback returns DOM result and never calls vision_fallback."""

    async def test_extract_with_fallback_uses_dom_when_sufficient(self):
        extractor = _make_extractor()
        dom_content = _words(30)

        with (
            patch.object(extractor, "extract_markdown", return_value=dom_content),
            patch.object(extractor, "vision_fallback", new_callable=AsyncMock) as mock_vision,
        ):
            result = await extractor.extract_with_fallback("<html>...</html>", "screenshot_b64")

        assert result == dom_content
        assert mock_vision.call_count == 0


# ===========================================================================
# Test 9 — extract_with_fallback uses vision when DOM extraction is empty
# ===========================================================================


class TestExtractWithFallbackUsesVisionWhenDomEmpty:
    """Test 9 — extract_with_fallback calls vision_fallback when extract_markdown returns ""."""

    async def test_extract_with_fallback_uses_vision_when_dom_empty(self):
        extractor = _make_extractor()

        with (
            patch.object(extractor, "extract_markdown", return_value=""),
            patch.object(
                extractor,
                "vision_fallback",
                new_callable=AsyncMock,
                return_value="# Vision result",
            ),
        ):
            result = await extractor.extract_with_fallback("<html>...</html>", "screenshot_b64")

        assert result == "# Vision result"


# ===========================================================================
# Test 10 — missing ANTHROPIC_API_KEY raises EnvironmentError at init time
# ===========================================================================


class TestMissingApiKeyRaisesOnInit:
    """Test 10 — ContentExtractor raises EnvironmentError when API key is absent."""

    def test_missing_api_key_raises_on_init(self):
        from src.extractor.extractor import ContentExtractor

        # Ensure the key is absent for this test
        env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        with patch.dict(os.environ, env_without_key, clear=True):
            with pytest.raises(EnvironmentError):
                ContentExtractor()
