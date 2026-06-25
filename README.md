# Watercrawl

## 1. What Watercrawl Is

Watercrawl is a production-grade web scraping API that converts any URL or entire website into clean, LLM-ready Markdown or structured JSON. It is a drop-in replacement for Firecrawl with better extraction quality via Playwright-powered JS rendering and lower cost when self-hosted. Runs fully locally with one Docker command — no external queue, no cloud dependency required.

---

## 2. Quick Start

### Docker (recommended)

```bash
git clone <repo>
cd watercrawl
cp .env.example .env
docker-compose up
# API is now running at http://localhost:8000
```

### Local dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
uvicorn src.api.app:app --reload
```

---

## 3. API Reference

### POST /scrape

Scrape a single URL and return its content as Markdown, plain text, or raw HTML.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | required | The URL to scrape |
| `output_format` | `"markdown"` \| `"text"` \| `"html"` | `"markdown"` | Desired output format |

**Example**

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"url": "https://news.ycombinator.com", "output_format": "markdown"}'
```

**Response shape**

```json
{
  "url": "https://news.ycombinator.com",
  "content": "# Hacker News\n...",
  "format": "markdown",
  "crawled_at": "2026-03-24T12:00:00Z"
}
```

---

### POST /crawl

Start an asynchronous crawl job from a root URL. Returns a `job_id` immediately; use `GET /crawl/{job_id}` to poll for results.

**Request body**

| Field | Type | Default | Description |
|---|---|---|---|
| `url` | string | required | Root URL to crawl |
| `max_pages` | integer | `50` | Maximum number of pages to visit |
| `max_depth` | integer | `3` | Maximum link depth from the root URL |
| `output_format` | string | `"markdown"` | Desired output format for each page |

**Example**

```bash
curl -X POST http://localhost:8000/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://docs.python.org", "max_pages": 50, "max_depth": 3}'
```

**Response shape**

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "queued"
}
```

---

### GET /crawl/{job_id}

Retrieve the current status and all collected pages for a crawl job.

**Path parameter:** `job_id` — the string returned by `POST /crawl`.

**Example**

```bash
curl http://localhost:8000/crawl/a1b2c3d4-...
```

**Response shape**

```json
{
  "job_id": "a1b2c3d4-...",
  "status": "complete",
  "pages": [
    {"url": "https://docs.python.org/", "content": "# Python Docs\n..."},
    {"url": "https://docs.python.org/tutorial/", "content": "# Tutorial\n..."}
  ]
}
```

Possible `status` values: `queued`, `running`, `complete`, `failed`.

---

### POST /extract

Run structured data extraction against a URL using a JSON-schema-style field definition. Claude processes the page content and returns typed values matching the provided schema.

**Request body**

| Field | Type | Description |
|---|---|---|
| `url` | string | The URL to extract data from |
| `schema` | object | A dict describing the fields to extract (field name → type hint string) |

**Example**

```bash
curl -X POST http://localhost:8000/extract \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/product",
    "schema": {
      "title": "string",
      "price": "number",
      "in_stock": "boolean"
    }
  }'
```

**Response shape**

```json
{
  "url": "https://example.com/product",
  "data": {
    "title": "Widget Pro",
    "price": 29.99,
    "in_stock": true
  }
}
```

---

## 4. Python SDK

**Install**

```bash
pip install -e sdk/
```

**Usage**

```python
from watercrawl import WatercrawlClient

client = WatercrawlClient(base_url="http://localhost:8000")

# Scrape a URL — returns the content string
markdown = client.scrape("https://news.ycombinator.com")

# Request plain text or HTML instead
text = client.scrape("https://news.ycombinator.com", output_format="text")

# Crawl a site — returns a job_id string
job_id = client.crawl("https://docs.python.org", max_pages=50, max_depth=3)

# Check crawl status — returns {"job_id": ..., "status": ..., "pages": [...]}
status = client.get_crawl_status(job_id)

# Extract structured data — returns the extracted data dict
data = client.extract("https://example.com/product", schema={
    "title": "string",
    "price": "number",
    "in_stock": "boolean"
})
```

The client can also be used as a context manager to ensure the underlying HTTP connection is closed cleanly:

```python
with WatercrawlClient(base_url="http://localhost:8000") as client:
    markdown = client.scrape("https://example.com")
```

**Error handling**

All methods raise `watercrawl.WatercrawlError` on non-2xx API responses. The exception carries a `status_code` attribute.

```python
from watercrawl import WatercrawlClient, WatercrawlError

with WatercrawlClient() as client:
    try:
        data = client.extract("https://example.com", schema={"title": "string"})
    except WatercrawlError as exc:
        print(f"Request failed with HTTP {exc.status_code}: {exc}")
```

**Constructor parameters**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `base_url` | string | `"http://localhost:8000"` | Base URL of the running API |
| `timeout` | float | `60.0` | Per-request timeout in seconds |

---

## 5. Configuration

Copy `.env.example` to `.env` and edit the values before starting the server.

| Variable | Description | Default |
|---|---|---|
| `HOST` | Host address the server binds to | `0.0.0.0` |
| `PORT` | Port the server listens on | `8000` |
| `WATERCRAWL_DB_PATH` | Path to the SQLite database file for async crawl job state | `./data/watercrawl.db` |
| `MAX_CONCURRENT_CRAWLS` | Maximum number of crawl jobs that may run simultaneously | `5` |
| `DEFAULT_TIMEOUT` | Per-page request timeout in seconds | `30` |
| `DEFAULT_MAX_PAGES` | Default upper limit on pages per crawl job | `100` |
| `LOG_LEVEL` | Log verbosity — one of `DEBUG`, `INFO`, `WARNING`, `ERROR` | `INFO` |

When running under Docker Compose, `MAX_CONCURRENT_CRAWLS`, `DEFAULT_TIMEOUT`, `DEFAULT_MAX_PAGES`, and `LOG_LEVEL` fall back to the defaults shown above if not set in the host environment.

---

## 6. Architecture Overview

The server is a FastAPI application that manages a single shared Playwright Chromium browser process; each incoming request receives its own isolated `BrowserContext` so cookies and storage never bleed across requests. Page content is extracted using trafilatura, which handles the common case of well-structured DOM content; when trafilatura returns low-confidence output, a Claude Vision fallback renders the page as an image and extracts text directly from the screenshot. Crawl jobs are queued and persisted in a local SQLite database via aiosqlite, giving the job store full async compatibility without requiring an external broker. Structured extraction calls the Claude API to convert scraped content into typed JSON matching the caller-supplied schema. The Python SDK wraps the HTTP interface with a synchronous httpx client, keeping the caller's code free of any asyncio requirement.

---

## 7. Contributing

1. Fork the repository and create a feature branch off `main`.
2. Make your changes, then run the test suite:
   ```bash
   pytest tests/ -v
   ```
3. Ensure all tests pass before opening a pull request.
4. Submit a PR with a clear description of what the change does and why.
