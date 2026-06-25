---
name: watercrawl-download
description: |
  Use when the user wants to save an entire website as local markdown files — for offline analysis,
  feeding into a vector DB, or archival. Triggers on: "download the site", "save as local files",
  "offline copy", "download all the docs", "save for reference", "bulk save".
  Crawls the site via the local Watercrawl API, then writes each page as a .md file.
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
  - Bash(mkdir *)
  - Bash(sleep *)
---

# watercrawl-download

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

1. **Start the crawl job**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
JOB=$(curl -s -X POST "$BASE_URL/crawl" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE", "max_pages": 100, "max_depth": 3}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('job_id',''))")
echo "Crawl job: $JOB"
```

2. **Poll until complete**
```bash
for i in $(seq 1 60); do
  STATUS=$(curl -s "$BASE_URL/crawl/$JOB" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'], len(d.get('pages',[])))")
  echo "[$i/60] $STATUS"
  echo "$STATUS" | grep -q "done" && break
  sleep 5
done
```

3. **Write pages to local files**
```bash
OUTPUT_DIR="OUTPUT_DIR_HERE"
mkdir -p "$OUTPUT_DIR"
curl -s "$BASE_URL/crawl/$JOB" | python3 -c "
import sys, json, re, os
data = json.load(sys.stdin)
output_dir = '$OUTPUT_DIR'
for page in data.get('pages', []):
    url = page['url']
    content = page.get('content', '')
    if not content:
        continue
    # Derive filename from URL path
    path = re.sub(r'https?://[^/]+', '', url).strip('/')
    path = re.sub(r'[^a-zA-Z0-9/_-]', '_', path) or 'index'
    filepath = os.path.join(output_dir, path + '.md')
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w') as f:
        f.write(f'# Source: {url}\n\n')
        f.write(content)
    print(f'Wrote {filepath}')
print(f'Done — {len(data[\"pages\"])} pages saved to {output_dir}')
"
```

4. **Confirm to the user** how many files were saved and where.

## Parameters

- `max_pages` — maximum pages to crawl (default 100)
- `max_depth` — maximum link depth (default 3)
- `OUTPUT_DIR` — local directory to write files into (ask the user or default to `./watercrawl-output/<domain>`)
