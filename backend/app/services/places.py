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
SEARCH_TYPES = (
    "store",
    "hardware_store",
    "furniture_store",
    "home_goods_store",
    "car_repair",
    "car_dealer",
    "storage",
    "gas_station",
    "restaurant",
    "bakery",
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

    for page in range(3):
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
        await asyncio.sleep(2.0)
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


async def search_nearby(
    icao: str,
    origin_lat: float,
    origin_lng: float,
    radius_miles: float,
    search_id: str,
) -> tuple[list[Candidate], list[str]]:
    """Top-level entry. Returns (candidates, warnings).

    Strategy:
        1. For each search type, run a paginated nearby search.
        2. Dedupe by place_id.
        3. For each unique place, fetch Place Details for phone + address.
        4. Convert to Candidate, computing distance from the airport.
    """
    settings = get_settings()
    warnings: list[str] = []

    if settings.app_mode == "mock":
        warnings.append("Running in mock mode. Results are from local fixtures, not Google Places.")
        raw_places = _load_mock_fixture(icao)
        if not raw_places:
            warnings.append(f"No mock fixture found for {icao}. Add backend/app/fixtures/places/{icao}.json.")
        candidates = [_to_candidate(p, origin_lat, origin_lng) for p in raw_places]
        # Filter to radius in mock mode too, so the spec behaves identically.
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
        # Run nearby searches concurrently across types.
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

        # Place details, also concurrent but with a small semaphore so we
        # don't hammer the API.
        sem = asyncio.Semaphore(8)

        async def details_with_limit(pid: str) -> tuple[str, dict[str, Any]]:
            async with sem:
                resp = await _fetch_details_live(client, pid, search_id)
                return pid, resp.get("result", {})

        details_tasks = [details_with_limit(pid) for pid in all_raw.keys()]
        details_results = await asyncio.gather(*details_tasks, return_exceptions=True)

        for item in details_results:
            if isinstance(item, Exception):
                warnings.append(f"Place details exception: {item}")
                continue
            pid, detail = item
            # Merge details on top of the nearby record.
            merged = {**all_raw[pid], **(detail or {})}
            all_raw[pid] = merged

    candidates = [_to_candidate(r, origin_lat, origin_lng) for r in all_raw.values()]
    candidates = [c for c in candidates if c.distance_miles <= radius_miles]
    return candidates, warnings


def new_search_id() -> str:
    """Generate a unique id for this search run, used to tag cost-log rows."""
    return uuid.uuid4().hex[:12]
