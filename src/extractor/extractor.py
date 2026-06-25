"""
Content extraction pipeline.

Primary strategy: trafilatura (HTML → Markdown).
Fallback strategy: Claude Vision API (screenshot → Markdown).
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import anthropic
import trafilatura
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

VISION_MODEL = "claude-sonnet-4-20250514"
MIN_WORD_COUNT = 20
_TAGS_TO_REMOVE = ["script", "style", "nav", "footer", "aside"]


class ContentExtractor:
    """
    Extracts clean text/Markdown content from raw HTML.

    Vision fallback requires ANTHROPIC_API_KEY to be set in the environment.
    A missing key raises EnvironmentError at instantiation time so the error
    surfaces early rather than at the first vision call.
    """

    def __init__(self) -> None:
        api_key: Optional[str] = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before instantiating ContentExtractor."
            )
        self._api_key = api_key

    # ------------------------------------------------------------------
    # Public extraction methods
    # ------------------------------------------------------------------

    def extract_markdown(self, html: str) -> str:
        """
        Extract clean content from HTML and return it as Markdown.

        Uses trafilatura with include_tables=True and include_comments=False.
        Returns an empty string if extraction fails or yields fewer than
        MIN_WORD_COUNT words — the caller should trigger a vision fallback.

        Args:
            html: Raw HTML string.

        Returns:
            Markdown string, or "" on failure / sparse content.
        """
        result: Optional[str] = trafilatura.extract(
            html,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
        )
        if result is None or len(result.split()) < MIN_WORD_COUNT:
            return ""
        return result

    def extract_text(self, html: str) -> str:
        """
        Extract clean content from HTML and return it as plain text.

        Args:
            html: Raw HTML string.

        Returns:
            Plain text string, or "" on failure.
        """
        result: Optional[str] = trafilatura.extract(
            html,
            output_format="txt",
            include_comments=False,
            include_tables=True,
        )
        if result is None:
            return ""
        return result

    def extract_raw(self, html: str) -> str:
        """
        Return a cleaned HTML string with noise tags removed.

        Strips <script>, <style>, <nav>, <footer>, and <aside> elements
        using BeautifulSoup then serialises back to an HTML string.

        Args:
            html: Raw HTML string.

        Returns:
            Cleaned HTML string.
        """
        soup = BeautifulSoup(html, "html.parser")
        for tag in _TAGS_TO_REMOVE:
            for element in soup.find_all(tag):
                element.decompose()
        return str(soup)

    async def vision_fallback(self, screenshot_b64: str) -> str:
        """
        Extract page content from a base64-encoded PNG screenshot via Claude Vision.

        Calls the Anthropic Messages API with the screenshot and a structured
        extraction prompt, then returns the model's text response as Markdown.

        Args:
            screenshot_b64: Base64-encoded PNG screenshot (no data-URI prefix).

        Returns:
            Markdown string extracted by Claude, or "" on any API error.
        """
        client = anthropic.AsyncAnthropic(api_key=self._api_key)
        messages = [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_b64,
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "You are a content extraction assistant. "
                            "Extract ALL visible text content from this webpage "
                            "screenshot and return it as clean, well-structured "
                            "Markdown. Preserve headings, lists, and paragraphs. "
                            "Output ONLY the Markdown content — no commentary, "
                            "no code fences."
                        ),
                    },
                ],
            }
        ]

        try:
            response = await client.messages.create(
                model=VISION_MODEL,
                max_tokens=4096,
                messages=messages,  # type: ignore[arg-type]
            )
            text_parts = [
                block.text
                for block in response.content
                if block.type == "text" and block.text
            ]
            return "\n".join(text_parts).strip()

        except anthropic.AuthenticationError as exc:
            logger.error("Anthropic authentication failed in vision_fallback: %s", exc)
            return ""
        except anthropic.RateLimitError as exc:
            logger.error("Anthropic rate limit hit in vision_fallback: %s", exc)
            return ""
        except anthropic.APIConnectionError as exc:
            logger.error("Anthropic connection error in vision_fallback: %s", exc)
            return ""
        except anthropic.APIStatusError as exc:
            logger.error(
                "Anthropic API error %s in vision_fallback: %s",
                exc.status_code,
                exc.message,
            )
            return ""
        except anthropic.APIError as exc:
            logger.error("Anthropic API error in vision_fallback: %s", exc)
            return ""

    async def extract_with_fallback(
        self, html: str, screenshot_b64: str
    ) -> str:
        """
        Extract content from HTML, falling back to Claude Vision if needed.

        Tries extract_markdown(html) first. If that returns an empty string
        (sparse/JS-only page), calls vision_fallback(screenshot_b64).

        Args:
            html:            Raw HTML string.
            screenshot_b64:  Base64-encoded PNG screenshot.

        Returns:
            Markdown string from whichever strategy succeeded, or "".
        """
        markdown = self.extract_markdown(html)
        if markdown:
            return markdown

        logger.debug(
            "trafilatura extraction returned empty or below threshold — "
            "falling back to Claude Vision."
        )
        return await self.vision_fallback(screenshot_b64)
