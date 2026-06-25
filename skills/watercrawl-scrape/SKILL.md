---
description: Scrape a single URL and return its content as clean Markdown, plain text, or raw HTML. Use when asked to fetch, scrape, read, or get the content of a webpage.
triggers:
  - "scrape"
  - "fetch page"
  - "get content of"
  - "read this url"
  - "extract content from"
---

# watercrawl-scrape

Scrape a single URL and return clean content.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required. The URL to scrape.
   - `format` — optional. `markdown` (default), `text`, or `html`.

2. **Fetch the page** using the WebFetch tool with the provided URL.

3. **Process the response**:
   - If `format=markdown` (default): return the content as-is from WebFetch (already Markdown). Clean up navigation artifacts: remove repeated navigation menus, cookie banners, and footer boilerplate visible as plain text blocks.
   - If `format=text`: strip all Markdown formatting (headers, links, bold) and return plain text.
   - If `format=html`: inform the user that raw HTML is not available via WebFetch; offer the Markdown version instead.

4. **Check content quality**:
   - If the returned content is fewer than 50 words, the page may be JavaScript-rendered. Inform the user: "This page may require JavaScript to render. If you have Playwright installed (`npm install -g playwright`), I can try a Bash-based approach to get the full content."
   - If Playwright is available, offer to use it.

5. **Return** the processed content with:
   - Source URL: `**Source:** <url>`
   - Word count: `**Words:** ~N`
   - The content body

## Playwright fallback (if requested)

Check if Playwright is available:
```bash
which playwright 2>/dev/null && echo "available" || npx playwright --version 2>/dev/null || echo "NOT_AVAILABLE"
```

If available, run:
```bash
node -e "
const { chromium } = require('playwright');
(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('URL_HERE', { waitUntil: 'networkidle' });
  const content = await page.content();
  console.log(content);
  await browser.close();
})();
" 2>/dev/null
```
Replace URL_HERE with the actual URL. Parse the returned HTML yourself.

## Error handling

- Network error: report the error and suggest checking the URL
- 403/404/5xx: report the status and suggest verifying the URL
- Timeout: inform the user and suggest retrying
