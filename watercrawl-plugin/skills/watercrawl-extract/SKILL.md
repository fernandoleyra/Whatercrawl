---
name: watercrawl-extract
description: |
  Use when the user wants to extract specific structured fields from a URL.
  Triggers on: "extract the product details", "get the price and title from",
  "pull structured data", "scrape the fields", user provides explicit field names.
  Scrapes the page via the local Watercrawl API, then extracts the requested
  fields natively in this Claude Code session — no secondary API key needed.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-extract

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Identify the fields the user wants** — either stated explicitly or infer from context.

2. **Scrape the URL to get page content**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/scrape" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE", "output_format": "markdown"}' \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')) if 'content' in d else print('Error:', d.get('detail','unknown'))"
```

3. **Extract the structured data** — once you have the page content, extract the requested
   fields directly from it and present the result as a JSON object or formatted table.
   Do NOT call an external API to do this — you already have the content and the
   intelligence to extract from it in this session.

## Output

Present results as a formatted JSON block or table per user preference.
