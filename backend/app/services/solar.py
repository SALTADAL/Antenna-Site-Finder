"""Google Solar API wrapper.

The Solar API exposes `buildingInsights:findClosest`, which returns the
roof geometry of the building closest to a given lat/lng. The interesting
parts for our use case are `solarPotential.roofSegmentStats[]`, each of
which has a pitch angle, azimuth, and area in square meters.

Our rubric considers a segment "flat" when pitch < 5 degrees. We sum the
area of those segments per candidate and report:
    - roof_area_sqft         total roof area (all segments)
    - flat_segments_area_sqft area of low-pitch segments
    - dominant_pitch_deg     pitch of the largest segment
    - verdict                "flat" | "pitched" | "mixed" | "unknown"

Cost: roughly $0.10 per buildingInsights call. We cache aggressively by
address hash because the same building hits the cache repeatedly across
multiple searches at the same airport.

In mock mode we read from app/fixtures/solar/<ICAO>.json which is keyed
by place_id. That file is built to mirror the shape this function would
return after parsing the real API.

When Solar returns no coverage (the building isn't in their dataset), we
mark roof_type=unknown and leave roof_source=none. Stage 4's vision
fallback covers this case.
"""

from __future__ import annotations

import json
import math
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

SOLAR_URL = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
COST_PER_CALL = 0.10  # Conservative estimate; real cost depends on SKU.

FLAT_PITCH_THRESHOLD_DEG = 5.0
SQM_TO_SQFT = 10.7639


def _fixture_path(icao: str) -> Path:
    """Resolve the mock fixture path for one airport."""
    return Path(__file__).resolve().parent.parent / "fixtures" / "solar" / f"{icao.upper()}.json"


def _load_fixture(icao: str) -> dict[str, Any]:
    """Return the per-place_id mock data, or {} if no fixture exists."""
    path = _fixture_path(icao)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _verdict_from_segments(
    total_sqft: float, flat_sqft: float, dominant_pitch: float
) -> str:
    """Translate segment stats into one of {flat, pitched, mixed, unknown}.

    Heuristic:
        - flat:     dominant pitch is below threshold AND most area is flat
        - pitched:  dominant pitch is well above threshold
        - mixed:    some flat area but also significant pitch
        - unknown:  no usable data
    """
    if total_sqft <= 0:
        return "unknown"
    flat_ratio = flat_sqft / total_sqft if total_sqft else 0.0
    if dominant_pitch < FLAT_PITCH_THRESHOLD_DEG and flat_ratio > 0.85:
        return "flat"
    if dominant_pitch >= 12.0 and flat_ratio < 0.15:
        return "pitched"
    return "mixed"


def _parse_live_response(payload: dict[str, Any]) -> dict[str, Any] | None:
    """Reduce Solar's findClosest payload to our four-field summary."""
    if not payload:
        return None
    sp = (payload.get("solarPotential") or {})
    segments = sp.get("roofSegmentStats") or []
    if not segments:
        return None

    total_sqm = 0.0
    flat_sqm = 0.0
    largest_area = 0.0
    dominant_pitch = 0.0
    for seg in segments:
        pitch = float(seg.get("pitchDegrees", 0.0))
        area = float((seg.get("stats") or {}).get("areaMeters2", 0.0))
        total_sqm += area
        if pitch < FLAT_PITCH_THRESHOLD_DEG:
            flat_sqm += area
        if area > largest_area:
            largest_area = area
            dominant_pitch = pitch

    total_sqft = round(total_sqm * SQM_TO_SQFT)
    flat_sqft = round(flat_sqm * SQM_TO_SQFT)
    return {
        "roof_area_sqft": total_sqft,
        "dominant_pitch_deg": round(dominant_pitch, 1),
        "flat_segments_area_sqft": flat_sqft,
        "verdict": _verdict_from_segments(total_sqft, flat_sqft, dominant_pitch),
    }


async def _fetch_live(
    client: httpx.AsyncClient, lat: float, lng: float, search_id: str
) -> dict[str, Any] | None:
    """Call Solar API for a single point. Returns parsed summary or None."""
    settings = get_settings()
    params = {
        "location.latitude": lat,
        "location.longitude": lng,
        "requiredQuality": "HIGH",
        "key": settings.google_maps_api_key,
    }
    cache_payload = {"url": SOLAR_URL, "params": {**params, "key": "REDACTED"}}
    key = cache_key(cache_payload)
    cached = cache_get("solar_cache", key)
    if cached is not None:
        # Re-derive the summary from the cached raw response so a rubric
        # change re-derives without re-hitting the API.
        return _parse_live_response(cached)

    t0 = time.time()
    ok = False
    data: dict[str, Any] = {}
    try:
        # Tighter retry budget than the other services. Solar tends to either
        # respond fast or 404 fast; a slow Solar call is usually a stuck call
        # and retrying it 3 times with backoff just compounds the wait.
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(2),
            wait=wait_exponential(multiplier=1, min=1, max=4),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                resp = await client.get(SOLAR_URL, params=params, timeout=12.0)
                # 404 = no coverage at this location. Not an error, just no data.
                if resp.status_code == 404:
                    ok = True
                    data = {}
                    break
                resp.raise_for_status()
                data = resp.json()
                ok = True
    except Exception as e:
        logger.warning("Solar API call failed at %s,%s: %s", lat, lng, e)
        data = {}
    finally:
        log_cost(
            search_id=search_id,
            api="solar",
            operation="findClosest",
            cost_usd=COST_PER_CALL,
            latency_ms=int((time.time() - t0) * 1000),
            success=ok,
        )

    if data:
        cache_put("solar_cache", key, cache_payload, data)
    return _parse_live_response(data)


async def enrich_with_solar(
    candidates: list[Candidate], search_id: str, airport_icao: str | None = None
) -> list[Candidate]:
    """Populate roof_type, roof_area_sqft, roof_source for each candidate.

    In mock mode, reads from fixtures/solar/<icao>.json. In live mode,
    fans out concurrent Solar API calls with a small semaphore.

    Candidates whose Solar response is missing or returns no segments are
    left with roof_type=unknown, roof_source=none. The vision fallback
    in Stage 4 will pick them up.
    """
    settings = get_settings()

    if settings.app_mode == "mock":
        fixture = _load_fixture(airport_icao or "")
        for c in candidates:
            summary = fixture.get(c.place_id)
            if not summary:
                continue
            _apply_summary(c, summary, "solar")
        return candidates

    if not settings.google_maps_api_key:
        logger.warning("Solar live mode requested but GOOGLE_MAPS_API_KEY is empty.")
        return candidates

    import asyncio
    # Bumped from 6 to 14. Solar's a Google service; it handles this fine,
    # and per-search Solar dominates wall-clock when sequential.
    sem = asyncio.Semaphore(14)

    # Single shared client so we get connection pooling across the fan-out.
    async with httpx.AsyncClient() as client:
        async def one(c: Candidate) -> None:
            async with sem:
                summary = await _fetch_live(client, c.latitude, c.longitude, search_id)
                if summary:
                    _apply_summary(c, summary, "solar")

        await asyncio.gather(*(one(c) for c in candidates), return_exceptions=True)
    return candidates


def _apply_summary(c: Candidate, summary: dict[str, Any], source: str) -> None:
    """Write a Solar summary onto a candidate."""
    total = summary.get("roof_area_sqft")
    if total is not None:
        c.roof_area_sqft = float(total)
    verdict = summary.get("verdict", "unknown")
    # Map our four-state verdict to the Candidate.roof_type literal.
    if verdict in {"flat", "mixed", "pitched", "unknown"}:
        c.roof_type = verdict  # type: ignore[assignment]
    if c.roof_type != "unknown":
        c.roof_source = source  # type: ignore[assignment]


def haversine_check(a: tuple[float, float], b: tuple[float, float]) -> float:
    """Utility for tests. Standard great-circle in miles."""
    r = 3958.8
    p1, p2 = math.radians(a[0]), math.radians(b[0])
    dphi = math.radians(b[0] - a[0])
    dlmb = math.radians(b[1] - a[1])
    h = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(h), math.sqrt(1 - h))
