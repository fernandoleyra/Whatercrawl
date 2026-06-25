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


class MapRequest(BaseModel):
    url: str
    max_urls: int = 200
    filter_keyword: str = ""


class MapResponse(BaseModel):
    url: str
    urls: list[str]
    count: int


class InteractAction(BaseModel):
    type: Literal["click", "fill", "wait", "scroll", "press"]
    selector: str = ""
    value: str = ""
    ms: int = 500


class InteractRequest(BaseModel):
    url: str
    actions: list[InteractAction]
    output_format: Literal["markdown", "text", "html"] = "markdown"


class InteractResponse(BaseModel):
    url: str
    content: str
    format: str


class BatchRequest(BaseModel):
    urls: list[str]
    output_format: Literal["markdown", "text", "html"] = "markdown"


class BatchResult(BaseModel):
    url: str
    content: str
    error: str | None = None


class BatchResponse(BaseModel):
    results: list[BatchResult]


class ScreenshotRequest(BaseModel):
    url: str
    full_page: bool = True


class ScreenshotResponse(BaseModel):
    url: str
    screenshot_b64: str
    width: int
    height: int


class LinksRequest(BaseModel):
    url: str
    include_external: bool = True


class LinkItem(BaseModel):
    url: str
    text: str
    context: str


class LinksResponse(BaseModel):
    url: str
    links: list[LinkItem]
    count: int


class MonitorRequest(BaseModel):
    url: str


class MonitorCheckRequest(BaseModel):
    snapshot_id: str


class MonitorDiff(BaseModel):
    added: list[str]
    removed: list[str]
    changed: bool


class MonitorSnapshotResponse(BaseModel):
    snapshot_id: str
    url: str

class MonitorResponse(BaseModel):
    snapshot_id: str
    url: str
    diff: MonitorDiff
    new_snapshot_id: str

