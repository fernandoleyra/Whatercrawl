# Research: Claude Vision API for Screenshot Extraction
**Researcher Agent | T4 | 2026-03-24**

---

## Question

How to: take a full-page screenshot with Playwright, encode it as base64, send to Claude Vision, and parse the Markdown response using the `anthropic` Python SDK.

---

## API Format

The Anthropic Messages API accepts image content blocks in the `content` array of a user message. Each image block has a `source` object with `type`, `media_type`, and `data` fields.

**Exact message structure for base64 image input:**

```python
messages=[
    {
        "role": "user",
        "content": [
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",   # or image/jpeg, image/gif, image/webp
                    "data": "<base64_encoded_string>",
                },
            },
            {
                "type": "text",
                "text": "Your prompt here",
            },
        ],
    }
]
```

**Supported media types:**
- `image/png`
- `image/jpeg`
- `image/gif`
- `image/webp`

**Image size limits:**
- Maximum image size: 8000x8000 pixels (images are auto-downscaled if larger)
- Maximum base64 payload: ~5 MB per image (raw image bytes before encoding)
- Maximum 20 images per API request

**SDK client instantiation:**

```python
import anthropic

client = anthropic.Anthropic(api_key="YOUR_ANTHROPIC_API_KEY")
# or set ANTHROPIC_API_KEY env var and call anthropic.Anthropic() with no args

# Async variant (recommended for Playwright async context):
async_client = anthropic.AsyncAnthropic(api_key="YOUR_ANTHROPIC_API_KEY")
```

---

## Working End-to-End Code Example

```python
"""
Playwright screenshot -> base64 -> Claude Vision -> Markdown string.

Dependencies:
    pip install anthropic playwright
    playwright install chromium
"""

import asyncio
import base64
import os
import time
from typing import Optional

import anthropic
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096
SCREENSHOT_TIMEOUT_MS = 30_000   # 30 s for full-page screenshot
MAX_RETRIES = 3
RETRY_BASE_DELAY = 2.0           # seconds, doubles on each retry


# ---------------------------------------------------------------------------
# Core extraction function
# ---------------------------------------------------------------------------

async def take_screenshot_and_extract(
    page: Page,
    extra_instructions: str = "",
    timeout_ms: int = SCREENSHOT_TIMEOUT_MS,
) -> str:
    """
    Take a full-page screenshot of `page`, send it to Claude Vision,
    and return the page content as a clean Markdown string.

    Args:
        page:                Playwright async Page object (must already be navigated).
        extra_instructions:  Optional additional instructions appended to the prompt.
        timeout_ms:          Playwright screenshot timeout in milliseconds.

    Returns:
        A Markdown string representing the page content.

    Raises:
        RuntimeError:        On unrecoverable API errors or empty response after retries.
        PlaywrightTimeoutError: If the screenshot times out.
    """
    # ------------------------------------------------------------------
    # 1. Capture full-page screenshot as PNG bytes
    # ------------------------------------------------------------------
    screenshot_bytes: bytes = await page.screenshot(
        full_page=True,
        type="png",
        timeout=timeout_ms,
    )

    if not screenshot_bytes:
        raise RuntimeError("Playwright returned empty screenshot bytes.")

    # ------------------------------------------------------------------
    # 2. Encode to base64
    # ------------------------------------------------------------------
    screenshot_b64: str = base64.standard_b64encode(screenshot_bytes).decode("utf-8")

    # ------------------------------------------------------------------
    # 3. Build the prompt
    # ------------------------------------------------------------------
    prompt = _build_extraction_prompt(extra_instructions)

    # ------------------------------------------------------------------
    # 4. Call Claude Vision API (with retry logic)
    # ------------------------------------------------------------------
    markdown_content = await _call_claude_vision(
        image_b64=screenshot_b64,
        media_type="image/png",
        prompt=prompt,
    )

    return markdown_content


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

def _build_extraction_prompt(extra_instructions: str = "") -> str:
    base_prompt = (
        "You are a web content extractor. "
        "The image shows a full web page screenshot. "
        "Extract ALL visible text content from the page and format it as clean, "
        "well-structured Markdown. Follow these rules:\n\n"
        "1. Preserve the logical document hierarchy using Markdown headings "
        "(# for h1, ## for h2, etc.).\n"
        "2. Render navigation menus, sidebars, and headers as Markdown lists "
        "or sections if they contain meaningful content; omit pure decoration.\n"
        "3. Format tables as Markdown tables.\n"
        "4. Render code blocks with triple backticks and the correct language tag "
        "if identifiable.\n"
        "5. Convert hyperlink text to plain text (do NOT invent URLs).\n"
        "6. Do NOT include HTML tags, CSS, or JavaScript.\n"
        "7. Do NOT add commentary, preamble, or explanation — output ONLY the "
        "Markdown content.\n"
        "8. If a section is unreadable or obscured, skip it silently.\n"
    )
    if extra_instructions:
        base_prompt += f"\nAdditional instructions: {extra_instructions}\n"
    return base_prompt


# ---------------------------------------------------------------------------
# Claude API call with retry / error handling
# ---------------------------------------------------------------------------

async def _call_claude_vision(
    image_b64: str,
    media_type: str,
    prompt: str,
    model: str = MODEL,
    max_tokens: int = MAX_TOKENS,
) -> str:
    """
    Send an image + text prompt to Claude and return the text response.

    Retries on rate-limit (429) and transient server errors (529, 5xx).
    Raises RuntimeError on permanent errors.
    """
    client = anthropic.AsyncAnthropic(
        api_key=os.environ["ANTHROPIC_API_KEY"],
    )

    messages = [
        {
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": image_b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt,
                },
            ],
        }
    ]

    last_exception: Optional[Exception] = None

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )

            # ----------------------------------------------------------
            # Parse response
            # ----------------------------------------------------------
            if not response.content:
                raise RuntimeError(
                    "Claude returned an empty content list (no text blocks)."
                )

            # Collect all text blocks
            text_parts = [
                block.text
                for block in response.content
                if block.type == "text" and block.text
            ]

            if not text_parts:
                raise RuntimeError(
                    "Claude response contained no text blocks. "
                    f"Stop reason: {response.stop_reason}"
                )

            return "\n".join(text_parts).strip()

        except anthropic.RateLimitError as exc:
            # 429 — back off and retry
            last_exception = exc
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            print(
                f"[claude_vision] Rate limit hit (attempt {attempt}/{MAX_RETRIES}). "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

        except anthropic.APIStatusError as exc:
            # 529 overload or other 5xx transient errors — retry
            if exc.status_code in (529, 500, 502, 503, 504):
                last_exception = exc
                delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(
                    f"[claude_vision] Server error {exc.status_code} "
                    f"(attempt {attempt}/{MAX_RETRIES}). Retrying in {delay:.1f}s..."
                )
                await asyncio.sleep(delay)
            else:
                # Permanent client-side error (400, 401, 403, 404, etc.)
                raise RuntimeError(
                    f"Anthropic API permanent error {exc.status_code}: {exc.message}"
                ) from exc

        except anthropic.APIConnectionError as exc:
            # Network-level failure — retry
            last_exception = exc
            delay = RETRY_BASE_DELAY * (2 ** (attempt - 1))
            print(
                f"[claude_vision] Connection error (attempt {attempt}/{MAX_RETRIES}). "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

        except anthropic.AuthenticationError as exc:
            raise RuntimeError(
                "Anthropic authentication failed. Check ANTHROPIC_API_KEY."
            ) from exc

    raise RuntimeError(
        f"Claude Vision API failed after {MAX_RETRIES} attempts. "
        f"Last error: {last_exception}"
    )


# ---------------------------------------------------------------------------
# Example usage
# ---------------------------------------------------------------------------

async def _demo():
    from playwright.async_api import async_playwright

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 800})
        await page.goto("https://example.com", wait_until="networkidle")

        markdown = await take_screenshot_and_extract(page)
        print(markdown)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(_demo())
```

---

## Prompt Engineering Notes

**What works best for clean Markdown extraction from a screenshot:**

1. **Role framing first** — opening with "You are a web content extractor" anchors the model's behavior before the instruction list.

2. **Explicit output-only instruction** — "output ONLY the Markdown content" suppresses Claude's natural tendency to add preamble like "Here is the extracted content:".

3. **Hierarchy preservation** — explicitly mapping h1→`#`, h2→`##` etc. produces structured output that is directly usable downstream.

4. **No invented URLs** — telling Claude not to fabricate link targets prevents hallucinated href values from polluting the output.

5. **Silent omission of unreadable sections** — avoids noise like "[text unclear]" annotations.

6. **Code block guidance** — without this, Claude may wrap code in prose paragraphs instead of fenced blocks.

7. **Avoid asking for JSON** — for arbitrary web pages, requesting Markdown directly is more robust than asking for structured JSON, since Markdown degrades gracefully for any page layout.

**Optional: add a system prompt** for consistent formatting across many pages:

```python
response = await client.messages.create(
    model=model,
    max_tokens=max_tokens,
    system=(
        "You extract web page content as clean Markdown. "
        "Never add commentary. Never invent data not visible in the image."
    ),
    messages=messages,
)
```

---

## Error Handling

| Exception class | Meaning | Strategy |
|---|---|---|
| `anthropic.RateLimitError` | 429 Too Many Requests | Exponential backoff, up to `MAX_RETRIES` |
| `anthropic.APIStatusError` (5xx / 529) | Server overload or transient error | Exponential backoff, up to `MAX_RETRIES` |
| `anthropic.APIStatusError` (4xx permanent) | Bad request, invalid input, auth | Raise immediately as `RuntimeError` |
| `anthropic.APIConnectionError` | Network failure | Exponential backoff, up to `MAX_RETRIES` |
| `anthropic.AuthenticationError` | Invalid API key | Raise immediately |
| Empty `response.content` | No content returned | Raise `RuntimeError` after response received |
| `PlaywrightTimeoutError` | Screenshot timed out | Propagate; caller decides whether to retry navigation |

**Key implementation details:**

- Use `asyncio.sleep()` (not `time.sleep()`) inside async functions to avoid blocking the event loop.
- Log the attempt number and delay before sleeping so operators can diagnose throttling.
- Distinguish permanent 4xx errors (do not retry) from transient 5xx errors (do retry).
- Always validate `response.content` is non-empty and contains at least one `text` block before accessing `.text`.
- Store the last exception and re-raise it with context after all retries are exhausted.

---

## Model Selection Note

**Recommended model for vision tasks (2025/2026):** `claude-sonnet-4-20250514`

This is the Claude Sonnet 4 release, which:
- Supports vision (image input) natively
- Has a 200K token context window
- Offers strong OCR-level text extraction from screenshots
- Balances capability and cost better than claude-opus-4 for extraction tasks

**Model ID to use in code:**
```python
MODEL = "claude-sonnet-4-20250514"
```

**Alternative / fallback:**
- `claude-opus-4-20250514` — highest capability, higher cost; use if Sonnet struggles with complex/dense layouts
- `claude-haiku-3-5-20241022` — fastest and cheapest; acceptable for simple pages with large text

Do NOT use `claude-3-opus-20240229` or other claude-3 variants for new projects — the claude-sonnet-4 family has superseded them for vision tasks.

---

## References

- Anthropic Vision Documentation: https://docs.anthropic.com/en/docs/build-with-claude/vision
- Anthropic Python SDK (PyPI): https://pypi.org/project/anthropic/
- Anthropic SDK GitHub: https://github.com/anthropic/anthropic-sdk-python
- Anthropic API Error Reference: https://docs.anthropic.com/en/api/errors
- Playwright Python Docs (screenshot): https://playwright.dev/python/docs/api/class-page#page-screenshot
- Anthropic Models Overview: https://docs.anthropic.com/en/docs/about-claude/models
