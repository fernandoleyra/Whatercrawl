---
name: watercrawl-scrape
description: |
  Use when the user provides a URL and wants its content as Markdown, plain text, or HTML.
  Triggers on: "scrape", "fetch this page", "get the content from", "grab the docs at",
  "read this URL", "what does this page say". Handles JavaScript-rendered SPAs and pages
  that WebFetch cannot load. Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-scrape

## Prerequisites

Watercrawl API must be running locally. Start it with:
```bash
docker-compose up
```
Default URL: `http://localhost:8000`. Override with env var `WATERCRAWL_URL`.

## Workflow

1. **Verify the API is reachable**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s --max-time 3 "$BASE_URL/docs" | grep -q "Watercrawl" && echo "API up" || echo "API down — run: docker-compose up"
```
If the API is down, tell the user to start the service and stop here.

2. **Scrape the URL**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/scrape" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"URL_HERE\", \"output_format\": \"markdown\"}" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')) if 'content' in d else print('Error:', d.get('detail','unknown'))"
```

3. **Surface the result** directly in the conversation — do not truncate unless the user asks for a summary.

## Output formats

- `markdown` (default) — clean Markdown, vision fallback for JS-heavy pages
- `text` — plain text, no formatting
- `html` — raw HTML

To change format, replace `"markdown"` in the curl command above.
