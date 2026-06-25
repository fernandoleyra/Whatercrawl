---
name: watercrawl-map
description: |
  Use when the user wants to discover all pages on a website or find which page contains something.
  Triggers on: "map the site", "list all pages on", "what pages are under", "find the URL for",
  "which page has", "show me the site structure", "find all links on". Returns a flat list of URLs
  (from sitemap.xml or link crawl). Useful before a targeted scrape or crawl.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-map

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Discover all URLs**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/map" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE", "max_urls": 200, "filter_keyword": ""}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Found {d[\"count\"]} URLs on {d[\"url\"]}:')
for u in d['urls']:
    print(f'  {u}')
"
```

2. **If a keyword filter is needed**, set `filter_keyword` to narrow results (e.g. `"docs"`, `"blog"`, `"api"`).

3. **Present the URL list** and suggest which URLs to scrape or crawl based on the user's goal.

## Parameters

- `url` — root URL of the site to map
- `max_urls` — maximum URLs to return (default 200)
- `filter_keyword` — only return URLs containing this string (optional)
