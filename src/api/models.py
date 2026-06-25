"""
src/api/models.py — Pydantic request and response models for the FastAPI app.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class ScrapeRequest(BaseModel):
    url: str
    output_format: Literal["markdown", "text", "html"] = "markdown"


class CrawlRequest(BaseModel):
    url: str
    max_pages: int = 50
    max_depth: int = 3
    output_format: str = "markdown"


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------


class ScrapeResponse(BaseModel):
    url: str
    content: str
    format: str
    crawled_at: str


class CrawlJobResponse(BaseModel):
    job_id: str
    status: str


class CrawlStatusResponse(BaseModel):
    job_id: str
    status: str
    pages: list[dict]


class SearchRequest(BaseModel):
    query: str
    max_results: int = 5
    output_format: Literal["markdown", "text"] = "markdown"


class SearchResult(BaseModel):
    url: str
    title: str
    snippet: str
    content: str


class SearchResponse(BaseModel):
    query: str
    results: list[SearchResult]


