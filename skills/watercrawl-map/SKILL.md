---
description: Discover all URLs on a domain by following links. Use when asked to map a site, list all pages, or discover the URL structure of a domain.
triggers:
  - "map the site"
  - "list all urls"
  - "discover pages"
  - "site structure"
  - "sitemap"
---

# watercrawl-map

Discover all URLs on a domain.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required.
   - `max_urls` — optional. Default: 50. Maximum: 200.

2. **Try sitemap first**:
   - Fetch `<domain>/sitemap.xml` using WebFetch
   - If it returns valid XML with `<url><loc>` entries, parse those URLs directly
   - Report: `Found sitemap with N URLs`

3. **If no sitemap**, crawl for links:
   - Use the crawl loop from watercrawl-crawl but collect only URLs, not content
   - This is faster — no need to read full page content

4. **Return a sorted URL list**:
   ```
   ## Site Map: <domain>
   **URLs discovered:** N
   **Method:** sitemap / link crawl

   ### All URLs:
   1. https://example.com/
   2. https://example.com/about
   ```
