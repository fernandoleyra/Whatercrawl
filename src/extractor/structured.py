"""
Claude-powered structured data extraction.

Sends HTML + a JSON schema to Claude and returns a validated dict
whose shape matches the schema. Retries once on validation failure.
"""

from __future__ import annotations

import json
import logging
import os

import anthropic
import jsonschema

logger = logging.getLogger(__name__)

STRUCTURED_MODEL = "claude-sonnet-4-20250514"
MAX_RETRIES = 2


class ExtractionError(Exception):
    pass


class StructuredExtractor:
    """
    Extracts structured data from raw HTML using the Claude API.

    Requires ANTHROPIC_API_KEY to be set in the environment — raises
    EnvironmentError at instantiation time if the key is absent.
    """

    def __init__(self) -> None:
        api_key: str | None = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise EnvironmentError(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before instantiating StructuredExtractor."
            )
        self._client = anthropic.AsyncAnthropic()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _build_initial_prompt(html: str, schema: dict) -> str:
        return (
            "You are a structured data extraction assistant.\n\n"
            "Given the HTML content of a webpage and a JSON schema, extract the data matching "
            "the schema fields and return ONLY a valid JSON object. No markdown, no explanation.\n\n"
            f"Schema:\n{json.dumps(schema, indent=2)}\n\n"
            f"HTML:\n{html[:8000]}\n\n"
            f"Return a JSON object with exactly these fields: {list(schema.get('properties', schema).keys())}"
        )

    @staticmethod
    def _build_retry_prompt(html: str, schema: dict, validation_error_message: str) -> str:
        return (
            f"Your previous response failed JSON schema validation with this error:\n"
            f"{validation_error_message}\n\n"
            "Please try again. Return ONLY a valid JSON object matching this schema:\n"
            f"{json.dumps(schema, indent=2)}\n\n"
            f"HTML:\n{html[:8000]}"
        )

    async def _call_claude(self, prompt: str) -> str:
        """Send a single prompt to Claude and return the raw text response."""
        try:
            response = await self._client.messages.create(
                model=STRUCTURED_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.AuthenticationError as exc:
            raise ExtractionError(f"Anthropic authentication failed: {exc}") from exc
        except anthropic.RateLimitError as exc:
            raise ExtractionError(f"Anthropic rate limit exceeded: {exc}") from exc
        except anthropic.APIConnectionError as exc:
            raise ExtractionError(f"Anthropic connection error: {exc}") from exc
        except anthropic.APIError as exc:
            raise ExtractionError(f"Anthropic API error: {exc}") from exc

        return response.content[0].text.strip()

    @staticmethod
    def _parse_json(response_text: str) -> dict:
        """Parse JSON from a Claude response string."""
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as exc:
            raise ExtractionError(
                f"Response was not valid JSON: {response_text[:200]}"
            ) from exc

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def extract(self, html: str, schema: dict) -> dict:
        """
        Extract structured data from HTML according to the provided JSON schema.

        Calls Claude with an extraction prompt, validates the result against
        the schema, and retries once if validation fails. Raises ExtractionError
        if both attempts fail or if an unrecoverable API error occurs.

        Args:
            html:   Raw HTML string of the page to extract from.
            schema: JSON Schema dict describing the expected output shape.

        Returns:
            Validated dict whose structure matches the schema.

        Raises:
            ExtractionError: On API failure, JSON parse failure, or two
                             consecutive schema validation failures.
        """
        # --- Attempt 1 ---
        prompt = self._build_initial_prompt(html, schema)
        response_text = await self._call_claude(prompt)
        parsed = self._parse_json(response_text)

        try:
            jsonschema.validate(instance=parsed, schema=schema)
            return parsed
        except jsonschema.ValidationError as first_error:
            logger.warning(
                "Schema validation failed on attempt 1: %s — retrying.", first_error.message
            )
            validation_error_message = first_error.message

        # --- Attempt 2 (retry with error feedback) ---
        retry_prompt = self._build_retry_prompt(html, schema, validation_error_message)
        retry_response_text = await self._call_claude(retry_prompt)
        retry_parsed = self._parse_json(retry_response_text)

        try:
            jsonschema.validate(instance=retry_parsed, schema=schema)
            return retry_parsed
        except jsonschema.ValidationError as second_error:
            raise ExtractionError(
                f"Structured extraction failed after {MAX_RETRIES} attempts. "
                f"Final validation error: {second_error.message}"
            ) from second_error
