"""
sdk/webcrawl/client.py — Sync Python SDK for the Webcrawl API.

Uses httpx.Client (sync) per the decisions.md requirement to support both
sync and async usage patterns without forcing asyncio on callers.
"""

from __future__ import annotations

from typing import Any

import httpx


class WebcrawlError(Exception):
    """Raised when the Webcrawl API returns a non-2xx response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


class WebcrawlClient:
    """
    Synchronous client for the Webcrawl API.

    Args:
        base_url: Base URL of the running API server.
        timeout:  Request timeout in seconds (default 60.0).

    Usage::

        client = WebcrawlClient("http://localhost:8000")
        content = client.scrape("https://example.com")
        client.close()

        # or as a context manager:
        with WebcrawlClient() as client:
            content = client.scrape("https://example.com")
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        timeout: float = 60.0,
    ) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._timeout: float = timeout
        self._client: httpx.Client = httpx.Client(
            base_url=self._base_url,
            timeout=self._timeout,
        )

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def scrape(self, url: str, output_format: str = "markdown") -> str:
        """
        Scrape a single URL and return its content.

        Args:
            url:           The URL to scrape.
            output_format: One of "markdown", "text", or "html".

        Returns:
            The scraped content as a string.

        Raises:
            WebcrawlError: On any non-2xx API response.
        """
        payload: dict[str, Any] = {"url": url, "output_format": output_format}
        response = self._client.post("/scrape", json=payload)
        self._raise_for_status(response)
        return response.json()["content"]

    def crawl(self, url: str, max_pages: int = 50, max_depth: int = 3) -> str:
        """
        Start an async crawl job and return the job ID.

        Args:
            url:       The root URL to crawl.
            max_pages: Maximum number of pages to crawl.
            max_depth: Maximum link-depth from the root URL.

        Returns:
            The job_id string to use with get_crawl_status().

        Raises:
            WebcrawlError: On any non-2xx API response.
        """
        payload: dict[str, Any] = {
            "url": url,
            "max_pages": max_pages,
            "max_depth": max_depth,
        }
        response = self._client.post("/crawl", json=payload)
        self._raise_for_status(response)
        return response.json()["job_id"]

    def get_crawl_status(self, job_id: str) -> dict[str, Any]:
        """
        Retrieve the status and results for a crawl job.

        Args:
            job_id: The job ID returned by crawl().

        Returns:
            A dict with keys: job_id, status, pages.

        Raises:
            WebcrawlError: On any non-2xx API response (including 404).
        """
        response = self._client.get(f"/crawl/{job_id}")
        self._raise_for_status(response)
        return response.json()

    def extract(self, url: str, schema: dict[str, Any]) -> dict[str, Any]:
        """
        Run structured extraction against a URL using the provided JSON schema.

        Args:
            url:    The URL to extract data from.
            schema: A JSON-schema-style dict describing the fields to extract.

        Returns:
            The extracted data dict.

        Raises:
            WebcrawlError: On any non-2xx API response.
        """
        payload: dict[str, Any] = {"url": url, "schema": schema}
        response = self._client.post("/extract", json=payload)
        self._raise_for_status(response)
        return response.json()["data"]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise WebcrawlError if the response status code is >= 400."""
        if response.status_code < 400:
            return

        status = response.status_code
        try:
            detail: str = response.json()["detail"]
        except Exception:  # noqa: BLE001 — response body may not be JSON; fall back to raw text
            detail = response.text

        raise WebcrawlError(f"API error {status}: {detail}", status_code=status)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying httpx.Client and release connections."""
        self._client.close()

    def __enter__(self) -> "WebcrawlClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        self.close()
