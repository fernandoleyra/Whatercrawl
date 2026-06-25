---
name: watercrawl-monitor
description: |
  Use when the user wants to watch a page for changes over time. Triggers on: "monitor",
  "watch for changes", "track", "alert me when", "notify when X changes", "has this changed",
  "check if the price changed", "is there anything new on". Takes a baseline snapshot,
  re-checks on demand, and reports only real content changes (not timestamps or formatting).
  Requires local Watercrawl API at localhost:8000.
allowed-tools:
  - Bash(curl *)
  - Bash(python3 *)
  - Bash(sleep *)
---

# watercrawl-monitor

## Prerequisites

Watercrawl API must be running. Start with `docker-compose up`.

## Workflow

### One-time check (has this page changed?)

1. **Take a baseline snapshot**
```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
SNAP=$(curl -s -X POST "$BASE_URL/monitor/snapshot" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['snapshot_id'])")
echo "Snapshot: $SNAP"
```

2. **Check for changes (run again later)**
```bash
curl -s -X POST "$BASE_URL/monitor/check" \
  -H "Content-Type: application/json" \
  -d "{\"snapshot_id\": \"$SNAP\"}" \
  | python3 -c "
import sys, json
d = json.load(sys.stdin)
diff = d['diff']
if not diff['changed']:
    print('No changes detected.')
else:
    print('CHANGES DETECTED:')
    for line in diff.get('added', []):
        print(f'  + {line}')
    for line in diff.get('removed', []):
        print(f'  - {line}')
print(f'New snapshot ID: {d[\"new_snapshot_id\"]}')
"
```

### Polling loop (watch continuously)

```bash
BASE_URL=${WATERCRAWL_URL:-http://localhost:8000}
SNAP=$(curl -s -X POST "$BASE_URL/monitor/snapshot" \
  -H "Content-Type: application/json" \
  -d '{"url": "URL_HERE"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['snapshot_id'])")

while true; do
  sleep 300  # check every 5 minutes
  RESULT=$(curl -s -X POST "$BASE_URL/monitor/check" \
    -H "Content-Type: application/json" \
    -d "{\"snapshot_id\": \"$SNAP\"}")
  CHANGED=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['diff']['changed'])")
  if [ "$CHANGED" = "True" ]; then
    echo "CHANGE DETECTED:"
    echo "$RESULT" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for line in d['diff']['added']: print(f'+ {line}')
for line in d['diff']['removed']: print(f'- {line}')
"
  fi
  SNAP=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['new_snapshot_id'])")
done
```
