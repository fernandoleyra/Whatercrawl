---
description: Snapshot a page and detect content changes compared to a previous snapshot. Use when asked to monitor a page, check for changes, or track updates to a URL.
triggers:
  - "monitor"
  - "watch for changes"
  - "track updates"
  - "snapshot this page"
  - "detect changes"
---

# watercrawl-monitor

Snapshot a page and detect changes compared to a previous snapshot.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required.
   - `action` — `snapshot` (save current state), `diff` (compare with saved), or `check` (snapshot + diff if previous exists). Default: `check`.

2. **Determine snapshot file path**:
   - Create `.watercrawl/snapshots/` in the current working directory
   - Filename: URL-slug (replace `://` and `/` with `_`, strip query strings, truncate to 60 chars) + `.md`

3. **For `snapshot` or `check`**:
   - Fetch the URL using WebFetch
   - Save content to snapshot file with header:
     ```
     <!-- snapshot: <ISO timestamp> -->
     <!-- url: <url> -->
     <content>
     ```
   - Report: `Snapshot saved to <filepath>`

4. **For `diff` or `check` with existing snapshot**:
   - Read the previous snapshot
   - Compare: word count change, added paragraphs, removed paragraphs
   - Report:
     ```
     ## Change Report: <url>
     **Previous snapshot:** <timestamp>
     **Current snapshot:** <timestamp>
     **Word count:** N → M (+/- delta)

     ### Added content
     ### Removed content
     ### No changes detected
     ```

5. **If no previous snapshot** and action is `diff`: take first snapshot and inform user.
