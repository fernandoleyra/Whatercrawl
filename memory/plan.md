# Project Plan: Webcrawl
**Orchestrator-authored | 2026-03-24T00:00:00Z**

---

## 1. What is the user trying to accomplish?

Build a production-grade web scraping API called **Webcrawl** that converts any URL or entire website into clean, LLM-ready Markdown or structured JSON — with vision-based fallback, self-healing selectors, and an async job queue — and package it as a Python SDK.

---

## 2. Tech Stack Decision

| Layer | Choice | Reason |
|-------|--------|--------|
| API Framework | FastAPI | Async-native, auto OpenAPI docs, matches BRIEF |
| Browser Automation | Playwright (async) | Handles JS-heavy sites, better than Selenium |
| Content Cleaning | trafilatura + markdownify | Proven DOM extraction libraries |
| Queue | SQLite (primary), Redis (optional) | Runtime-detected; SQLite removes hard dependency |
| Vision Fallback | Claude API (claude-sonnet-4-20250514) | Specified in BRIEF |
| Structured Extraction | Claude API with JSON schema | Specified in BRIEF |
| SDK | Python package with pip install | Mirrors Firecrawl SDK interface |
| Container | Docker + docker-compose | For Redis optional dependency |

---

## 3. Milestones (7 total, ordered)

### M1: Research Phase
Investigate unknowns before any code is written. Researcher agent only.
- Research async Playwright patterns with FastAPI
- Research SQLite queue implementation (vs Redis)
- Research trafilatura vs alternatives for content extraction
- Research Claude Vision API integration for screenshot fallback

### M2: Core Crawler Engine
Build the Playwright-based browser automation module.
- Crawls single URLs and full sites (configurable depth)
- Respects robots.txt
- Anti-bot: random delays, realistic user agents
- Returns raw HTML + screenshot

### M3: Content Extraction Pipeline
Transform raw HTML into clean Markdown/text/JSON.
- DOM cleaning (strips nav, footer, ads)
- Markdown output via trafilatura/markdownify
- Screenshot-to-Markdown vision fallback via Claude API
- Plain text and raw HTML output modes

### M4: FastAPI API Layer + Async Job Queue
The REST API surface and job management system.
- `POST /scrape` — single URL, sync response
- `POST /crawl` — multi-page, returns job_id immediately
- `GET /crawl/{job_id}` — status + results
- `POST /extract` — structured data via JSON schema
- SQLite job store (Redis if available at runtime)

### M5: Structured Extraction + Self-Healing
Claude API integration for intelligent data extraction.
- JSON schema input → validated JSON output
- Intelligent field mapping via Claude
- Self-healing selectors: re-derives broken selectors from page semantics
- Audit trail log for selector changes

### M6: Python SDK
Pip-installable SDK mirroring Firecrawl interface.
- `webcrawl.scrape(url)` → Markdown
- `webcrawl.crawl(url, max_pages=50)` → job_id
- `webcrawl.get_crawl_status(job_id)` → status dict
- `webcrawl.extract(url, schema)` → structured dict

### M7: Docker + README + Final QA
Packaging and project completion.
- Dockerfile (multi-stage, production-ready)
- docker-compose.yml (app + optional Redis)
- README.md with Quick Start
- End-to-end integration tests
- Final Critic review of all code

---

## 4. Biggest Risks

1. **Playwright in Docker** — browser binaries are large; need multi-stage build
2. **Claude Vision API latency** — vision fallback must be async; don't block crawls
3. **SQLite concurrency** — async writes from multiple crawl workers; need WAL mode
4. **Anti-bot detection** — Playwright fingerprinting; mitigated with realistic agents + delays
5. **Self-healing selectors** — complex; scoped to semantic re-derivation only (not full ML)

---

## 5. Done Criteria

- [ ] `POST /scrape {"url": "https://news.ycombinator.com"}` returns clean Markdown
- [ ] `POST /crawl {"url": "https://docs.python.org", "max_pages": 50}` returns job_id
- [ ] `GET /crawl/{id}` returns progress + completed pages
- [ ] `POST /extract {"url": "...", "schema": {"title": "string", "price": "number"}}` returns JSON
- [ ] All endpoints have passing tests
- [ ] README has working Quick Start
- [ ] Docker build succeeds
- [ ] `pip install -e .` works and SDK functions execute
