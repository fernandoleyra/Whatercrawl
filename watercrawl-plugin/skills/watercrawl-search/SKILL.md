---
name: watercrawl-search
description: |
  Use when the user wants to search the web and get full page content — not just snippets.
  Triggers on: "search for", "find articles about", "look up", "research",
  "find recent news on", "what are people saying about", "find sources on".
  Returns full-page markdown for each result — far richer than built-in WebSearch.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-search

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Submit the search**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "QUERY_HERE", "max_results": 5, "output_format": "markdown"}' \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for r in d.get('results', []):
    print(f'## {r[\"title\"]}')
    print(f'URL: {r[\"url\"]}')
    print(f'Snippet: {r[\"snippet\"]}')
    print()
    print(r['content'][:1000])
    print('---')
"
```

2. **Synthesize the results** — read the full content from each result and answer the user's research question directly. Surface sources inline.

## Parameters

- `query` — the search query string
- `max_results` — number of pages to fetch and return (default 5, max 10)
- `output_format` — `markdown` (default) or `text`
