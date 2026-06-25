---
name: watercrawl-links
description: |
  Use when the user wants to know what links are on a page — to decide which to follow,
  map a site's navigation, or find related content without doing a full crawl.
  Triggers on: "what links are on", "extract all links", "find all URLs on this page",
  "what pages does this link to", "show me the navigation links", "find related pages".
  Returns each link with anchor text and the sentence it appears in.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-links

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Extract all links**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/links" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE", "include_external": true}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(f'Found {d[\"count\"]} links on {d[\"url\"]}:')
for link in d['links']:
    print(f'  [{link[\"text\"]}] {link[\"url\"]}')
    if link['context']:
        print(f'    Context: {link[\"context\"][:100]}')
"
```

2. **Filter or prioritise** — decide which links are worth scraping or crawling based on the anchor text and context, then pass those URLs to `watercrawl-scrape`, `watercrawl-batch`, or `watercrawl-crawl`.

## Parameters

- `url` — the page to extract links from
- `include_external` — if false, only return links on the same domain (default true)
