---
name: watercrawl-crawl
description: |
  Use when the user wants to crawl an entire site or multiple pages under a URL.
  Triggers on: "crawl", "get all pages from", "extract everything under /docs",
  "bulk scrape", "get all articles from", "scrape the whole site".
  Starts a background job and polls until done. Requires local Watercrawl API.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
  - Bash(sleep *)
---

# watercrawl-crawl

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Start the crawl job**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
JOB=$(curl -s -X POST "$BASE_URL/crawl" \
  -H "Content-Type: application/json" \
  -d "{\"url\": \"URL_HERE\", \"max_pages\": 50, \"max_depth\": 3}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))")
echo "Job started: $JOB"
```

2. **Poll until complete** (check every 5 seconds, timeout after 5 minutes)
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
for i in $(seq 1 60); do
  STATUS=$(curl -s "$BASE_URL/crawl/$JOB" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], len(d.get('pages',[])))")
  echo "[$i/60] $STATUS"
  echo "$STATUS" | grep -q "done" && break
  sleep 5
done
```

3. **Retrieve results**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
curl -s "$BASE_URL/crawl/$JOB" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
for p in d.get('pages', []):
    print(f'### {p[\"url\"]}')
    print(p.get('content','')[:500])
    print()
"
```

## Parameters

- `max_pages` — maximum pages to crawl (default 50)
- `max_depth` — maximum link depth from seed URL (default 3)
