# Watercrawl

**Web scraping and crawling for Claude Code — no service, no API key, no Docker.**

Watercrawl gives Claude Code the ability to fetch pages, crawl sites, extract structured data, search the web, take screenshots (with Playwright), and monitor pages for changes — using Claude's native WebFetch tool.

## Install

```
/plugin marketplace add fernandoleyra/watercrawl
/plugin install watercrawl
```

Enable it: run `/plugin`, find **watercrawl**, toggle it on, then `/reload-plugins`.

## Quick start

```
/watercrawl-scrape https://news.ycombinator.com
```

```
/watercrawl-crawl https://docs.python.org/3/library/ max_pages=15
```

```
/watercrawl-extract https://example.com/product
schema: { "title": "string", "price": "number", "in_stock": "boolean" }
```

Or use natural language:
- *"Scrape this page and summarize it: https://..."*
- *"Crawl the Stripe docs and find everything about webhooks"*
- *"Extract the product name and price from https://..."*

## Commands

| Command | Description |
|---|---|
| `/watercrawl` | Show available commands |
| `/watercrawl-scrape <url>` | Fetch a single page as Markdown |
| `/watercrawl-crawl <url>` | Crawl a site following links |
| `/watercrawl-extract <url>` | Extract structured JSON fields |
| `/watercrawl-search <query>` | Search the web |
| `/watercrawl-map <url>` | Discover all URLs on a domain |
| `/watercrawl-screenshot <url>` | Take a screenshot (requires Playwright) |
| `/watercrawl-links <url>` | List all links on a page |
| `/watercrawl-batch <urls>` | Scrape multiple URLs |
| `/watercrawl-monitor <url>` | Snapshot and detect changes |

## Optional: Playwright for JS-heavy sites and screenshots

```bash
npm install -g playwright
npx playwright install chromium
```

All commands work without Playwright — it only adds screenshot capture and JS-heavy site support.

## Troubleshooting

**Page content is sparse or empty**
The page may require JavaScript. Install Playwright (see above).

**Screenshot command says "Playwright not available"**
Run: `npm install -g playwright && npx playwright install chromium`

**Crawl returns too many pages**
Use `max_pages=N`: `/watercrawl-crawl https://example.com max_pages=5`

**Extract returns wrong field values**
Be explicit: `"price_usd as a number without currency symbol"`
