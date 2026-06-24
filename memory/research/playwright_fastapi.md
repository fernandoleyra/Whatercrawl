# Research: Playwright + FastAPI Async Integration
**Researcher Agent | T1 | 2026-03-24**

## Question
What is the best async Python approach for combining Playwright browser automation with FastAPI? Does Playwright's async API work within FastAPI request lifecycle? What are the known pitfalls with event loops?

---

## Options Considered

### A) One browser instance per request (naive approach)
Launch a new browser for every incoming HTTP request using `async_playwright().start()` inside the route handler.

- Pros:
  - Simple to implement
  - Complete isolation between requests — no shared state
  - No resource contention between concurrent users
- Cons:
  - Very slow — browser cold-start (~300–800ms per launch for Chromium)
  - High memory usage under any meaningful concurrency
  - Risk of resource leaks if exceptions occur before cleanup
  - Does not scale; each browser process is ~100–200 MB

### B) Shared browser instance via FastAPI lifespan (recommended)
Launch a single `Browser` instance during application startup using FastAPI's `lifespan` context manager. Share it across all requests; create a new `BrowserContext` per request (or per session).

- Pros:
  - Browser launched once — amortizes startup cost
  - Low memory footprint relative to option A
  - `BrowserContext` provides per-request isolation (cookies, storage, auth)
  - Clean startup/shutdown lifecycle managed by FastAPI
  - Fully async — no event loop conflicts
- Cons:
  - Shared browser can crash and bring down all in-flight requests; needs restart logic
  - Requires careful context cleanup to prevent leaks
  - Concurrency limited by the browser's own process capacity (mitigated by context pooling)

### C) Browser context pool (production-grade)
Maintain a pool of pre-warmed `BrowserContext` instances using `asyncio.Queue` or a dedicated pool library, checked out per request and returned on completion.

- Pros:
  - Best throughput under high concurrency
  - Bounded resource usage (pool size cap)
  - Avoids per-request context creation overhead (~20–50ms)
- Cons:
  - Most complex to implement correctly (checkout/return, timeout, replacement on error)
  - Overkill for low-to-medium traffic scenarios
  - Context state can leak between requests if not reset properly

### D) Running Playwright in a thread pool via `asyncio.run_in_executor` with sync API
Use the synchronous Playwright API (`playwright.sync_api`) in a `ThreadPoolExecutor`.

- Pros:
  - Avoids async complexity
- Cons:
  - Defeats the purpose of an async stack
  - Thread-per-request model; GIL contention
  - Sync Playwright internally manages its own event loop — conflicts with FastAPI's loop
  - Not recommended; known to cause deadlocks when mixing sync and async Playwright

---

## Recommendation

**Option B — Shared browser instance launched in FastAPI `lifespan`, with a new `BrowserContext` created and closed per request.**

For a firecrawl-style scraping service, add a simple semaphore (e.g. `asyncio.Semaphore(20)`) to bound concurrency. Upgrade to Option C (context pool) only if profiling shows context-creation latency is a bottleneck.

---

## Reason

Playwright's `async_playwright` is designed to run on an `asyncio` event loop. FastAPI's async route handlers run on the same `asyncio` event loop managed by `uvicorn`. There is **no event loop conflict** as long as you use `async_playwright` (not the sync API) and do not call `asyncio.run()` from within a handler (which would attempt to create a nested event loop and raise `RuntimeError: This event loop is already running`).

The `lifespan` context manager (introduced as the recommended pattern in FastAPI 0.93+) provides the correct hook for managing long-lived async resources like a browser. Storing the `Browser` and `Playwright` objects in `app.state` makes them accessible to route handlers without globals.

---

## Working Code Snippet

```python
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright, Browser, Playwright
from pydantic import BaseModel

# --------------------------------------------------------------------------- #
# Lifespan: manages browser startup and shutdown                               #
# --------------------------------------------------------------------------- #

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Launch Chromium once on startup; close on shutdown."""
    pw: Playwright = await async_playwright().start()
    browser: Browser = await pw.chromium.launch(
        headless=True,
        args=["--no-sandbox", "--disable-dev-shm-usage"],  # required in Docker
    )
    app.state.browser = browser
    app.state.playwright = pw
    app.state.semaphore = __import__("asyncio").Semaphore(20)  # max 20 concurrent pages
    try:
        yield
    finally:
        await browser.close()
        await pw.stop()


app = FastAPI(lifespan=lifespan)


# --------------------------------------------------------------------------- #
# Request / response models                                                    #
# --------------------------------------------------------------------------- #

class ScrapeRequest(BaseModel):
    url: str
    timeout_ms: int = 30_000


class ScrapeResponse(BaseModel):
    url: str
    title: str
    html: str


# --------------------------------------------------------------------------- #
# Route handler                                                                #
# --------------------------------------------------------------------------- #

@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest) -> ScrapeResponse:
    browser: Browser = app.state.browser
    semaphore = app.state.semaphore

    async with semaphore:  # bound concurrency
        # BrowserContext = isolated session (cookies, localStorage) per request
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        try:
            page = await context.new_page()
            response = await page.goto(
                req.url,
                timeout=req.timeout_ms,
                wait_until="domcontentloaded",
            )
            if response is None or not response.ok:
                status = response.status if response else 0
                raise HTTPException(status_code=502, detail=f"Page returned HTTP {status}")

            title = await page.title()
            html = await page.content()
            return ScrapeResponse(url=req.url, title=title, html=html)

        except Exception as exc:
            # Re-raise HTTPExceptions directly; wrap others
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=500, detail=str(exc)) from exc

        finally:
            # CRITICAL: always close the context to release resources
            await context.close()
```

**Running:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

**Docker note:** Pass `--no-sandbox` and `--disable-dev-shm-usage` in `launch()` args when running inside a container, or the browser will crash on start.

---

## Known Pitfalls

1. **Never use `asyncio.run()` inside a FastAPI route handler.** FastAPI's handlers already execute inside a running event loop. Calling `asyncio.run()` raises `RuntimeError: This event loop is already running`. Use `await` directly.

2. **Never mix sync and async Playwright in the same process.** The sync API (`from playwright.sync_api import sync_playwright`) spawns its own event loop internally. Importing and using it alongside `async_playwright` in the same uvicorn worker causes hard-to-debug deadlocks or `SelectorThread` errors.

3. **Always close `BrowserContext` in a `finally` block.** An unhandled exception mid-scrape will leave an open context. Each open context holds a separate browser process memory partition; leaks accumulate quickly and OOM-kill the process.

4. **Do not call blocking sync I/O from async route handlers.** Any synchronous blocking call (e.g. `time.sleep()`, `requests.get()`, synchronous file I/O) inside an `async def` handler blocks the entire uvicorn event loop, freezing all in-flight Playwright operations. Use `asyncio.sleep()`, `httpx.AsyncClient`, and `aiofiles` instead.

5. **`page.goto()` default timeout is 30 seconds — set it explicitly.** If not set, a hanging page will block a semaphore slot for 30 seconds. In a scraping service, set aggressive timeouts (10–15 s) and use `wait_until="domcontentloaded"` rather than `"networkidle"` to avoid waiting for analytics/ad beacons.

6. **Browser crash does not raise in the route handler automatically.** If the shared browser process dies (OOM, segfault), subsequent `browser.new_context()` calls raise `playwright._impl._errors.Error: Browser has been closed`. Add a health-check endpoint and a restart wrapper (e.g. re-run the lifespan logic, or use a supervisor process like a `BrowserManager` class with reconnect logic).

7. **Chromium `--disable-dev-shm-usage` is mandatory in Docker** (default `/dev/shm` is 64 MB, far too small for Chromium). Without it, the renderer crashes silently and pages return empty HTML.

8. **`async_playwright().start()` must be awaited and the returned object must be stopped.** Failing to call `await pw.stop()` on shutdown leaves the Playwright subprocess running as a zombie. Always pair `.start()` with `.stop()` in a `try/finally` or `lifespan` block.

9. **Uvicorn worker count vs. browser instances.** Each uvicorn worker process has its own event loop and its own browser instance. With `--workers 4`, you have 4 browsers. Account for this in memory sizing: `workers * (browser_base_mem + contexts * context_mem)`.

10. **`pytest-asyncio` conflicts when testing.** When writing tests with `pytest-asyncio`, use `@pytest.fixture(scope="session")` for the browser to avoid creating/destroying it per test. Use `asyncio_mode = "auto"` in `pytest.ini` to avoid manual `@pytest.mark.asyncio` decoration.

---

## References

- Playwright Python async API documentation: https://playwright.dev/python/docs/api/class-playwright
- FastAPI lifespan events documentation: https://fastapi.tiangolo.com/advanced/events/
- `async_playwright` context manager pattern (playwright-python GitHub): https://github.com/microsoft/playwright-python
- FastAPI `app.state` for shared resources: https://fastapi.tiangolo.com/advanced/dataclasses/#use-request-state
- Uvicorn deployment guide (worker processes): https://www.uvicorn.org/deployment/
- Python `asyncio.Semaphore` for concurrency bounding: https://docs.python.org/3/library/asyncio-sync.html#asyncio.Semaphore
