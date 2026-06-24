---
name: watercrawl-extract
description: |
  Use when the user wants to extract specific structured fields from a URL.
  Triggers on: "extract the product details", "get the price and title from",
  "pull structured data", "scrape the fields", user provides explicit field names.
  Sends a JSON schema to the Watercrawl API and returns validated structured output.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-extract

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.
`ANTHROPIC_API_KEY` must be set in the service's `.env` — extraction uses Claude.

## Workflow

1. **Identify the fields the user wants** — either stated explicitly or infer from context.

2. **Build and submit the extraction request**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/extract" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "URL_HERE",
    "schema": {
      "type": "object",
      "properties": {
        "FIELD_1": {"type": "string"},
        "FIELD_2": {"type": "number"}
      },
      "required": ["FIELD_1", "FIELD_2"]
    }
  }' | python3 -c "import sys,json; d=json.load(sys.stdin); print(json.dumps(d.get('data',d), indent=2))"
```

3. **Surface the result** as a formatted table or JSON block per user preference.

## Schema types

Supported field types in the schema: `string`, `number`, `boolean`, `array`, `object`.
