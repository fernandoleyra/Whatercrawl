# Research: Async Job Queue Without Redis
**Researcher Agent | T2 | 2026-03-24**

## Question
What is the best approach for an async job queue in Python that does NOT require Redis as a hard dependency, supporting: job creation, status polling, result storage, and concurrent workers?

## Options Considered

### A) aiosqlite + SQLite WAL mode (custom implementation)
- **What it is:** `aiosqlite` wraps Python's built-in `sqlite3` in an async interface using a background thread per connection. WAL (Write-Ahead Logging) mode allows concurrent readers + one writer without full table locks.
- **Dependency:** `aiosqlite` only (pure Python, ~1 file). No Redis. No external services.
- **Async-native:** Yes — all DB calls are `await`-able. Uses `asyncio` natively.
- **Concurrent workers:** WAL mode enables multiple processes/coroutines to read simultaneously; writes are serialized at the SQLite level but non-blocking to the event loop thanks to the thread executor.
- **Pros:** Zero external services, full control over schema, SQLite is universally available, WAL mode gives good concurrent read performance, supports SELECT ... FOR UPDATE equivalent via transactions with `BEGIN IMMEDIATE`.
- **Cons:** Must implement polling loop, retry logic, and worker lifecycle yourself. SQLite write throughput has a ceiling (~1000 TPS for simple inserts on SSD). Not suitable for distributed multi-machine setups.
- **Verdict:** Best fit for single-machine, embedded, or low-to-medium throughput use cases. Exactly what a firecrawl-clone needs.

### B) arq (Async Redis Queue)
- **What it is:** A production-quality async job queue by Samuel Colvin (pydantic author), built specifically for `asyncio`.
- **Redis dependency:** HARD — arq requires Redis as its only broker. There is no SQLite or in-memory backend. Cannot be used without Redis.
- **Verdict:** Eliminated. Does not meet the "no mandatory Redis" requirement.

### C) dramatiq with SQLite broker
- **What it is:** `dramatiq` is a mature task processing library with a pluggable broker interface. It ships with a `StubBroker` for testing and `RabbitmqBroker`/`RedisBroker` for production.
- **SQLite broker:** No official SQLite broker exists in the `dramatiq` package. Third-party `dramatiq-sqlite` projects exist but are unmaintained (last commit 2021, no async support).
- **Async-native:** dramatiq is synchronous/threaded by design. Workers run in threads, not coroutines. Bridging to asyncio requires `asyncio.run()` inside each worker thread — awkward and inefficient.
- **Verdict:** Eliminated. No maintained SQLite broker, not async-native.

### D) Custom asyncio.Queue + SQLite persistence
- **What it is:** An in-memory `asyncio.Queue` for the hot path, with SQLite as a persistence/recovery layer written on enqueue and read on startup.
- **Pros:** Fastest possible enqueue/dequeue (in-memory). Simple.
- **Cons:** In-memory queue is lost on crash unless SQLite recovery logic is carefully implemented. Status polling requires reading SQLite anyway, negating the speed benefit. Two sources of truth (memory + DB) introduce consistency bugs.
- **Verdict:** Overcomplicated for the benefit gained. Pure aiosqlite is simpler and more reliable.

## Recommendation

**Use Option A: pure `aiosqlite` with SQLite WAL mode.**

## Reason

For a firecrawl-clone running on a single machine or container, `aiosqlite` + SQLite WAL is the ideal choice:

1. **Zero external services** — no Redis, no RabbitMQ, no separate process. SQLite is built into Python's stdlib; `aiosqlite` is the only `pip install` needed.
2. **Async-native** — every DB call is a proper coroutine. Multiple worker coroutines can run concurrently in one event loop without blocking.
3. **WAL mode** handles the primary concurrency concern: multiple workers can read job status simultaneously while one writer atomically claims a job via `BEGIN IMMEDIATE` transaction.
4. **Full schema control** — job params, results, errors, and status are all first-class columns. No serialization into opaque blobs.
5. **Sufficient throughput** — web crawling jobs are I/O bound and coarse-grained. A queue handling dozens to hundreds of jobs/minute is well within SQLite's write capacity.
6. **Simplicity** — the entire queue implementation fits in ~100 lines of Python with no abstractions beyond a `JobQueue` class.

arq is the better choice if Redis is already in the stack; dramatiq requires an external broker and is thread-based. Neither satisfies the requirements here.

## SQLite Schema

```sql
-- Enable WAL mode immediately after connecting (per connection, persists to DB file)
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;  -- Safe with WAL; much faster than FULL
PRAGMA busy_timeout = 5000;   -- Wait up to 5s on locked writes before raising

CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,           -- UUID4 as string
    type        TEXT NOT NULL,              -- e.g. 'crawl', 'scrape', 'extract'
    params      TEXT NOT NULL DEFAULT '{}', -- JSON-encoded input parameters
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'done', 'failed')),
    result      TEXT,                       -- JSON-encoded output (NULL until done)
    error       TEXT,                       -- error message/traceback (NULL unless failed)
    worker_id   TEXT,                       -- which worker claimed this job (for debugging)
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

-- Index for the most common worker query: grab oldest pending job
CREATE INDEX IF NOT EXISTS idx_jobs_status_created
    ON jobs (status, created_at)
    WHERE status = 'pending';

-- Index for polling by ID (status checks from API)
-- PRIMARY KEY already covers this; listed for clarity.

-- Index for listing jobs by type + status (dashboard/admin queries)
CREATE INDEX IF NOT EXISTS idx_jobs_type_status
    ON jobs (type, status);
```

## Working Example

```python
"""
job_queue.py — Minimal async job queue using aiosqlite + SQLite WAL mode.

Usage:
    asyncio.run(main())
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import aiosqlite

DB_PATH = "jobs.db"

# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA busy_timeout = 5000;

CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    type        TEXT NOT NULL,
    params      TEXT NOT NULL DEFAULT '{}',
    status      TEXT NOT NULL DEFAULT 'pending'
                    CHECK(status IN ('pending', 'running', 'done', 'failed')),
    result      TEXT,
    error       TEXT,
    worker_id   TEXT,
    created_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now')),
    updated_at  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
);

CREATE INDEX IF NOT EXISTS idx_jobs_status_created
    ON jobs (status, created_at) WHERE status = 'pending';

CREATE INDEX IF NOT EXISTS idx_jobs_type_status
    ON jobs (type, status);
"""


async def init_db(db: aiosqlite.Connection) -> None:
    """Run schema migrations. Safe to call on every startup."""
    await db.executescript(SCHEMA_SQL)
    await db.commit()


# ---------------------------------------------------------------------------
# Job queue operations
# ---------------------------------------------------------------------------


async def enqueue(
    db: aiosqlite.Connection,
    job_type: str,
    params: dict[str, Any],
) -> str:
    """Create a new job and return its UUID."""
    job_id = str(uuid.uuid4())
    await db.execute(
        """
        INSERT INTO jobs (id, type, params)
        VALUES (?, ?, ?)
        """,
        (job_id, job_type, json.dumps(params)),
    )
    await db.commit()
    return job_id


async def dequeue(
    db: aiosqlite.Connection,
    worker_id: str,
) -> Optional[dict[str, Any]]:
    """
    Atomically claim the oldest pending job.

    Uses BEGIN IMMEDIATE to acquire a write lock before the SELECT,
    preventing two workers from claiming the same job (WAL mode still
    allows other readers during this transaction).
    Returns the job dict or None if the queue is empty.
    """
    async with db.execute("BEGIN IMMEDIATE"):
        pass  # aiosqlite executes BEGIN IMMEDIATE as a statement

    # Re-issue as explicit transaction for clarity
    await db.execute("BEGIN IMMEDIATE")
    try:
        async with db.execute(
            """
            SELECT id, type, params, status, created_at
            FROM jobs
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT 1
            """
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            await db.execute("ROLLBACK")
            return None

        job_id, job_type, params_json, status, created_at = row
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"

        await db.execute(
            """
            UPDATE jobs
            SET status = 'running', worker_id = ?, updated_at = ?
            WHERE id = ?
            """,
            (worker_id, now, job_id),
        )
        await db.execute("COMMIT")

        return {
            "id": job_id,
            "type": job_type,
            "params": json.loads(params_json),
            "status": "running",
            "created_at": created_at,
        }
    except Exception:
        await db.execute("ROLLBACK")
        raise


async def complete_job(
    db: aiosqlite.Connection,
    job_id: str,
    result: Any,
) -> None:
    """Mark a job as done and store its result."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    await db.execute(
        """
        UPDATE jobs
        SET status = 'done', result = ?, updated_at = ?
        WHERE id = ?
        """,
        (json.dumps(result), now, job_id),
    )
    await db.commit()


async def fail_job(
    db: aiosqlite.Connection,
    job_id: str,
    error: str,
) -> None:
    """Mark a job as failed and store the error message."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    await db.execute(
        """
        UPDATE jobs
        SET status = 'failed', error = ?, updated_at = ?
        WHERE id = ?
        """,
        (error, now, job_id),
    )
    await db.commit()


async def get_job(
    db: aiosqlite.Connection,
    job_id: str,
) -> Optional[dict[str, Any]]:
    """Fetch a single job by ID (used for status polling)."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM jobs WHERE id = ?", (job_id,)
    ) as cursor:
        row = await cursor.fetchone()
    if row is None:
        return None
    d = dict(row)
    d["params"] = json.loads(d["params"]) if d["params"] else {}
    d["result"] = json.loads(d["result"]) if d["result"] else None
    return d


async def list_jobs_by_status(
    db: aiosqlite.Connection,
    status: str,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Return all jobs with a given status, ordered oldest-first."""
    db.row_factory = aiosqlite.Row
    async with db.execute(
        "SELECT * FROM jobs WHERE status = ? ORDER BY created_at ASC LIMIT ?",
        (status, limit),
    ) as cursor:
        rows = await cursor.fetchall()
    results = []
    for row in rows:
        d = dict(row)
        d["params"] = json.loads(d["params"]) if d["params"] else {}
        d["result"] = json.loads(d["result"]) if d["result"] else None
        results.append(d)
    return results


# ---------------------------------------------------------------------------
# Demo worker
# ---------------------------------------------------------------------------


async def fake_worker(worker_id: str, db_path: str) -> None:
    """Simulated worker: claim one job, process it, mark done."""
    async with aiosqlite.connect(db_path) as db:
        await db.execute("PRAGMA journal_mode = WAL")
        await db.execute("PRAGMA busy_timeout = 5000")

        job = await dequeue(db, worker_id=worker_id)
        if job is None:
            print(f"[{worker_id}] No jobs available.")
            return

        print(f"[{worker_id}] Processing job {job['id']} (type={job['type']})")
        await asyncio.sleep(0.1)  # simulate work

        await complete_job(db, job["id"], result={"pages_crawled": 42, "worker": worker_id})
        print(f"[{worker_id}] Job {job['id']} completed.")


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


async def main() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await init_db(db)

        # Enqueue three jobs
        ids = []
        for i in range(3):
            job_id = await enqueue(db, job_type="crawl", params={"url": f"https://example.com/page{i}"})
            ids.append(job_id)
            print(f"Enqueued job {job_id}")

        # Poll status of first job before processing
        job = await get_job(db, ids[0])
        print(f"Status before processing: {job['status']}")  # -> pending

        # List pending jobs
        pending = await list_jobs_by_status(db, "pending")
        print(f"Pending jobs: {len(pending)}")  # -> 3

    # Run 3 workers concurrently, each with its own connection
    await asyncio.gather(
        fake_worker("worker-1", DB_PATH),
        fake_worker("worker-2", DB_PATH),
        fake_worker("worker-3", DB_PATH),
    )

    # Poll final status
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("PRAGMA journal_mode = WAL")
        for job_id in ids:
            job = await get_job(db, job_id)
            print(f"Job {job_id[:8]}... → status={job['status']}, result={job['result']}")

        done = await list_jobs_by_status(db, "done")
        print(f"Done jobs: {len(done)}")  # -> 3


if __name__ == "__main__":
    asyncio.run(main())
```

## SQLite WAL Mode Concurrency Notes

**What WAL mode changes:**

| Mode | Readers block writers? | Writers block readers? | Concurrent readers |
|------|----------------------|----------------------|-------------------|
| DELETE (default) | Yes | Yes | No |
| WAL | No | No | Yes (unlimited) |

WAL (Write-Ahead Logging) separates reads from writes: readers see the last committed snapshot while a writer appends to the WAL file. This is critical for a job queue where workers are constantly reading status while occasionally writing updates.

**Key settings to apply on every connection:**
```sql
PRAGMA journal_mode = WAL;    -- Persists to DB file; only needs to be set once,
                               -- but harmless to re-apply on each connection open.
PRAGMA synchronous = NORMAL;  -- Safe with WAL (no data loss on crash, just possible
                               -- rollback of last transaction). Much faster than FULL.
PRAGMA busy_timeout = 5000;   -- If a write lock is held by another worker, wait up
                               -- to 5000ms before raising OperationalError.
                               -- Without this, concurrent writers fail immediately.
```

**Preventing double-claiming jobs (the critical section):**

The `dequeue` function uses `BEGIN IMMEDIATE` to acquire a write lock *before* the SELECT. This ensures only one worker can read-and-update atomically:

```
Worker A: BEGIN IMMEDIATE → SELECT pending → UPDATE to running → COMMIT
Worker B: BEGIN IMMEDIATE → (waits for A's lock, released at COMMIT) → SELECT pending (gets different row)
```

Without `BEGIN IMMEDIATE`, two workers could both SELECT the same pending row before either updates it (classic TOCTOU race).

**aiosqlite threading model:**

`aiosqlite` runs each connection's SQLite calls in a dedicated `ThreadPoolExecutor` thread. This means:
- All `await db.execute(...)` calls are non-blocking to the asyncio event loop.
- SQLite's own thread-safety handles the rest.
- Each worker coroutine should open its own `aiosqlite.connect()` context — do NOT share a single connection across concurrent coroutines, as that serializes all DB access.

**WAL checkpoint behavior:**

WAL files grow until a checkpoint is triggered (default: after 1000 pages written). Checkpoints merge the WAL back into the main DB file. For a job queue, this is automatic and transparent. For long-running processes, you can add `PRAGMA wal_autocheckpoint = 1000;` (default) or trigger manually with `PRAGMA wal_checkpoint(TRUNCATE)` during low-activity periods.

**Limits of this approach:**
- Single machine only. WAL does not work across network filesystems (NFS, SMB) — do not put the SQLite file on a network share.
- Write throughput ceiling: ~500–2000 simple writes/second on an SSD. Adequate for crawl job queues; not adequate for high-frequency task queues (use Redis/Postgres for those).
- No pub/sub or push notification. Workers must poll (`SELECT ... WHERE status = 'pending'`). Use a short sleep interval (0.5–2s) to avoid busy-waiting.

## References

- Python `sqlite3` WAL documentation: https://docs.python.org/3/library/sqlite3.html
- SQLite WAL mode official docs: https://www.sqlite.org/wal.html
- `aiosqlite` library (PyPI): https://pypi.org/project/aiosqlite/ — maintained by Omnilib, stable API
- `aiosqlite` GitHub: https://github.com/omnilib/aiosqlite
- `arq` library — Redis required, no SQLite backend: https://arq-docs.helpmanual.io/
- `dramatiq` library — thread-based, no maintained SQLite broker: https://dramatiq.io/
- SQLite `BEGIN IMMEDIATE` semantics: https://www.sqlite.org/lang_transaction.html
- SQLite `busy_timeout` pragma: https://www.sqlite.org/pragma.html#pragma_busy_timeout
