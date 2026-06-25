---
description: Crawl an entire website by following links and returning all pages as Markdown. Use when asked to crawl a site, scrape all pages, or get all content from a domain.
triggers:
  - "crawl"
  - "scrape all pages"
  - "get all content from"
  - "spider"
  - "crawl the docs"
---

# watercrawl-crawl

Crawl a website by following links from a starting URL.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required. Starting URL.
   - `max_pages` — optional. Max pages to crawl. Default: 10. Maximum: 50.
   - `same_domain` — optional. `true` (default) to stay on the same domain.
   - `depth` — optional. Max link depth. Default: 3.

2. **Validate inputs**:
   - If `max_pages > 50`, cap at 50 and inform the user.
   - Extract the domain from the starting URL for domain filtering.

3. **Initialize crawl state**:
   - `visited = []` — already-fetched URLs
   - `queue = [starting_url]` — URLs to fetch next
   - `results = []` — collected page data

4. **Crawl loop** (repeat until queue empty OR visited.length >= max_pages):
   a. Take the next URL from the queue
   b. Skip if already visited
   c. Fetch using WebFetch
   d. Add to visited and results: `{ url, title (first H1/H2), word_count, content }`
   e. Extract links: find all `[text](url)` patterns in Markdown
   f. Filter links: same domain only (if same_domain=true), skip anchors, mailto:, tel:
   g. Add new links to queue

5. **Report progress**: `Crawling page N/max_pages: <url>`

6. **Return summary**:
   ```
   ## Crawl Results: <domain>
   **Pages crawled:** N
   **Total words:** ~N

   ### Pages found:
   | # | URL | Title | Words |
   |---|-----|-------|-------|

   ---
   ## Page Content
   ### Page 1: <url>
   <content>
   ```

## Limitations

JavaScript-heavy SPAs may return sparse content via WebFetch. For SPAs, suggest the user install Playwright.
