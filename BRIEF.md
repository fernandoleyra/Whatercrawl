# Project Brief: Watercrawl

## What to build

A production-grade **web scraping API** called **Watercrawl** that converts any URL
or entire website into clean, LLM-ready Markdown or structured JSON.

Target: be a drop-in replacement for Firecrawl with better extraction quality,
vision-based fallback, self-healing selectors, and lower cost when self-hosted.

---

## Core Features

### 1. REST API
Four endpoints, that's it:

| Method | Endpoint | What it does |
|--------|----------|--------------|
| POST | `/scrape` | Scrape one URL → return Markdown or JSON |
| POST | `/crawl` | Crawl an entire site → return job ID |
| GET | `/crawl/{job_id}` | Poll job status + get completed pages |
| POST | `/extract` | Scrape a URL + extract structured fields via schema |

### 2. Crawler Engine
- Playwright for JavaScript-heavy sites (SPAs, infinite scroll, lazy loading)
- Respects `robots.txt` — skip disallowed paths
- Configurable: `max_pages`, `max_depth`, `allowed_domains`, `exclude_patterns`
- Random delays + realistic user agents to avoid blocks
- Follows redirects, handles pagination automatically

### 3. Content Extractor
- Strips navigation, footers, cookie banners, ads
- Returns clean body content as **Markdown** (default), plain text, or raw HTML
- Handles: articles, product pages, docs, blogs
- **Vision fallback**: if DOM extraction confidence is low → take a screenshot →
  send to Claude Vision API → extract content from the image instead

### 4. Structured Extraction
- User sends a JSON schema with field names and types
- System scrapes the page and maps content to the schema using Claude API
- Validates output against schema before returning
- Example input:
  ```json
  {
    "url": "https://example.com/product",
    "schema": {
      "title": "string",
      "price": "number",
      "in_stock": "boolean",
      "description": "string"
    }
  }
  ```

### 5. Self-Healing Selectors
- Track CSS selectors used per domain in a local database
- If a selector fails on re-run, automatically re-derive it from page semantics
- Log selector changes to an audit trail in `memory/selector_audit.jsonl`

### 6. Job Queue
- `POST /crawl` returns `{"job_id": "abc123"}` immediately
- Crawl runs in background via async task queue (asyncio + SQLite)
- `GET /crawl/{job_id}` returns progress + results so far

### 7. Python SDK
- `pip install watercrawl`
- Mirrors Firecrawl SDK interface for easy migration:
  ```python
  from watercrawl import WatercrawlApp
  app = WatercrawlApp(api_url="http://localhost:8000")
  result = app.scrape_url("https://news.ycombinator.com")
  print(result.markdown)
  ```

---

## Tech Stack

| Layer | Choice | Reason |
|-------|--------|--------|
| API framework | FastAPI | async-native, auto-docs |
| Browser automation | Playwright (async) | best JS rendering |
| HTML parsing | BeautifulSoup4 + lxml | fast, reliable |
| AI extraction | Anthropic SDK (`claude-sonnet-4-20250514`) | structured output + vision |
| Job storage | SQLite (aiosqlite) | zero-dependency, file-based |
| Containerization | Docker + docker-compose | single command startup |

No Redis required. No external queue. Runs fully local with one command.

---

## Project Structure (target)

```
src/
├── api/
│   ├── main.py           ← FastAPI app, route registration
│   ├── routes/
│   │   ├── scrape.py     ← POST /scrape
│   │   ├── crawl.py      ← POST /crawl, GET /crawl/{id}
│   │   └── extract.py    ← POST /extract
│   └── models.py         ← Pydantic request/response models
├── crawler/
│   ├── engine.py         ← Playwright crawl logic
│   ├── robots.py         ← robots.txt parser + enforcer
│   └── queue.py          ← async job queue (SQLite-backed)
├── extractor/
│   ├── html.py           ← DOM-based content extraction
│   ├── vision.py         ← Screenshot → Claude Vision fallback
│   ├── structured.py     ← Schema-driven extraction via Claude
│   └── markdown.py       ← HTML → clean Markdown converter
├── healing/
│   ├── selector_db.py    ← Track + repair broken selectors
│   └── audit.py          ← Selector change audit log
├── sdk/
│   └── client.py         ← Python SDK (WebcrawlApp class)
└── config.py             ← Settings from environment variables
```

---

## Environment Variables Required

```
ANTHROPIC_API_KEY=        # required — extraction and vision fallback
HOST=0.0.0.0
PORT=8000
DB_PATH=./data/watercrawl.db
MAX_CONCURRENT_CRAWLS=5
DEFAULT_TIMEOUT=30
DEFAULT_MAX_PAGES=100
LOG_LEVEL=INFO
```

---

## Acceptance Criteria (definition of done)

The project is complete when ALL of the following work:

1. **Scrape endpoint** returns clean Markdown for any public URL
2. **Crawl endpoint** returns a job ID, crawls asynchronously, job status is pollable
3. **Extract endpoint** maps page content to a user-provided JSON schema
4. **Vision fallback** activates when DOM extraction confidence is low
5. **SDK** — `app.scrape_url("https://example.com").markdown` returns non-empty string
6. **Docker** — `docker-compose up` starts the API at `http://localhost:8000`
7. **All tests pass** — `pytest tests/ -v` shows 0 failures
8. **README Quick Start** — a developer can clone and run in under 5 minutes

---

## Out of Scope

- Authentication / API key management
- Rate limiting / billing
- Cloud deployment
- Frontend UI / dashboard
- Webhook callbacks
