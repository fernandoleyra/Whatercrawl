---
description: Take a screenshot of a webpage. Requires Playwright to be installed. Use when asked to take a screenshot, capture a page, or visually inspect a URL.
triggers:
  - "screenshot"
  - "capture page"
  - "take a screenshot"
  - "show me what"
  - "visually check"
---

# watercrawl-screenshot

Take a screenshot of a webpage using Playwright.

## Instructions

1. **Parse arguments** from `$ARGUMENTS`:
   - `url` — required.
   - `width` — optional. Default: 1280.
   - `height` — optional. Default: 800.
   - `full_page` — optional. `true` for full scroll height. Default: `false`.

2. **Check Playwright availability**:
   ```bash
   npx playwright --version 2>/dev/null || echo "NOT_AVAILABLE"
   ```
   If NOT_AVAILABLE, inform the user:
   > "Playwright is not installed. To use screenshot capture, install it with:
   > `npm install -g playwright && npx playwright install chromium`
   > Then try this command again."
   Stop here.

3. **Generate a safe output filename** from the URL (replace non-alphanumeric chars with underscores, max 50 chars, add .png).

4. **Run Playwright screenshot**:
   ```bash
   node -e "
   const { chromium } = require('playwright');
   (async () => {
     const browser = await chromium.launch();
     const page = await browser.newPage();
     await page.setViewportSize({ width: WIDTH, height: HEIGHT });
     await page.goto('URL', { waitUntil: 'networkidle', timeout: 30000 });
     await page.screenshot({ path: 'OUTFILE', fullPage: FULL_PAGE });
     await browser.close();
     console.log('DONE');
   })().catch(e => { console.error(e.message); process.exit(1); });
   "
   ```
   Replace WIDTH, HEIGHT, URL, OUTFILE, FULL_PAGE with actual values.

5. **Return**: "Screenshot saved to `<filename>`. Use Read to view the image."

## Error handling
- Launch failure: suggest `npx playwright install chromium`
- Navigation timeout: suggest checking the URL or increasing timeout
