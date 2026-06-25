---
description: Scrape multiple URLs concurrently and return all content. Use when asked to scrape multiple pages, fetch several URLs, or compare content from multiple sites.
triggers:
  - "batch scrape"
  - "scrape multiple"
  - "fetch these urls"
  - "get content from all"
  - "compare these pages"
---

# watercrawl-batch

Scrape multiple URLs and return all content.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `urls` — required. Newline- or comma-separated list of URLs. Maximum: 20.
   - `format` — optional. `markdown` (default) or `text`.

2. **If no URLs provided**, ask the user for a list of URLs.

3. **Cap at 20 URLs** if more are provided.

4. **Fetch each URL** sequentially using WebFetch. Report progress: `Fetching URL N/total: <url>`

5. **Return all results**:
   ```
   ## Batch Scrape Results
   **URLs requested:** N
   **Successful:** X
   **Failed:** Y

   ---
   ### 1. <url>
   **Status:** OK | Failed (<reason>)
   **Words:** ~N
   <content>
   ```
