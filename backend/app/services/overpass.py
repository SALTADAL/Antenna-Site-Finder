"""OpenStreetMap Overpass API wrapper.

Overpass is free and key-free, but rate-limited (~10000 queries/day from
the public endpoints). We query for buildings near each candidate's
lat/lng and extract `height` or `building:levels` tags.

A meaningful fraction of small commercial buildings in the US have no
height tagging in OSM. Those candidates get height=None and the scorer
treats height as "unknown" rather than penalizing them.

In mock mode we read from app/fixtures/overpass/<ICAO>.json keyed by
place_id.
"""

from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.config import get_settings
from app.db import cache_get, cache_key, cache_put, log_cost
from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)

# We rotate between two public endpoints to spread load.
OVERPASS_ENDPOINTS = (
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
)

# Free API, but we still log a notional cost of 0 for accounting.
COST_PER_CALL = 0.0


def _fixture_path(icao: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "overpass" / f"{icao.upper()}.json"


def _load_fixture(icao: str) -> dict[str, Any]:
    path = _fixture_path(icao)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _round_coord(lat: float, lng: float) -> tuple[float, float]:
    """Round to 4 decimals (~11m precision) for cache key stability."""
    return round(lat, 4), round(lng, 4)


def _query(lat: float, lng: float) -> str:
    """Overpass QL: buildings within ~30m of the point."""
    return f"""
        [out:json][timeout:25];
        (
          way["building"](around:30,{lat},{lng});
          relation["building"](around:30,{lat},{lng});
        );
        out tags;
    """


def _extract(elements: list[dict[str, Any]]) -> dict[str, Any]:
    """Pick the tallest tagged element. Buildings overlap occasionally."""
    best_height: float | None = None
    best_levels: int | None = None
    for el in elements:
        tags = el.get("tags") or {}
        h = tags.get("height") or tags.get("building:height")
        lvl = tags.get("building:levels")
        try:
            if h is not None:
                h_val = float(str(h).replace("m", "").strip())
                if best_height is None or h_val > best_height:
                    best_height = h_val
        except (ValueError, TypeError):
            pass
        try:
            if lvl is not None:
                lvl_val = int(float(str(lvl).strip()))
                if best_levels is None or lvl_val > best_levels:
                    best_levels = lvl_val
        except (ValueError, TypeError):
            pass

    # If we have levels but no height, estimate 3m per level.
    if best_height is None and best_levels is not None:
        best_height = float(best_levels) * 3.0

    return {"height_m": best_height, "levels": best_levels}


async def _fetch_live(
    client: httpx.AsyncClient, lat: float, lng: float, search_id: str
) -> dict[str, Any]:
    """One Overpass round trip. Returns {height_m, levels}."""
    rlat, rlng = _round_coord(lat, lng)
    cache_payload = {"src": "overpass", "lat": rlat, "lng": rlng, "radius_m": 30}
    key = cache_key(cache_payload)
    cached = cache_get("overpass_cache", key)
    if cached is not None:
        return cached

    body = _query(rlat, rlng)
    last_err: Exception | None = None
    parsed: dict[str, Any] = {"height_m": None, "levels": None}
    # Tight per-call timeout. Overpass is volunteer infrastructure; a slow
    # response now is almost certainly going to stay slow. Better to give
    # up and mark height unknown than block the search.
    for url in OVERPASS_ENDPOINTS:
        t0 = time.time()
        ok = False
        try:
            resp = await client.post(url, content=body, timeout=6.0)
            resp.raise_for_status()
            data = resp.json()
            parsed = _extract(data.get("elements", []))
            ok = True
        except Exception as e:
            last_err = e
            logger.debug("Overpass attempt failed at %s: %s", url, e)
        finally:
            log_cost(
                search_id=search_id,
                api="overpass",
                operation="buildings_near",
                cost_usd=COST_PER_CALL,
                latency_ms=int((time.time() - t0) * 1000),
                success=ok,
            )
        if ok:
            cache_put("overpass_cache", key, cache_payload, parsed)
            return parsed

    if last_err is not None:
        logger.warning("Overpass exhausted endpoints at %s,%s: %s", rlat, rlng, last_err)
    return parsed


async def enrich_with_overpass(
    candidates: list[Candidate], search_id: str, airport_icao: str | None = None
) -> list[Candidate]:
    """Set building_height_m on each candidate (None where unknown).

    Wrapped in a hard 15-second budget. Overpass is free public infrastructure
    with no SLA; we'd rather have most candidates show "unknown" height than
    have one slow Overpass call hold up the entire search.
    """
    settings = get_settings()

    if settings.app_mode == "mock":
        fixture = _load_fixture(airport_icao or "")
        for c in candidates:
            entry = fixture.get(c.place_id) or {}
            c.building_height_m = entry.get("height_m")
        return candidates

    if not candidates:
        return candidates

    # Bumped from 3 to 6. Per-call timeout is now 6s, so even max-out
    # bursts are bounded. Overpass can handle this load fine.
    sem = asyncio.Semaphore(6)

    async with httpx.AsyncClient() as client:
        async def one(c: Candidate) -> None:
            async with sem:
                parsed = await _fetch_live(client, c.latitude, c.longitude, search_id)
                c.building_height_m = parsed.get("height_m")

        try:
            await asyncio.wait_for(
                asyncio.gather(*(one(c) for c in candidates), return_exceptions=True),
                timeout=15.0,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "Overpass stage exceeded 15s budget; %d/%d candidates may have no height data.",
                sum(1 for c in candidates if c.building_height_m is None),
                len(candidates),
            )
    return candidates
