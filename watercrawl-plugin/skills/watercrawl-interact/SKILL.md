---
name: watercrawl-interact
description: |
  Use when a page needs browser interaction to reveal its content — login, button clicks,
  form fills, pagination, or infinite scroll. Triggers on: "click", "fill out", "log in to",
  "submit the form", "load more", "scroll down", "next page", "paginated results",
  "scrape failed — JS required", "interact with". First figure out what actions are needed,
  then build the action sequence and submit it.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-interact

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Action types

| type    | selector required | value required | description                        |
|---------|-------------------|----------------|------------------------------------|
| click   | yes               | no             | Click an element by CSS selector   |
| fill    | yes               | yes            | Type value into an input field     |
| wait    | no                | no             | Wait `ms` milliseconds             |
| scroll  | no                | no             | Scroll one viewport height down    |
| press   | no                | yes            | Press a keyboard key (e.g. Enter)  |

## Workflow

1. **Infer the action sequence** from the user's description of what they need to do on the page.

2. **Submit the interaction**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/interact" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "URL_HERE",
    "actions": [
      {"type": "fill", "selector": "input#username", "value": "user@example.com", "ms": 0},
      {"type": "fill", "selector": "input#password", "value": "PASSWORD", "ms": 0},
      {"type": "click", "selector": "button[type=submit]", "value": "", "ms": 0},
      {"type": "wait", "selector": "", "value": "", "ms": 2000}
    ],
    "output_format": "markdown"
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('content','')[:2000])"
```

3. **Surface the result** and extract what the user asked for.
