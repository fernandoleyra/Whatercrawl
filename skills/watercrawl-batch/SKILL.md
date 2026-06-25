---
name: watercrawl-batch
description: |
  Use when the user has a list of URLs to read and wants all of them fetched at once.
  Triggers on: "scrape all these URLs", "fetch this list", "read all of these pages",
  "get content from each of these", a list of 2+ URLs provided together.
  Faster than scraping one-by-one. Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-batch

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Submit all URLs at once**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/batch" \
  -H "Content-Type: application/json" \
  -d '{
    "urls": ["URL_1", "URL_2", "URL_3"],
    "output_format": "markdown"
  }' | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d['results']:
    print(f'=== {r[\"url\"]} ===')
    if r.get('error'):
        print(f'ERROR: {r[\"error\"]}')
    else:
        print(r['content'][:800])
    print()
"
```

2. **Process results** — each result has `url`, `content`, and an optional `error` field if fetching failed.

## Parameters

- `urls` — list of URLs to scrape (no upper limit, but be mindful of the server's concurrency cap)
- `output_format` — `markdown` (default), `text`, or `html`
