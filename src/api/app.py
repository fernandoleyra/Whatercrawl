"""
src/api/app.py — FastAPI application with lifespan and 3 endpoints.

Endpoints:
  POST /scrape        — Scrape a single URL and return extracted content.
  POST /crawl         — Start a background site-crawl job.
  GET  /crawl/{job_id} — Poll the status of a crawl job.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime
from typing import AsyncGenerator

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from src.api.models import (
    CrawlJobResponse,
    CrawlRequest,
    CrawlStatusResponse,
    MapRequest,
    MapResponse,
    ScrapeRequest,
    ScrapeResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
)
from src.crawler.engine import CrawlerEngine
from src.crawler.mapper import map_site
from src.crawler.search import search_web
from src.crawler.site_crawler import crawl_site
from src.extractor.extractor import ContentExtractor
from src.queue.job_store import JobStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_CONCURRENT: int = int(os.environ.get("MAX_CONCURRENT_CRAWLS", "5"))


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------


async def _run_crawl_job(state, job_id: str, req: CrawlRequest) -> None:
    """Drive a site crawl in the background and persist results to JobStore."""
    try:
        await state.job_store.update_job(job_id, status="running")
        async with state.semaphore:
            results = await crawl_site(
                state.crawler,
                req.url,
                max_pages=req.max_pages,
                max_depth=req.max_depth,
            )
        pages = []
        for r in results:
            if r["error"]:
                pages.append({"url": r["url"], "content": "", "error": r["error"]})
            else:
                content = state.extractor.extract_markdown(r["html"])
                pages.append({"url": r["url"], "content": content, "error": None})
        await state.job_store.update_job(job_id, status="done", result=pages)
    except Exception as exc:  # noqa: BLE001
        logger.error("Crawl job %s failed: %s", job_id, exc)
        await state.job_store.update_job(job_id, status="failed", error=str(exc))


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start shared resources on startup; shut them down cleanly on exit."""
    crawler = CrawlerEngine()
    job_store = JobStore()
    await job_store.init()
    extractor = ContentExtractor()
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)

    app.state.crawler = crawler
    app.state.job_store = job_store
    app.state.extractor = extractor
    app.state.semaphore = semaphore

    logger.info("FastAPI app started (MAX_CONCURRENT_CRAWLS=%d).", MAX_CONCURRENT)

    try:
        yield
    finally:
        await crawler.close()
        await job_store.close()
        logger.info("FastAPI app shut down cleanly.")


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Watercrawl",
    description="Playwright-powered web crawl and extraction API.",
    version="0.1.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@app.post("/scrape", response_model=ScrapeResponse)
async def scrape(req: ScrapeRequest, request: Request) -> ScrapeResponse:
    """Crawl a single URL and return its content in the requested format."""
    crawler: CrawlerEngine = request.app.state.crawler
    extractor: ContentExtractor = request.app.state.extractor
    semaphore: asyncio.Semaphore = request.app.state.semaphore

    await semaphore.acquire()
    try:
        result = await crawler.crawl_url(req.url)

        if result["error"]:
            raise HTTPException(
                status_code=502,
                detail=result["error"],
            )

        html: str = result["html"]

        if req.output_format == "markdown":
            content = extractor.extract_markdown(html)
        elif req.output_format == "text":
            content = extractor.extract_text(html)
        else:  # "html"
            content = extractor.extract_raw(html)

        return ScrapeResponse(
            url=req.url,
            content=content,
            format=req.output_format,
            crawled_at=datetime.utcnow().isoformat(),
        )
    finally:
        semaphore.release()


@app.post("/crawl", response_model=CrawlJobResponse)
async def crawl(
    req: CrawlRequest,
    background_tasks: BackgroundTasks,
    request: Request,
) -> CrawlJobResponse:
    """Start a background site-crawl job and return its job ID."""
    job_store: JobStore = request.app.state.job_store

    job_id: str = await job_store.create_job(
        "crawl",
        {
            "url": req.url,
            "max_pages": req.max_pages,
            "max_depth": req.max_depth,
            "output_format": req.output_format,
        },
    )

    background_tasks.add_task(
        _run_crawl_job,
        request.app.state,
        job_id,
        req,
    )

    return CrawlJobResponse(job_id=job_id, status="pending")


@app.get("/crawl/{job_id}", response_model=CrawlStatusResponse)
async def get_crawl_status(job_id: str, request: Request) -> CrawlStatusResponse:
    """Return the current status and results of a crawl job."""
    job_store: JobStore = request.app.state.job_store

    job = await job_store.get_job(job_id)

    if job is None:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found.",
        )

    return CrawlStatusResponse(
        job_id=job_id,
        status=job["status"],
        pages=job["result"] or [],
    )


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request) -> SearchResponse:
    """Search the web and return full-page content for each result."""
    crawler: CrawlerEngine = request.app.state.crawler
    extractor: ContentExtractor = request.app.state.extractor
    semaphore: asyncio.Semaphore = request.app.state.semaphore

    await semaphore.acquire()
    try:
        results = await search_web(
            crawler, req.query, max_results=req.max_results, output_format=req.output_format,
            extractor=extractor,
        )
        return SearchResponse(
            query=req.query,
            results=[SearchResult(**r) for r in results],
        )
    finally:
        semaphore.release()


@app.post("/map", response_model=MapResponse)
async def map_urls(req: MapRequest, request: Request) -> MapResponse:
    """Discover all URLs on a domain via sitemap or link crawl."""
    crawler: CrawlerEngine = request.app.state.crawler
    semaphore: asyncio.Semaphore = request.app.state.semaphore

    await semaphore.acquire()
    try:
        urls = await map_site(
            crawler, req.url, max_urls=req.max_urls, filter_keyword=req.filter_keyword
        )
        return MapResponse(url=req.url, urls=urls, count=len(urls))
    finally:
        semaphore.release()

