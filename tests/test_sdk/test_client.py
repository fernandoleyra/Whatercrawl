"""
tests/test_sdk/test_client.py — Unit tests for sdk/webcrawl/client.py.

Uses unittest.mock to patch httpx.Client instance methods (post/get) so
no live server is required.  All tests are synchronous (the SDK is sync).
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock

from sdk.webcrawl.client import WebcrawlClient, WebcrawlError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_response(
    status_code: int,
    json_data: dict | None = None,
    text: str = "",
) -> MagicMock:
    """Return a MagicMock that mimics an httpx.Response."""
    mock_resp = MagicMock()
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data if json_data is not None else {}
    mock_resp.text = text
    mock_resp.raise_for_status = MagicMock()  # we handle status manually
    return mock_resp


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def client() -> WebcrawlClient:
    """Return a WebcrawlClient with a patched (no-op) httpx.Client."""
    wc = WebcrawlClient("http://localhost:8000")
    # Replace the underlying httpx.Client with a plain MagicMock so no real
    # network calls are ever attempted.
    wc._client = MagicMock()
    return wc


# ---------------------------------------------------------------------------
# scrape() tests
# ---------------------------------------------------------------------------


def test_scrape_correct_http_method_and_url(client: WebcrawlClient) -> None:
    """scrape() must POST to /scrape and return the 'content' field."""
    mock_resp = make_mock_response(
        200,
        json_data={
            "content": "# Hello",
            "format": "markdown",
            "url": "http://example.com",
            "crawled_at": "2026-03-24",
        },
    )
    client._client.post.return_value = mock_resp

    result = client.scrape("http://example.com")

    client._client.post.assert_called_once()
    call_args = client._client.post.call_args
    assert call_args[0][0] == "/scrape"
    assert result == "# Hello"


def test_scrape_correct_request_body(client: WebcrawlClient) -> None:
    """scrape() must pass url and output_format in the JSON body."""
    mock_resp = make_mock_response(
        200,
        json_data={"content": "text result", "url": "http://example.com"},
    )
    client._client.post.return_value = mock_resp

    client.scrape("http://example.com", output_format="text")

    call_kwargs = client._client.post.call_args[1]
    assert call_kwargs["json"]["url"] == "http://example.com"
    assert call_kwargs["json"]["output_format"] == "text"


def test_scrape_error_raises_webcrawl_error(client: WebcrawlClient) -> None:
    """scrape() must raise WebcrawlError with the correct status_code on 502."""
    mock_resp = make_mock_response(502, json_data={"detail": "crawl failed"})
    client._client.post.return_value = mock_resp

    with pytest.raises(WebcrawlError) as exc_info:
        client.scrape("http://example.com")

    assert exc_info.value.status_code == 502


# ---------------------------------------------------------------------------
# crawl() tests
# ---------------------------------------------------------------------------


def test_crawl_correct_request(client: WebcrawlClient) -> None:
    """crawl() must POST to /crawl and return the job_id."""
    mock_resp = make_mock_response(
        200,
        json_data={"job_id": "abc-123", "status": "pending"},
    )
    client._client.post.return_value = mock_resp

    result = client.crawl("http://example.com", max_pages=10)

    client._client.post.assert_called_once()
    call_args = client._client.post.call_args
    assert call_args[0][0] == "/crawl"
    assert result == "abc-123"

    body = call_args[1]["json"]
    assert body["url"] == "http://example.com"
    assert body["max_pages"] == 10


# ---------------------------------------------------------------------------
# get_crawl_status() tests
# ---------------------------------------------------------------------------


def test_get_crawl_status_correct_url(client: WebcrawlClient) -> None:
    """get_crawl_status() must GET /crawl/<job_id> and return the full dict."""
    mock_resp = make_mock_response(
        200,
        json_data={"job_id": "abc-123", "status": "done", "pages": []},
    )
    client._client.get.return_value = mock_resp

    result = client.get_crawl_status("abc-123")

    client._client.get.assert_called_once()
    call_args = client._client.get.call_args
    assert call_args[0][0] == "/crawl/abc-123"
    assert result["status"] == "done"


def test_get_crawl_status_404_raises_webcrawl_error(client: WebcrawlClient) -> None:
    """get_crawl_status() must raise WebcrawlError with status_code 404."""
    mock_resp = make_mock_response(404, json_data={"detail": "not found"})
    client._client.get.return_value = mock_resp

    with pytest.raises(WebcrawlError) as exc_info:
        client.get_crawl_status("abc-123")

    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# extract() tests
# ---------------------------------------------------------------------------


def test_extract_correct_request(client: WebcrawlClient) -> None:
    """extract() must POST to /extract and return the 'data' field."""
    mock_resp = make_mock_response(
        200,
        json_data={"url": "http://example.com", "data": {"title": "Widget"}},
    )
    client._client.post.return_value = mock_resp

    result = client.extract("http://example.com", {"title": "string"})

    client._client.post.assert_called_once()
    call_args = client._client.post.call_args
    assert call_args[0][0] == "/extract"
    assert result == {"title": "Widget"}

    body = call_args[1]["json"]
    assert body["url"] == "http://example.com"
    assert body["schema"] == {"title": "string"}


# ---------------------------------------------------------------------------
# Error-handling edge cases
# ---------------------------------------------------------------------------


def test_error_response_raises_webcrawl_error_non_json(client: WebcrawlClient) -> None:
    """WebcrawlError must be raised even when the error body is not JSON."""
    mock_resp = make_mock_response(500, text="Internal Server Error")
    # json() raises an exception to simulate a non-JSON body
    mock_resp.json.side_effect = ValueError("No JSON")
    client._client.post.return_value = mock_resp

    with pytest.raises(WebcrawlError) as exc_info:
        client.scrape("http://example.com")

    assert exc_info.value.status_code == 500
    assert "Internal Server Error" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Context manager
# ---------------------------------------------------------------------------


def test_context_manager() -> None:
    """WebcrawlClient must work as a context manager without raising."""
    with WebcrawlClient() as wc:
        # Replace underlying transport so close() doesn't fail on teardown
        wc._client = MagicMock()
        assert isinstance(wc, WebcrawlClient)
