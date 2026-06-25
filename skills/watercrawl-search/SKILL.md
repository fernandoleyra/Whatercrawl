---
description: Search the web and return full page content for each result. Use when asked to search the web, find information online, or research a topic.
triggers:
  - "search the web"
  - "search for"
  - "find online"
  - "look up"
  - "research"
---

# watercrawl-search

Search the web and return full content for each result.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `query` — required.
   - `max_results` — optional. Default: 3. Maximum: 10.
   - `engine` — optional. `google` (default) or `bing`.

2. **Construct search URL**:
   - Google: `https://www.google.com/search?q=<url-encoded-query>&num=<max_results>`
   - Bing: `https://www.bing.com/search?q=<url-encoded-query>&count=<max_results>`

3. **Fetch the search results page** using WebFetch.

4. **Extract result URLs** from the Markdown — find links that appear as numbered results. Filter out navigation links (settings, maps, images, etc.).

5. **For each result URL** (up to max_results): fetch the full page using WebFetch and note its title.

6. **Return**:
   ```
   ## Search Results: "<query>"
   Found N pages.

   ---
   ### Result 1: <title>
   **URL:** <url>
   <content>
   ```

## Note
Search engines may vary results by location and session. For repeatable results, search specific sites directly.
