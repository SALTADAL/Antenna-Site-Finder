"""Google Places API wrapper with a mock-mode fallback.

Two execution paths:
    LIVE  -> calls Google Places (Nearby Search + Place Details), caches
              every response in SQLite, logs cost and latency.
    MOCK  -> reads fixtures from app/fixtures/places/<icao>.json. Lets us
              develop and test the full pipeline before paying for any API.

The mock fixtures are real-shaped Place objects derived from manually
curated examples around KRDU. Add new airports by dropping a file in the
fixtures directory.

Cost estimate: Nearby Search is roughly $0.032/request, Place Details
roughly $0.017/request. We log estimates per call so the UI can show
"this search cost about $X."
"""

from __future__ import annotations

import asyncio
import json
import math
import time
import uuid
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

NEARBY_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

# Business types we search. Tuned for "small business with a probable flat
# roof": light retail, light industrial, auto services, food service in
# strip-mall buildings.
#
# Reduced from 11 to 6 types in the perf pass. "store" subsumes
# hardware/furniture/home_goods in practice. Restaurant + bakery + gym
# share enough overlap with each other that one is enough. Removed
# car_dealer because dealerships are essentially never independents.
SEARCH_TYPES = (
    "store",
    "car_repair",
    "storage",
    "gas_station",
    "restaurant",
    "gym",
)

# Conservative cost-per-call estimates. Real billing depends on the
# specific SKU and any free-tier credits.
COST_NEARBY = 0.032
COST_DETAILS = 0.017


def _haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in miles. Standard formula."""
    r_miles = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r_miles * c


def _fixtures_dir() -> Path:
    """Where mock data lives. App dir / fixtures / places /."""
    return Path(__file__).resolve().parent.parent / "fixtures" / "places"


async def _fetch_nearby_live(
    client: httpx.AsyncClient,
    lat: float,
    lng: float,
    radius_m: int,
    place_type: str,
    search_id: str,
) -> list[dict[str, Any]]:
    """Paginated Nearby Search for one type. Returns raw Place results.

    Google's nearby search caps radius at 50km and paginates with a
    `next_page_token`. We honor up to 3 pages (60 results per type).
    """
    settings = get_settings()
    all_results: list[dict[str, Any]] = []
    params: dict[str, Any] = {
        "location": f"{lat},{lng}",
        "radius": radius_m,
        "type": place_type,
        "key": settings.google_maps_api_key,
    }

    # Reduced from 3 pages to 1. The second and third page typically add
    # diminishing-returns matches (further from the airport, often duplicates
    # across types after dedup) for ~5 seconds of extra wall-clock per type.
    # Restore by bumping to 2 or 3 if you find searches missing real candidates.
    for page in range(1):
        cache_payload = {"url": NEARBY_URL, "params": {**params, "key": "REDACTED"}}
        key = cache_key(cache_payload)
        cached = cache_get("places_cache", key)
        if cached is not None:
            results = cached.get("results", [])
            all_results.extend(results)
            next_token = cached.get("next_page_token")
            if not next_token:
                break
            params = {"pagetoken": next_token, "key": settings.google_maps_api_key}
            continue

        t0 = time.time()
        ok = False
        try:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(3),
                wait=wait_exponential(multiplier=1, min=1, max=8),
                retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
                reraise=True,
            ):
                with attempt:
                    resp = await client.get(NEARBY_URL, params=params, timeout=30.0)
                    resp.raise_for_status()
                    data = resp.json()
            ok = True
        except Exception as e:
            logger.error("Nearby search failed type=%s page=%d: %s", place_type, page, e)
            break
        finally:
            log_cost(
                search_id=search_id,
                api="places",
                operation=f"nearby:{place_type}",
                cost_usd=COST_NEARBY,
                latency_ms=int((time.time() - t0) * 1000),
                success=ok,
            )

        cache_put("places_cache", key, cache_payload, data)
        results = data.get("results", [])
        all_results.extend(results)

        next_token = data.get("next_page_token")
        if not next_token:
            break
        # Google requires a brief wait before the page token activates.
        # 500ms is enough in practice; the docs say "a brief delay".
        await asyncio.sleep(0.5)
        params = {"pagetoken": next_token, "key": settings.google_maps_api_key}

    return all_results


async def _fetch_details_live(
    client: httpx.AsyncClient, place_id: str, search_id: str
) -> dict[str, Any]:
    """Place Details lookup for phone, address components, business_status."""
    settings = get_settings()
    fields = (
        "place_id,name,formatted_address,formatted_phone_number,"
        "international_phone_number,address_components,business_status,"
        "rating,user_ratings_total,geometry,types,url"
    )
    params = {"place_id": place_id, "fields": fields, "key": settings.google_maps_api_key}
    cache_payload = {"url": DETAILS_URL, "params": {**params, "key": "REDACTED"}}
    key = cache_key(cache_payload)
    cached = cache_get("places_cache", key)
    if cached is not None:
        return cached

    t0 = time.time()
    ok = False
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                resp = await client.get(DETAILS_URL, params=params, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
        ok = True
    except Exception as e:
        logger.error("Place details failed place_id=%s: %s", place_id, e)
        data = {"result": {}}
    finally:
        log_cost(
            search_id=search_id,
            api="places",
            operation="details",
            cost_usd=COST_DETAILS,
            latency_ms=int((time.time() - t0) * 1000),
            success=ok,
        )

    cache_put("places_cache", key, cache_payload, data)
    return data


def _load_mock_fixture(icao: str) -> list[dict[str, Any]]:
    """Read fixtures/places/<icao>.json. Returns [] if not present."""
    path = _fixtures_dir() / f"{icao.upper()}.json"
    if not path.exists():
        logger.warning("No mock fixture for %s at %s", icao, path)
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _components_to_address(components: list[dict[str, Any]]) -> tuple[str, str, str]:
    """Pick city, state, zip out of Places address_components."""
    city, state, zip_code = "", "", ""
    for comp in components or []:
        types = comp.get("types", [])
        if "locality" in types:
            city = comp.get("long_name", "")
        elif "administrative_area_level_1" in types and not state:
            state = comp.get("short_name", "")
        elif "postal_code" in types:
            zip_code = comp.get("long_name", "")
    return city, state, zip_code


def _to_candidate(raw: dict[str, Any], origin_lat: float, origin_lng: float) -> Candidate:
    """Translate a Place result (nearby + details merged) into a Candidate."""
    geom = raw.get("geometry", {}).get("location", {})
    lat = float(geom.get("lat", 0.0))
    lng = float(geom.get("lng", 0.0))
    city, state, zip_code = _components_to_address(raw.get("address_components", []))

    phone = raw.get("formatted_phone_number") or raw.get("international_phone_number") or ""
    place_id = raw.get("place_id", "")
    maps_url = raw.get("url") or (
        f"https://www.google.com/maps/place/?q=place_id:{place_id}" if place_id else ""
    )

    return Candidate(
        place_id=place_id,
        name=raw.get("name", ""),
        address=raw.get("formatted_address", ""),
        city=city,
        state=state,
        zip=zip_code,
        phone=phone,
        latitude=lat,
        longitude=lng,
        distance_miles=round(_haversine_miles(origin_lat, origin_lng, lat, lng), 2),
        rating=raw.get("rating"),
        user_ratings_total=raw.get("user_ratings_total"),
        business_status=raw.get("business_status"),
        google_maps_url=maps_url,
    )


async def search_nearby_basic(
    icao: str,
    origin_lat: float,
    origin_lng: float,
    radius_miles: float,
    search_id: str,
) -> tuple[list[Candidate], list[str]]:
    """Fast first pass: nearby search only, no Place Details.

    Returns lightweight Candidate objects with name, place_id, lat/lng,
    distance, and basic Places metadata. Address, phone, and address
    components are filled in by enrich_with_details() AFTER the caller
    has filtered chains and out-of-radius results. This split is the
    biggest performance win: we don't pay $0.017 per Place Details call
    on candidates we're about to throw away.
    """
    settings = get_settings()
    warnings: list[str] = []

    # Mock paths: still call the full _to_candidate translator because the
    # fixture already has merged nearby+details shape.
    if settings.app_mode == "mock":
        warnings.append("Running in mock mode. Results are from local fixtures, not Google Places.")
        raw_places = _load_mock_fixture(icao)
        if not raw_places:
            warnings.append(f"No mock fixture found for {icao}. Add backend/app/fixtures/places/{icao}.json.")
        candidates = [_to_candidate(p, origin_lat, origin_lng) for p in raw_places]
        candidates = [c for c in candidates if c.distance_miles <= radius_miles]
        return candidates, warnings

    if not settings.google_maps_api_key:
        warnings.append("GOOGLE_MAPS_API_KEY is empty. Falling back to mock fixtures.")
        raw_places = _load_mock_fixture(icao)
        candidates = [_to_candidate(p, origin_lat, origin_lng) for p in raw_places]
        candidates = [c for c in candidates if c.distance_miles <= radius_miles]
        return candidates, warnings

    radius_m = int(radius_miles * 1609.344)
    all_raw: dict[str, dict[str, Any]] = {}

    async with httpx.AsyncClient() as client:
        nearby_tasks = [
            _fetch_nearby_live(client, origin_lat, origin_lng, radius_m, t, search_id)
            for t in SEARCH_TYPES
        ]
        nearby_results = await asyncio.gather(*nearby_tasks, return_exceptions=True)
        for t, results in zip(SEARCH_TYPES, nearby_results):
            if isinstance(results, Exception):
                warnings.append(f"Nearby search failed for type={t}: {results}")
                continue
            for r in results:
                pid = r.get("place_id")
                if pid and pid not in all_raw:
                    all_raw[pid] = r

    candidates = [_to_candidate(r, origin_lat, origin_lng) for r in all_raw.values()]
    candidates = [c for c in candidates if c.distance_miles <= radius_miles]
    return candidates, warnings


async def enrich_with_details(
    candidates: list[Candidate], search_id: str
) -> list[Candidate]:
    """Fill in phone, formatted_address, address_components for each candidate.

    Call this AFTER chain detection and radius filtering so you only pay
    for Place Details on candidates that survive those filters. Mock mode
    is a no-op because fixtures already include the full detail shape.
    """
    settings = get_settings()
    if settings.app_mode == "mock" or not candidates:
        return candidates

    if not settings.google_maps_api_key:
        return candidates

    # Bumped 12 -> 20. Google's Place Details endpoint handles this fine
    # and the calls are short-lived (50-300ms each).
    sem = asyncio.Semaphore(20)
    by_place_id = {c.place_id: c for c in candidates}

    async with httpx.AsyncClient() as client:
        async def one(pid: str) -> None:
            async with sem:
                resp = await _fetch_details_live(client, pid, search_id)
            detail = (resp or {}).get("result", {}) or {}
            cand = by_place_id.get(pid)
            if not cand or not detail:
                return
            # Patch missing/improved fields on the candidate.
            phone = detail.get("formatted_phone_number") or detail.get("international_phone_number")
            if phone and not cand.phone:
                cand.phone = phone
            addr = detail.get("formatted_address")
            if addr:
                cand.address = addr
            comps = detail.get("address_components")
            if comps:
                city, state, zip_code = _components_to_address(comps)
                cand.city = cand.city or city
                cand.state = cand.state or state
                cand.zip = cand.zip or zip_code
            status = detail.get("business_status")
            if status and not cand.business_status:
                cand.business_status = status
            url = detail.get("url")
            if url and not cand.google_maps_url:
                cand.google_maps_url = url

        await asyncio.gather(*(one(pid) for pid in by_place_id.keys()), return_exceptions=True)

    return candidates


# Backward-compatible alias for existing callers / tests.
async def search_nearby(
    icao: str,
    origin_lat: float,
    origin_lng: float,
    radius_miles: float,
    search_id: str,
) -> tuple[list[Candidate], list[str]]:
    """Legacy entry: runs nearby + details together. Kept for the mock-mode
    smoke test which doesn't do the chain-filter-then-details dance.
    Prefer search_nearby_basic + enrich_with_details in new code.
    """
    candidates, warnings = await search_nearby_basic(
        icao, origin_lat, origin_lng, radius_miles, search_id
    )
    candidates = await enrich_with_details(candidates, search_id)
    return candidates, warnings


def new_search_id() -> str:
    """Generate a unique id for this search run, used to tag cost-log rows."""
    return uuid.uuid4().hex[:12]
