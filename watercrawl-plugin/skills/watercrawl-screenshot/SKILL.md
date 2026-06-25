---
name: watercrawl-screenshot
description: |
  Use when the user wants to see what a page looks like, or when text extraction is misleading
  (charts, visual layouts, JS-rendered tables). Triggers on: "take a screenshot", "show me
  what this page looks like", "capture this URL", "screenshot of", "visualize this page",
  "the layout is important", "it's a chart or graph". Returns the image — Claude Code can view it.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
---

# watercrawl-screenshot

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Capture the screenshot**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s -X POST "$BASE_URL/screenshot" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE"}' \
  | python3 -c "
import sys, json, base64, os
d = json.load(sys.stdin)
b64 = d.get('screenshot_b64', '')
if not b64:
    print('No screenshot returned')
    sys.exit(1)
path = '/tmp/watercrawl_screenshot.png'
with open(path, 'wb') as f:
    f.write(base64.standard_b64decode(b64))
print(f'Screenshot saved to {path}')
"
```

2. **Read the saved file** using the Read tool to view the image inline in the Claude Code session. The path is `/tmp/watercrawl_screenshot.png`.

3. **Describe what you see** and answer the user's question based on the visual content.
