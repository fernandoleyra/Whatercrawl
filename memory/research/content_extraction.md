# Research: HTML Content Extraction Library
**Researcher Agent | T3 | 2026-03-24**

## Question
Which Python library is best for extracting clean content text from raw HTML in 2025, for a general-purpose web crawler (not just articles)? Must handle product pages, docs, landing pages, and support Markdown output. Libraries compared: trafilatura, readability-lxml, newspaper4k, justext.

---

## Options Considered

### A) trafilatura

**What it is:** A Python library (and CLI) by Adrien Barbaresi, purpose-built for web scraping and content extraction. Uses a custom heuristic pipeline combining XPath, text density analysis, and fallback parsers (readability, justext). Actively maintained; as of 2025, version 1.x+ with regular releases.

**Pros:**
- Native Markdown output — `extract(html, output_format="markdown")` — this is a first-class feature, not a post-processing step
- Also outputs XML, JSON, CSV, and plain text from the same call
- Handles non-article pages reasonably well (product pages, docs) via configurable `include_tables`, `include_links`, `include_images` flags
- Returns `None` on failure (empty/JS-only pages) — clean sentinel for fallback logic
- Exposes a `bare_extraction()` function that returns a structured dict with metadata: title, author, date, language, content, **and a `confidence` float** (0.0–1.0) — directly useful for vision fallback threshold
- Fastest of the four in benchmarks; handles large HTML documents efficiently
- `include_comments=False` by default — avoids noise
- Can follow redirects, fetch URLs directly, or accept raw HTML strings
- Actively maintained on GitHub (adbar/trafilatura), with a dedicated benchmark suite showing it outperforming readability and justext on recall + precision
- Supports Python 3.8+

**Cons:**
- Still article-centric by design; very short product page descriptions may get stripped if below text-density threshold
- Markdown output preserves heading hierarchy but inline formatting (bold/italic) can be inconsistently preserved depending on source HTML
- Dependency footprint is moderate (lxml, urllib3, courlan, htmldate, charset-normalizer)

---

### B) readability-lxml

**What it is:** A Python port of Mozilla's Readability.js algorithm (the same one Firefox Reader View uses). Parses the DOM, scores candidate elements by text density, and returns the "main" content block.

**Pros:**
- Very good at article-style pages; well-tested on news/blog content
- Fast; lightweight dependency (just lxml)
- Returns an HTML fragment — can be piped to markdownify or html2text for Markdown
- Widely used; stable API

**Cons:**
- No native Markdown output — requires a secondary conversion step
- No confidence/quality score — no built-in way to detect extraction failure vs. sparse content
- Returns empty/boilerplate HTML on JS-heavy or near-empty pages without signaling failure — you must check `len(content.strip())` manually
- Poorly maintained as of 2024–2025: the main fork (buriy/python-readability) has had infrequent releases; some upstream Readability.js improvements have not been backported
- Drops tables, complex layouts — product pages and documentation pages lose structure
- No support for non-article page types (e-commerce, landing pages) beyond naive text extraction

---

### C) newspaper4k

**What it is:** newspaper4k is the actively maintained fork of newspaper3k (which went unmaintained ~2022). Forked and revived in 2023–2024 with Python 3.11/3.12 support, bug fixes, and updated dependencies.

**Pros:**
- Includes NLP features: keyword extraction, summary, language detection
- Article-oriented metadata: publish date, authors, top image, tags
- Reasonably good for news/blog articles
- Active fork vs. the dead newspaper3k

**Cons:**
- Strongly article-centric — non-article pages (product pages, docs, landing pages) produce poor results; the library's heuristics assume a news article structure
- No native Markdown output — returns plain text only; requires html2text/markdownify post-processing
- Heavier dependency tree (nltk, Pillow, feedfinder2, etc.)
- No confidence/quality score
- Returns empty string on failure with no clear sentinel — harder to gate vision fallback
- Slower than trafilatura; article download/parse is synchronous by default
- Still catches up to newspaper3k issues; some edge cases around paywalled/JS pages are unresolved

---

### D) justext

**What it is:** Implements the JusText algorithm (Pomikálek 2011), a boilerplate-removal algorithm based on paragraph text density and stopword analysis. Often used as a backend component inside other extractors.

**Pros:**
- Very precise at removing boilerplate (navbars, footers, ads)
- Language-aware (uses stopword lists per language)
- Simple, deterministic algorithm — easy to understand and debug
- Used internally by trafilatura as a fallback strategy

**Cons:**
- Returns a list of paragraph objects with classification labels (GOOD, BAD, NEAR-GOOD, SHORT) — requires manual assembly into a document
- No native Markdown output whatsoever
- Designed for boilerplate removal, not full content extraction — struggles with structured content (tables, code blocks, lists)
- No metadata extraction (title, date, author)
- No confidence score
- Low-level: needs significant wrapper code to be production-ready
- Not suitable as a standalone solution for a general-purpose crawler

---

## Recommendation

**trafilatura**

---

## Reason

trafilatura is the only library among the four that satisfies all the acceptance criteria out of the box:

1. **Native Markdown output** via `output_format="markdown"` — no secondary conversion library needed
2. **Returns `None` on extraction failure** — clean, unambiguous sentinel for gating vision fallback
3. **`bare_extraction()` returns a `confidence` float** — enables quantitative thresholds for deciding when to escalate to vision
4. **Handles non-article pages** better than any alternative — configurable flags (`include_tables`, `include_links`, `include_images`) let you tune extraction for product pages, documentation, and landing pages
5. **Actively maintained** — regular releases on PyPI through 2024–2025, maintained benchmarks, responsive issue tracker
6. **Fastest** — important for a crawler processing many pages concurrently

For the HTML → Markdown pipeline in a firecrawl-style crawler, trafilatura eliminates the need for a separate markdownify/html2text step and provides the confidence signal needed to decide when static extraction is insufficient and a vision/JS-rendering fallback is warranted.

---

## Working Code Example

```python
# pip install trafilatura

import trafilatura

# --- 1. Basic: HTML string → clean Markdown ---

raw_html = """
<html>
<head><title>Product: Wireless Headphones</title></head>
<body>
  <nav><a href="/">Home</a> | <a href="/shop">Shop</a></nav>
  <main>
    <h1>Wireless Headphones XZ-500</h1>
    <p>Experience <strong>crystal-clear audio</strong> with 40-hour battery life.</p>
    <h2>Features</h2>
    <ul>
      <li>Active Noise Cancellation</li>
      <li>Bluetooth 5.3</li>
      <li>USB-C charging</li>
    </ul>
    <table>
      <tr><th>Spec</th><th>Value</th></tr>
      <tr><td>Weight</td><td>250g</td></tr>
      <tr><td>Driver size</td><td>40mm</td></tr>
    </table>
    <p>Price: $149.99</p>
  </main>
  <footer>© 2025 AudioCo. All rights reserved.</footer>
</body>
</html>
"""

# Extract as Markdown directly
markdown_output = trafilatura.extract(
    raw_html,
    output_format="markdown",
    include_tables=True,
    include_links=False,      # set True if you need hyperlinks preserved
    include_images=False,
    no_fallback=False,        # allow readability/justext fallbacks if primary fails
    favor_recall=True,        # better for non-article pages; trades precision for coverage
)

if markdown_output:
    print(markdown_output)
else:
    print("[EXTRACTION FAILED — trigger vision fallback]")


# --- 2. With confidence score via bare_extraction() ---

result = trafilatura.bare_extraction(
    raw_html,
    output_format="markdown",
    include_tables=True,
    favor_recall=True,
)

if result is None:
    confidence = 0.0
    text = None
else:
    text = result.get("text") or result.get("raw_text", "")
    confidence = result.get("confidence", 0.0)  # float 0.0–1.0

CONFIDENCE_THRESHOLD = 0.5  # tune per use-case; see Edge Cases section

if text and confidence >= CONFIDENCE_THRESHOLD:
    print(f"Extracted (confidence={confidence:.2f}):\n{text}")
else:
    print(f"Low confidence ({confidence:.2f}) or empty — escalate to vision fallback")


# --- 3. Fetching directly from a URL (trafilatura handles HTTP) ---

# url = "https://example.com/product-page"
# downloaded = trafilatura.fetch_url(url)
# markdown_output = trafilatura.extract(downloaded, output_format="markdown", favor_recall=True)
```

**Expected output for the example above (abbreviated):**
```markdown
# Wireless Headphones XZ-500

Experience **crystal-clear audio** with 40-hour battery life.

## Features

- Active Noise Cancellation
- Bluetooth 5.3
- USB-C charging

| Spec | Value |
|------|-------|
| Weight | 250g |
| Driver size | 40mm |

Price: $149.99
```

---

## Edge Cases

### Empty page
`trafilatura.extract()` returns `None`. `bare_extraction()` returns `None` or a dict with empty `text`.

**Handling:**
```python
result = trafilatura.extract(html, output_format="markdown", favor_recall=True)
if not result:
    # Page is empty, stub HTML, or pure boilerplate — no usable text
    trigger_vision_fallback(url)
```

### JS-only page (SPA / React / Vue)
When a page requires JavaScript execution to render its content, the static HTML will contain only a shell: `<div id="root"></div>` or similar. trafilatura will return `None` or a very short string (title only).

**Detection pattern:**
```python
import trafilatura

result = trafilatura.bare_extraction(html, output_format="markdown", favor_recall=True)

if result is None:
    is_js_only = True
else:
    text = result.get("text", "") or ""
    confidence = result.get("confidence", 0.0)
    word_count = len(text.split())
    # Heuristic: meaningful pages have >50 words; JS-only shells have <10
    is_js_only = word_count < 20 or confidence < 0.3

if is_js_only:
    # Signal upstream to re-fetch with Playwright/Splash and retry extraction
    # OR pass the URL to the vision agent for screenshot-based extraction
    trigger_js_render_or_vision_fallback(url)
```

**Note:** There is no way for any static parser to recover JS-rendered content. The correct approach is:
1. Detect failure via `None` return or low word-count/confidence
2. Re-fetch with a headless browser (Playwright, Selenium) to get rendered HTML
3. Re-run `trafilatura.extract()` on the rendered HTML — this almost always succeeds
4. If rendered HTML is also sparse (e.g., heavy canvas/WebGL page), escalate to vision (screenshot → LLM)

### Very short content (not JS, just sparse pages)
Some legitimate pages have minimal text (e.g., a product image gallery, a video embed page, a "coming soon" page).

**Threshold recommendation:**
| Word count | Confidence | Action |
|---|---|---|
| > 100 words | ≥ 0.6 | Accept extraction result |
| 20–100 words | 0.3–0.6 | Accept but flag as low-confidence; optionally supplement with vision |
| < 20 words | any | Trigger vision fallback |
| any | < 0.3 | Trigger JS render or vision fallback |

```python
def should_use_vision_fallback(result: dict | None, min_words: int = 20, min_confidence: float = 0.3) -> bool:
    if result is None:
        return True
    text = result.get("text", "") or ""
    confidence = result.get("confidence", 0.0)
    word_count = len(text.split())
    return word_count < min_words or confidence < min_confidence
```

### Malformed / truncated HTML
trafilatura uses lxml's fault-tolerant parser under the hood — it handles tag soup, unclosed tags, and encoding issues gracefully. Returns `None` only when there is genuinely no recoverable text.

### Paywalled pages
trafilatura will extract whatever text is visible in the static HTML (teaser paragraph, headline). It will not bypass paywalls. Confidence will typically be low (0.2–0.4). The vision fallback is not applicable here either — flag as `PAYWALL_SUSPECTED` if the extracted word count is unusually low for a known news domain.

---

## Supplementary: Markdown conversion libraries (if trafilatura is not used)

If the team ever needs to convert arbitrary HTML to Markdown independent of content extraction (e.g., post-processing readability-lxml output):

- **markdownify** (`pip install markdownify`): Simple, reliable HTML → Markdown. Handles tables, code blocks, nested lists. Best for clean HTML fragments.
  ```python
  from markdownify import markdownify as md
  markdown = md(html_fragment, heading_style="ATX")
  ```
- **html2text** (`pip install html2text`): Aaron Swartz's original tool. Good for link-heavy pages; configurable. Slightly noisier output than markdownify on structured content.
  ```python
  import html2text
  h = html2text.HTML2Text()
  h.ignore_links = False
  markdown = h.handle(html_fragment)
  ```

**For the firecrawl-clone project, neither is needed** since trafilatura outputs Markdown natively. Reserve these for cases where you receive a pre-cleaned HTML fragment from another source.

---

## Dependencies (pip install ...)

```bash
# Core: trafilatura with all optional extras
pip install "trafilatura[all]"

# Or minimal install (no CLI extras, no speed extras):
pip install trafilatura

# Key transitive dependencies pulled in automatically:
# lxml, urllib3, courlan, htmldate, charset-normalizer, certifi
```

For the firecrawl-clone `requirements.txt`:
```
trafilatura>=1.6.0
```

---

## References

- trafilatura GitHub: https://github.com/adbar/trafilatura
- trafilatura documentation: https://trafilatura.readthedocs.io/
- trafilatura `bare_extraction()` API: https://trafilatura.readthedocs.io/en/latest/corefunctions.html
- JusText algorithm paper: Pomikálek (2011) — "Removing Boilerplate and Duplicate Content from Web Corpora"
- readability-lxml (buriy fork): https://github.com/buriy/python-readability
- newspaper4k (fork of newspaper3k): https://github.com/andefined/newspaper4k
- markdownify: https://github.com/matthewwithanm/python-markdownify
- html2text: https://github.com/Alir3z4/html2text
- Benchmarks comparing extraction algorithms: https://trafilatura.readthedocs.io/en/latest/evaluation.html
