# Watercrawl — Claude Code Plugin

Give Claude Code the ability to scrape pages, crawl entire sites, take screenshots, search the web, and more — powered by your own local Watercrawl service. No cloud account, no rate limits, no data leaving your machine.

---

## Prerequisites

- [Claude Code](https://claude.ai/code) installed
- Docker + Docker Compose

---

## 1. Start the Watercrawl service

The plugin talks to a local Watercrawl API. Clone the repo and start it once:

```bash
git clone https://github.com/YOUR_USERNAME/watercrawl
cd watercrawl
docker-compose up
```

The API is now running at `http://localhost:8000`. Keep this terminal open (or run `docker-compose up -d` to run it in the background).

Verify it's healthy:

```bash
curl http://localhost:8000/docs
```

You should see the Watercrawl OpenAPI page.

---

## 2. Install the plugin

From inside the `watercrawl-plugin/` directory:

```bash
claude plugins install .
```

Or install directly from a published registry entry:

```bash
claude plugins install watercrawl
```

To confirm it's installed:

```bash
claude plugins list
```

You should see `watercrawl` in the list.

---

## 3. Use it

### Via slash commands

Type these directly in any Claude Code session:

| Command | What it does |
|---|---|
| `/watercrawl-scrape` | Scrape one URL — returns clean Markdown (or text / HTML) |
| `/watercrawl-crawl` | Crawl an entire site — follows links, returns all pages as Markdown |
| `/watercrawl-search` | Search the web and return full-page content for each result |
| `/watercrawl-map` | Discover all URLs on a domain via sitemap or link crawl |
| `/watercrawl-batch` | Scrape multiple URLs concurrently |
| `/watercrawl-screenshot` | Take a screenshot of a page and return it as base64 PNG |
| `/watercrawl-interact` | Execute browser actions (click, fill, scroll) on a page |
| `/watercrawl-links` | Extract all links with anchor text and context from a page |
| `/watercrawl-monitor` | Snapshot a page and detect content changes over time |
| `/watercrawl-download` | Download a file from a URL to disk |
| `/watercrawl-extract` | Scrape a URL and extract structured JSON fields you define |

**Examples:**

```
/watercrawl-scrape https://news.ycombinator.com
```

```
/watercrawl-crawl https://docs.python.org max_pages=30
```

```
/watercrawl-search "FastAPI best practices" max_results=5
```

```
/watercrawl-map https://example.com max_urls=100
```

```
/watercrawl-screenshot https://example.com
```

```
/watercrawl-extract https://example.com/product
schema: { "title": "string", "price": "number", "in_stock": "boolean" }
```

### Via natural language (skills)

The plugin registers eleven skills that activate automatically — no slash command needed. Just describe what you want:

- *"Scrape this page and summarize it: https://..."*
- *"Crawl the Stripe docs and find everything about webhooks"*
- *"Search the web for recent FastAPI performance benchmarks"*
- *"Map all URLs on https://example.com"*
- *"Take a screenshot of https://example.com"*
- *"Extract the product name, price, and availability from https://..."*
- *"Click the login button on https://example.com and show the result"*
- *"List all links on https://example.com"*
- *"Download the PDF at https://example.com/report.pdf"*
- *"Snapshot https://example.com and check it again tomorrow for changes"*
- *"Batch scrape these 5 URLs and compare their content"*

Claude will detect the intent and run the right skill.

---

## 4. Configuration

By default the plugin talks to `http://localhost:8000`. To point it at a different host (e.g. a remote or staging instance):

```bash
export WATERCRAWL_URL=http://192.168.1.50:8000
```

Add this to your shell profile (`~/.zshrc`, `~/.bashrc`) to make it permanent.

---

## 5. Uninstall

```bash
claude plugins uninstall watercrawl
```

This removes the plugin from Claude Code. The Watercrawl service itself keeps running until you stop it with `docker-compose down`.

---

## Troubleshooting

**"API down" warning when I run a command**

The plugin checks `$WATERCRAWL_URL/docs` on every invocation. If it can't reach the service:

1. Make sure Docker is running: `docker ps`
2. Start the service: `docker-compose up` (from the `watercrawl/` repo directory)
3. Check `WATERCRAWL_URL` is set correctly if you changed the default port

**Crawl returns empty content on JavaScript-heavy pages**

Watercrawl uses a Playwright headless browser, so JS rendering is handled. If content is still empty, increase the timeout in `.env`:

```
DEFAULT_TIMEOUT=60
```

**Screenshot dimensions show 0x0**

The plugin does not surface width/height from the engine. To get actual dimensions, decode the returned base64 PNG.

**Extraction returns unexpected field values**

The extract skill scrapes the page and then uses Claude Code's native intelligence to fill your schema. If fields are wrong, be more explicit when describing what you want:

```
Extract price_usd as a number (no currency symbol), in_stock as boolean, and title as the main product heading.
```
