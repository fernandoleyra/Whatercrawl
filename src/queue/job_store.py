"""
job_store.py — Async SQLite job store backed by aiosqlite + WAL mode.

Usage:
    store = JobStore()
    await store.init()
    job_id = await store.create_job("crawl", {"url": "https://example.com"})
    await store.update_job(job_id, "done", result={"pages": 5})
    job = await store.get_job(job_id)
    await store.close()
"""

import datetime
import json
import os
import uuid
from typing import Optional

import aiosqlite

DB_PATH_DEFAULT = "webcrawl.db"
BUSY_TIMEOUT_MS = 5000

_CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    params TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','running','done','failed')),
    result TEXT,
    error TEXT,
    worker_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""

_CREATE_INDEX_SQL = """
CREATE INDEX IF NOT EXISTS idx_jobs_status_created
    ON jobs (status, created_at)
    WHERE status = 'pending'
"""


def _utcnow() -> str:
    return datetime.datetime.utcnow().isoformat()


def _row_to_dict(row: aiosqlite.Row) -> dict:
    d = dict(row)
    d["params"] = json.loads(d["params"]) if d["params"] else {}
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


class JobStore:
    """Async SQLite job store. Call await store.init() before any other method."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        self._db_path: str = (
            db_path
            or os.environ.get("WEBCRAWL_DB_PATH")
            or DB_PATH_DEFAULT
        )
        self._conn: Optional[aiosqlite.Connection] = None

    def _require_conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Call init() first.")
        return self._conn

    async def init(self) -> None:
        """Open the SQLite connection, configure WAL mode, and create the schema."""
        self._conn = await aiosqlite.connect(self._db_path)
        self._conn.row_factory = aiosqlite.Row
        try:
            await self._conn.execute("PRAGMA journal_mode = WAL")
            await self._conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
            await self._conn.execute("PRAGMA synchronous = NORMAL")
            await self._conn.execute(_CREATE_TABLE_SQL)
            await self._conn.execute(_CREATE_INDEX_SQL)
            await self._conn.commit()
        except aiosqlite.Error:
            await self._conn.close()
            self._conn = None
            raise

    async def close(self) -> None:
        """Close the underlying SQLite connection."""
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    async def create_job(self, type: str, params: dict) -> str:
        """Insert a new pending job and return its UUID string."""
        conn = self._require_conn()
        job_id = str(uuid.uuid4())
        now = _utcnow()
        try:
            await conn.execute(
                """
                INSERT INTO jobs (id, type, params, status, created_at, updated_at)
                VALUES (?, ?, ?, 'pending', ?, ?)
                """,
                (job_id, type, json.dumps(params), now, now),
            )
            await conn.commit()
        except aiosqlite.Error:
            raise
        return job_id

    async def update_job(
        self,
        job_id: str,
        status: str,
        result: Optional[dict] = None,
        error: Optional[str] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        """Update a job's status and optionally its result, error, and worker_id."""
        conn = self._require_conn()
        now = _utcnow()

        # Build SET clause dynamically — status and updated_at always updated.
        set_parts = ["status = ?", "updated_at = ?"]
        values: list = [status, now]

        if result is not None:
            set_parts.append("result = ?")
            values.append(json.dumps(result))

        if error is not None:
            set_parts.append("error = ?")
            values.append(error)

        if worker_id is not None:
            set_parts.append("worker_id = ?")
            values.append(worker_id)

        values.append(job_id)

        sql = f"UPDATE jobs SET {', '.join(set_parts)} WHERE id = ?"  # noqa: S608
        try:
            await conn.execute(sql, values)
            await conn.commit()
        except aiosqlite.Error:
            raise

    async def get_job(self, job_id: str) -> Optional[dict]:
        """Return a job dict by ID, or None if not found."""
        conn = self._require_conn()
        try:
            async with conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ) as cursor:
                row = await cursor.fetchone()
        except aiosqlite.Error:
            raise
        if row is None:
            return None
        return _row_to_dict(row)

    async def list_jobs(self, status: Optional[str] = None) -> list[dict]:
        """Return all jobs, optionally filtered by status, oldest first."""
        conn = self._require_conn()
        try:
            if status is not None:
                async with conn.execute(
                    "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC",
                    (status,),
                ) as cursor:
                    rows = await cursor.fetchall()
            else:
                async with conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at ASC"
                ) as cursor:
                    rows = await cursor.fetchall()
        except aiosqlite.Error:
            raise
        return [_row_to_dict(row) for row in rows]
