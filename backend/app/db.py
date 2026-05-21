"""SQLite-backed cache for expensive external API responses.

Design notes:
    - One table per upstream source (places, solar, overpass, vision).
      We could collapse into one table with a `source` column, but separate
      tables make ad-hoc inspection in `sqlite3` easier for the field-ops
      person debugging a weird result.
    - The cache key is a SHA256 of the canonicalized request payload. That
      lets us re-key without migrating: bump the hash recipe and old
      entries simply miss.
    - We also write a `cost_log` table so the UI can show per-search spend.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings
from app.logging_config import get_logger

logger = get_logger(__name__)


SCHEMA = """
CREATE TABLE IF NOT EXISTS places_cache (
    key TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS solar_cache (
    key TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS overpass_cache (
    key TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS vision_cache (
    key TEXT PRIMARY KEY,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS cost_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    search_id TEXT NOT NULL,
    api TEXT NOT NULL,
    operation TEXT NOT NULL,
    cost_usd REAL NOT NULL,
    latency_ms INTEGER NOT NULL,
    success INTEGER NOT NULL,
    created_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cost_search ON cost_log (search_id);
"""


def _db_path() -> Path:
    """Resolve and create parent dir for the SQLite file."""
    path = Path(get_settings().cache_db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def init_db() -> None:
    """Create tables if they don't exist. Safe to call repeatedly."""
    with connection() as conn:
        conn.executescript(SCHEMA)
    logger.info("SQLite cache ready at %s", _db_path())


@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with sensible defaults.

    Using a context manager + explicit close because long-running uvicorn
    processes can leak handles otherwise.
    """
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def cache_key(payload: dict[str, Any]) -> str:
    """Stable hash for a request payload.

    Sort keys to make the hash insensitive to dict ordering, which matters
    because different code paths might build the same logical request in
    different orders.
    """
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_get(table: str, key: str) -> dict[str, Any] | None:
    """Return a cached response payload or None if not present."""
    assert table in {"places_cache", "solar_cache", "overpass_cache", "vision_cache"}
    with connection() as conn:
        row = conn.execute(
            f"SELECT response_json FROM {table} WHERE key = ?", (key,)
        ).fetchone()
    if not row:
        return None
    return json.loads(row["response_json"])


def cache_put(table: str, key: str, request: dict[str, Any], response: dict[str, Any]) -> None:
    """Insert or replace a cache entry."""
    assert table in {"places_cache", "solar_cache", "overpass_cache", "vision_cache"}
    with connection() as conn:
        conn.execute(
            f"INSERT OR REPLACE INTO {table} (key, request_json, response_json, created_at) "
            f"VALUES (?, ?, ?, ?)",
            (
                key,
                json.dumps(request, sort_keys=True),
                json.dumps(response),
                int(time.time()),
            ),
        )


def log_cost(
    search_id: str,
    api: str,
    operation: str,
    cost_usd: float,
    latency_ms: int,
    success: bool,
) -> None:
    """Append a single API call to the cost log.

    Cost numbers are best-effort estimates. They're surfaced in the UI so
    the user can see roughly what each search cost; they're not invoices.
    """
    with connection() as conn:
        conn.execute(
            "INSERT INTO cost_log (search_id, api, operation, cost_usd, latency_ms, success, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                search_id,
                api,
                operation,
                float(cost_usd),
                int(latency_ms),
                1 if success else 0,
                int(time.time()),
            ),
        )


def cost_summary(search_id: str) -> dict[str, Any]:
    """Aggregate cost for a single search run, for the UI cost badge."""
    with connection() as conn:
        rows = conn.execute(
            "SELECT api, COUNT(*) AS calls, SUM(cost_usd) AS spend, SUM(latency_ms) AS latency_ms "
            "FROM cost_log WHERE search_id = ? GROUP BY api",
            (search_id,),
        ).fetchall()
    by_api = {
        r["api"]: {
            "calls": r["calls"],
            "spend_usd": round(r["spend"] or 0.0, 4),
            "latency_ms": r["latency_ms"] or 0,
        }
        for r in rows
    }
    total = round(sum(v["spend_usd"] for v in by_api.values()), 4)
    return {"by_api": by_api, "total_usd": total}
