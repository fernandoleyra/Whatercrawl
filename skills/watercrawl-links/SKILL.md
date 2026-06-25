---
description: Extract all links from a page with anchor text and context. Use when asked to list links, find all links on a page, or audit links.
triggers:
  - "list links"
  - "extract links"
  - "find all links"
  - "links on this page"
---

# watercrawl-links

Extract all links from a page with anchor text.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required.
   - `filter` — optional. `internal` (same domain), `external` (other domains), `all` (default).

2. **Fetch the page** using WebFetch.

3. **Extract all links**: find all `[anchor text](href)` patterns from the Markdown.

4. **Classify each link**: internal (same domain as source) or external.

5. **Apply filter** based on `filter` argument.

6. **Return**:
   ```
   ## Links on <url>
   **Total:** N links (X internal, Y external)

   ### Internal Links
   | Anchor Text | URL |
   |---|---|

   ### External Links
   | Anchor Text | URL |
   |---|---|
   ```
