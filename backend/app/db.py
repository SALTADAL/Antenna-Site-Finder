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

-- Outreach state per candidate. One row per Place ID the field-ops user has
-- touched. Candidates with no row are considered "untouched".
CREATE TABLE IF NOT EXISTS outreach_state (
    place_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    last_contact_at INTEGER,
    notes TEXT NOT NULL DEFAULT '',
    contacted_by TEXT NOT NULL DEFAULT '',
    business_name TEXT NOT NULL DEFAULT '',
    airport_icao TEXT NOT NULL DEFAULT '',
    updated_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_outreach_status ON outreach_state (status);
CREATE INDEX IF NOT EXISTS idx_outreach_airport ON outreach_state (airport_icao);
"""

VALID_OUTREACH_STATUSES = {
    "untouched",
    "contacted",
    "followup",
    "interested",
    "declined",
    "won",
    "lost",
}


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


# ---------------------------------------------------------------------------
# Outreach state helpers
# ---------------------------------------------------------------------------


def outreach_get(place_id: str) -> dict[str, Any] | None:
    """Fetch outreach state for one Place ID. None if never touched."""
    with connection() as conn:
        row = conn.execute(
            "SELECT place_id, status, last_contact_at, notes, contacted_by, "
            "business_name, airport_icao, updated_at "
            "FROM outreach_state WHERE place_id = ?",
            (place_id,),
        ).fetchone()
    if not row:
        return None
    return dict(row)


def outreach_get_many(place_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Bulk lookup. Returns place_id -> state dict for any rows that exist.

    Used by /search so we can annotate every candidate in one query
    instead of N queries.
    """
    if not place_ids:
        return {}
    placeholders = ",".join("?" * len(place_ids))
    with connection() as conn:
        rows = conn.execute(
            f"SELECT place_id, status, last_contact_at, notes, contacted_by, "
            f"business_name, airport_icao, updated_at "
            f"FROM outreach_state WHERE place_id IN ({placeholders})",
            place_ids,
        ).fetchall()
    return {r["place_id"]: dict(r) for r in rows}


def outreach_set(
    place_id: str,
    status: str,
    notes: str = "",
    contacted_by: str = "",
    business_name: str = "",
    airport_icao: str = "",
    set_last_contact: bool = True,
) -> dict[str, Any]:
    """Upsert outreach state for one Place ID. Returns the resulting row.

    `set_last_contact` defaults True so saving any status update bumps
    the timestamp. Set False when you're correcting an old entry without
    actually re-contacting the prospect.
    """
    import time as _time
    if status not in VALID_OUTREACH_STATUSES:
        raise ValueError(f"Invalid status {status!r}. Allowed: {sorted(VALID_OUTREACH_STATUSES)}")
    now = int(_time.time())
    last_contact = now if set_last_contact and status != "untouched" else None

    with connection() as conn:
        # Preserve existing last_contact_at if we're not bumping it now.
        existing = conn.execute(
            "SELECT last_contact_at, business_name, airport_icao "
            "FROM outreach_state WHERE place_id = ?",
            (place_id,),
        ).fetchone()
        if existing and last_contact is None:
            last_contact = existing["last_contact_at"]
        if existing:
            business_name = business_name or existing["business_name"]
            airport_icao = airport_icao or existing["airport_icao"]

        conn.execute(
            "INSERT INTO outreach_state "
            "(place_id, status, last_contact_at, notes, contacted_by, "
            " business_name, airport_icao, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(place_id) DO UPDATE SET "
            "  status=excluded.status, "
            "  last_contact_at=excluded.last_contact_at, "
            "  notes=excluded.notes, "
            "  contacted_by=excluded.contacted_by, "
            "  business_name=COALESCE(NULLIF(excluded.business_name, ''), outreach_state.business_name), "
            "  airport_icao=COALESCE(NULLIF(excluded.airport_icao, ''), outreach_state.airport_icao), "
            "  updated_at=excluded.updated_at",
            (
                place_id, status, last_contact, notes, contacted_by,
                business_name, airport_icao, now,
            ),
        )
    return outreach_get(place_id) or {}


def outreach_delete(place_id: str) -> bool:
    """Remove a Place ID's outreach state (effectively reset to untouched)."""
    with connection() as conn:
        cursor = conn.execute("DELETE FROM outreach_state WHERE place_id = ?", (place_id,))
        return cursor.rowcount > 0


def outreach_list(airport_icao: str | None = None) -> list[dict[str, Any]]:
    """Return every outreach row, optionally filtered by airport."""
    with connection() as conn:
        if airport_icao:
            rows = conn.execute(
                "SELECT * FROM outreach_state WHERE airport_icao = ? "
                "ORDER BY updated_at DESC",
                (airport_icao.upper(),),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM outreach_state ORDER BY updated_at DESC"
            ).fetchall()
    return [dict(r) for r in rows]
