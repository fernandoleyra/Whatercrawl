"""
tests/test_extractor/test_structured.py

Unit tests for:
  - src/extractor/structured.py  (StructuredExtractor, tests 1-6)
  - src/crawler/selector_healer.py  (SelectorHealer, tests 7-12)

All Anthropic API calls are mocked — no live network traffic.
Requires: pytest, pytest-asyncio
Run with: pytest tests/test_extractor/test_structured.py -v
"""

from __future__ import annotations

import json
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

def _make_mock_client(response_text: str) -> MagicMock:
    """Build a mock AsyncAnthropic client whose messages.create returns
    a response with content[0].text == response_text."""
    mock_content_block = MagicMock()
    mock_content_block.text = response_text

    mock_response = MagicMock()
    mock_response.content = [mock_content_block]

    mock_messages = AsyncMock()
    mock_messages.create = AsyncMock(return_value=mock_response)

    mock_client = MagicMock()
    mock_client.messages = mock_messages

    return mock_client


def _make_structured_extractor(mock_client: MagicMock) -> "StructuredExtractor":
    """Instantiate StructuredExtractor with a dummy API key and mocked client."""
    from src.extractor.structured import StructuredExtractor

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("src.extractor.structured.anthropic.AsyncAnthropic", return_value=mock_client),
    ):
        extractor = StructuredExtractor()
    return extractor


def _make_selector_healer(mock_client: MagicMock, audit_log_path: str) -> "SelectorHealer":
    """Instantiate SelectorHealer with a dummy API key and mocked client."""
    from src.crawler.selector_healer import SelectorHealer

    with (
        patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}),
        patch("src.crawler.selector_healer.anthropic.AsyncAnthropic", return_value=mock_client),
    ):
        healer = SelectorHealer(audit_log_path=audit_log_path)
    return healer


SIMPLE_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "price": {"type": "number"},
    },
    "required": ["title", "price"],
}

SAMPLE_HTML = "<html><body><h1>Widget</h1><span>$9.99</span></body></html>"


# ===========================================================================
# Test 1 — extract returns valid dict
# ===========================================================================


class TestExtractReturnsValidDict:
    """Test 1 — extract returns the parsed dict when Claude returns valid JSON."""

    async def test_extract_returns_valid_dict(self):
        mock_client = _make_mock_client('{"title": "Widget", "price": 9.99}')
        extractor = _make_structured_extractor(mock_client)

        result = await extractor.extract(SAMPLE_HTML, SIMPLE_SCHEMA)

        assert result == {"title": "Widget", "price": 9.99}


# ===========================================================================
# Test 2 — extract retries on validation failure
# ===========================================================================


class TestExtractRetriesOnValidationFailure:
    """Test 2 — extract retries once when first response fails schema validation."""

    async def test_extract_retries_on_validation_failure(self):
        # First call: missing required "price" field — fails validation
        # Second call: valid response
        first_response_block = MagicMock()
        first_response_block.text = '{"title": "Widget"}'

        second_response_block = MagicMock()
        second_response_block.text = '{"title": "Widget", "price": 9.99}'

        first_response = MagicMock()
        first_response.content = [first_response_block]

        second_response = MagicMock()
        second_response.content = [second_response_block]

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=[first_response, second_response])

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        extractor = _make_structured_extractor(mock_client)
        result = await extractor.extract(SAMPLE_HTML, SIMPLE_SCHEMA)

        assert result == {"title": "Widget", "price": 9.99}
        assert mock_client.messages.create.call_count == 2


# ===========================================================================
# Test 3 — extract raises after two failures
# ===========================================================================


class TestExtractRaisesAfterTwoFailures:
    """Test 3 — extract raises ExtractionError when both attempts fail schema validation."""

    async def test_extract_raises_after_two_failures(self):
        from src.extractor.structured import ExtractionError

        # Both calls return JSON that is missing required "price" field
        first_response_block = MagicMock()
        first_response_block.text = '{"title": "Widget"}'

        second_response_block = MagicMock()
        second_response_block.text = '{"title": "Widget"}'

        first_response = MagicMock()
        first_response.content = [first_response_block]

        second_response = MagicMock()
        second_response.content = [second_response_block]

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=[first_response, second_response])

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        extractor = _make_structured_extractor(mock_client)

        with pytest.raises(ExtractionError):
            await extractor.extract(SAMPLE_HTML, SIMPLE_SCHEMA)


# ===========================================================================
# Test 4 — extract raises on JSON parse error
# ===========================================================================


class TestExtractRaisesOnJsonParseError:
    """Test 4 — extract raises ExtractionError when Claude returns non-JSON text."""

    async def test_extract_raises_on_json_parse_error(self):
        from src.extractor.structured import ExtractionError

        mock_client = _make_mock_client("not json at all")
        extractor = _make_structured_extractor(mock_client)

        with pytest.raises(ExtractionError):
            await extractor.extract(SAMPLE_HTML, SIMPLE_SCHEMA)


# ===========================================================================
# Test 5 — extract raises on API error
# ===========================================================================


class TestExtractRaisesOnApiError:
    """Test 5 — extract raises ExtractionError when the Anthropic API raises."""

    async def test_extract_raises_on_api_error(self):
        import httpx
        import anthropic as anthropic_lib
        from src.extractor.structured import ExtractionError

        fake_request = MagicMock(spec=httpx.Request)
        api_error = anthropic_lib.APIError(
            message="simulated API error",
            request=fake_request,
            body=None,
        )

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=api_error)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        extractor = _make_structured_extractor(mock_client)

        with pytest.raises(ExtractionError):
            await extractor.extract(SAMPLE_HTML, SIMPLE_SCHEMA)


# ===========================================================================
# Test 6 — missing API key raises EnvironmentError
# ===========================================================================


class TestMissingApiKeyRaises:
    """Test 6 — StructuredExtractor raises EnvironmentError when API key is absent."""

    def test_missing_api_key_raises(self):
        from src.extractor.structured import StructuredExtractor

        env_without_key = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        with patch.dict(os.environ, env_without_key, clear=True):
            with pytest.raises(EnvironmentError):
                StructuredExtractor()


# ===========================================================================
# Test 7 — extract_with_selector succeeds without healing
# ===========================================================================


class TestExtractWithSelectorSuccess:
    """Test 7 — extract_with_selector returns text when selector matches without healing."""

    async def test_extract_with_selector_success(self, tmp_path):
        audit_log = str(tmp_path / "test_audit.log")
        mock_client = _make_mock_client("div.price")  # heal response, should not be called
        healer = _make_selector_healer(mock_client, audit_log)

        html = "<div class='price'>$19.99</div>"

        with patch.object(healer, "heal_selector", new_callable=AsyncMock) as mock_heal:
            result = await healer.extract_with_selector(html, "div.price", "price element")

        assert result == "$19.99"
        assert mock_heal.call_count == 0


# ===========================================================================
# Test 8 — extract_with_selector triggers healing on broken selector
# ===========================================================================


class TestExtractWithSelectorTriggersHealing:
    """Test 8 — extract_with_selector heals a broken selector and logs the change."""

    async def test_extract_with_selector_triggers_healing(self, tmp_path):
        audit_log = str(tmp_path / "test_audit.log")
        mock_client = _make_mock_client("div.price")
        healer = _make_selector_healer(mock_client, audit_log)

        html = "<div class='price'>$19.99</div>"

        with (
            patch.object(
                healer,
                "heal_selector",
                new_callable=AsyncMock,
                return_value="div.price",
            ) as mock_heal,
            patch.object(healer, "log_selector_change") as mock_log,
        ):
            result = await healer.extract_with_selector(html, "span.broken", "price element")

        assert result == "$19.99"
        mock_heal.assert_called_once()
        mock_log.assert_called_once()


# ===========================================================================
# Test 9 — heal_selector returns stripped Claude response
# ===========================================================================


class TestHealSelectorReturnsClaudeResponse:
    """Test 9 — heal_selector returns the stripped selector text from Claude."""

    async def test_heal_selector_returns_claude_response(self, tmp_path):
        audit_log = str(tmp_path / "test_audit.log")
        mock_client = _make_mock_client("div.actual-price\n")
        healer = _make_selector_healer(mock_client, audit_log)

        html = "<div class='actual-price'>$19.99</div>"
        result = await healer.heal_selector(html, "span.broken", "price element")

        assert result == "div.actual-price"


# ===========================================================================
# Test 10 — heal_selector returns original selector on API error
# ===========================================================================


class TestHealSelectorReturnsOriginalOnApiError:
    """Test 10 — heal_selector returns broken_selector unchanged when Claude API raises."""

    async def test_heal_selector_returns_original_on_api_error(self, tmp_path):
        import httpx
        import anthropic as anthropic_lib

        fake_request = MagicMock(spec=httpx.Request)
        api_error = anthropic_lib.APIError(
            message="simulated API error",
            request=fake_request,
            body=None,
        )

        mock_messages = AsyncMock()
        mock_messages.create = AsyncMock(side_effect=api_error)

        mock_client = MagicMock()
        mock_client.messages = mock_messages

        audit_log = str(tmp_path / "test_audit.log")
        healer = _make_selector_healer(mock_client, audit_log)

        html = "<div class='price'>$19.99</div>"
        result = await healer.heal_selector(html, "span.broken", "price element")

        assert result == "span.broken"


# ===========================================================================
# Test 11 — log_selector_change writes a JSONL record
# ===========================================================================


class TestLogSelectorChangeWritesJsonl:
    """Test 11 — log_selector_change writes a single valid JSONL record to the audit log."""

    async def test_log_selector_change_writes_jsonl(self, tmp_path):
        audit_log = str(tmp_path / "test_audit.log")
        mock_client = _make_mock_client("")
        healer = _make_selector_healer(mock_client, audit_log)

        healer.log_selector_change("old", "new", "http://example.com")

        with open(audit_log, encoding="utf-8") as fh:
            lines = fh.readlines()

        assert len(lines) == 1
        record = json.loads(lines[0])
        assert record["original_selector"] == "old"
        assert record["healed_selector"] == "new"
        assert record["url"] == "http://example.com"


# ===========================================================================
# Test 12 — log_selector_change appends multiple records
# ===========================================================================


class TestLogSelectorChangeAppendsMultiple:
    """Test 12 — log_selector_change appends successive JSONL records without overwriting."""

    async def test_log_selector_change_appends_multiple(self, tmp_path):
        audit_log = str(tmp_path / "test_audit.log")
        mock_client = _make_mock_client("")
        healer = _make_selector_healer(mock_client, audit_log)

        healer.log_selector_change("old1", "new1", "http://example.com/1")
        healer.log_selector_change("old2", "new2", "http://example.com/2")

        with open(audit_log, encoding="utf-8") as fh:
            lines = fh.readlines()

        assert len(lines) == 2

        for line in lines:
            record = json.loads(line)
            assert "original_selector" in record
            assert "healed_selector" in record
            assert "url" in record
