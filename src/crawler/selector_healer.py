"""Self-healing CSS selector system using Claude API for re-derivation."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from bs4 import BeautifulSoup

HEALER_MODEL = "claude-sonnet-4-20250514"
AUDIT_LOG_PATH = "memory/selector_audit.log"

logger = logging.getLogger(__name__)


class SelectorHealer:
    """Re-derives broken CSS selectors via Claude API and audits all changes."""

    def __init__(self, audit_log_path: str = AUDIT_LOG_PATH) -> None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY is not set in the environment."
            )
        self._client = anthropic.AsyncAnthropic()
        self._audit_log_path = audit_log_path

    async def extract_with_selector(
        self,
        html: str,
        css_selector: str,
        description: str = "",
    ) -> str:
        """Extract text using css_selector; auto-heals on failure.

        Args:
            html: Raw HTML string to parse.
            css_selector: CSS selector to apply.
            description: Human-readable description of the target element.

        Returns:
            Extracted text, or "" on total failure.
        """
        text = self._run_selector(html, css_selector)
        if text is not None:
            return text

        # Selector failed — attempt healing.
        healed = await self.heal_selector(html, css_selector, description)
        if healed != css_selector:
            self.log_selector_change(css_selector, healed, url="unknown")

        text = self._run_selector(html, healed)
        return text if text is not None else ""

    def _run_selector(self, html: str, css_selector: str) -> str | None:
        """Run a CSS selector against html.

        Returns joined text if any elements matched, or None on empty/error.
        """
        try:
            soup = BeautifulSoup(html, "html.parser")
            elements = soup.select(css_selector)
            if elements:
                return " ".join(el.get_text(separator=" ", strip=True) for el in elements)
            return None
        except Exception as exc:  # noqa: BLE001 — BS4 may raise various errors
            logger.warning("Selector %r raised %s: %s", css_selector, type(exc).__name__, exc)
            return None

    async def heal_selector(
        self,
        html: str,
        broken_selector: str,
        description: str,
    ) -> str:
        """Ask Claude to re-derive a working CSS selector.

        Args:
            html: Raw HTML of the page.
            broken_selector: The selector that failed to match.
            description: What the selector was intended to target.

        Returns:
            A new CSS selector string, or broken_selector on API failure.
        """
        target = description or "the main content area"
        prompt = (
            f'You are a CSS selector repair assistant.\n\n'
            f'The CSS selector "{broken_selector}" failed to match any elements on a webpage.\n'
            f'It was intended to select: {target}\n\n'
            f'Here is the relevant HTML (first 4000 chars):\n'
            f'{html[:4000]}\n\n'
            f'Return ONLY a single CSS selector that would correctly match the intended element.\n'
            f'No explanation, no markdown, just the CSS selector string.'
        )
        try:
            message = await self._client.messages.create(
                model=HEALER_MODEL,
                max_tokens=256,
                messages=[{"role": "user", "content": prompt}],
            )
            healed = message.content[0].text.strip()
            return healed
        except anthropic.APIError as exc:
            logger.warning(
                "Claude API error during selector healing (selector=%r): %s",
                broken_selector,
                exc,
            )
            return broken_selector

    def log_selector_change(
        self,
        original: str,
        healed: str,
        url: str,
    ) -> None:
        """Append a JSONL record of a selector change to the audit log.

        Args:
            original: The broken selector.
            healed: The replacement selector.
            url: URL where the selector was used (may be "unknown").
        """
        record = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "url": url,
            "original_selector": original,
            "healed_selector": healed,
        }
        try:
            log_path = Path(self._audit_log_path)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with log_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record) + "\n")
        except IOError as exc:
            logger.warning("Could not write selector audit log: %s", exc)
