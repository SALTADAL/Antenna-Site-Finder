"""Claude vision fallback for roof classification.

When Google Solar API has no coverage at a candidate's address, we fall
back to a vision model. The pipeline is:

    1. Pull a satellite tile from Google Static Maps centered on the
       candidate's lat/lng (zoom 20, 600x600px, maptype=satellite).
    2. Send the tile to Claude (claude-sonnet-4-6 vision) with a tight
       prompt that constrains the answer to {FLAT, PITCHED, MIXED, UNCLEAR}.
    3. Parse the response. Cache by lat/lng + zoom + size hash.

Costs (live mode, approximate):
    Static Maps: ~$0.002 per tile
    Claude vision: ~$0.003 per image
    Total per vision fallback: ~$0.005

In mock mode we read from fixtures/vision/<ICAO>.json keyed by place_id.
The fixture only covers candidates that Solar marked unknown, mirroring
the real call pattern.
"""

from __future__ import annotations

import base64
import json
import time
from pathlib import Path
from typing import Literal

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

VisionVerdict = Literal["FLAT", "PITCHED", "MIXED", "UNCLEAR"]

STATIC_MAPS_URL = "https://maps.googleapis.com/maps/api/staticmap"
ANTHROPIC_MODEL = "claude-sonnet-4-6"

COST_STATIC_MAP = 0.002
COST_VISION = 0.003

PROMPT = (
    "You are reviewing a top-down satellite image of a single commercial "
    "building. Determine whether the main building in the center of the "
    "image has a roof that would suit a small rooftop antenna (about 4ft "
    "square, weighing 30lb).\n\n"
    "Answer with exactly one word:\n"
    "- FLAT if the central building's roof is clearly flat (no visible pitch)\n"
    "- PITCHED if the central building's roof is clearly sloped\n"
    "- MIXED if part of the roof is flat and part is pitched\n"
    "- UNCLEAR if cloud cover, image quality, or framing make it impossible to tell\n\n"
    "Reply with only the single word. No explanation, no punctuation."
)


def _fixture_path(icao: str) -> Path:
    return Path(__file__).resolve().parent.parent / "fixtures" / "vision" / f"{icao.upper()}.json"


def _load_fixture(icao: str) -> dict:
    path = _fixture_path(icao)
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


async def _fetch_static_map(
    client: httpx.AsyncClient, lat: float, lng: float, search_id: str
) -> bytes | None:
    """Pull one satellite tile. Returns PNG bytes or None on failure."""
    settings = get_settings()
    params = {
        "center": f"{lat},{lng}",
        "zoom": 20,
        "size": "600x600",
        "maptype": "satellite",
        "key": settings.google_maps_api_key,
    }
    t0 = time.time()
    ok = False
    img: bytes | None = None
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            retry=retry_if_exception_type((httpx.HTTPError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                resp = await client.get(STATIC_MAPS_URL, params=params, timeout=30.0)
                resp.raise_for_status()
                img = resp.content
                ok = True
    except Exception as e:
        logger.warning("Static Maps fetch failed at %s,%s: %s", lat, lng, e)
    finally:
        log_cost(
            search_id=search_id,
            api="static_maps",
            operation="satellite_tile",
            cost_usd=COST_STATIC_MAP,
            latency_ms=int((time.time() - t0) * 1000),
            success=ok,
        )
    return img


async def _classify_with_claude(image_bytes: bytes, search_id: str) -> VisionVerdict:
    """Send the satellite tile to Claude and parse the one-word verdict."""
    settings = get_settings()
    if not settings.anthropic_api_key:
        logger.warning("ANTHROPIC_API_KEY not set; vision fallback unavailable.")
        return "UNCLEAR"

    # Lazy import so the app boots fine when anthropic isn't installed
    # (it's in requirements.txt but the runtime check is cheap).
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        logger.error("anthropic package missing. Install or set ANTHROPIC_API_KEY=''.")
        return "UNCLEAR"

    encoded = base64.standard_b64encode(image_bytes).decode("ascii")
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    t0 = time.time()
    ok = False
    verdict: VisionVerdict = "UNCLEAR"
    try:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(3),
            wait=wait_exponential(multiplier=1, min=1, max=8),
            reraise=True,
        ):
            with attempt:
                resp = await client.messages.create(
                    model=ANTHROPIC_MODEL,
                    max_tokens=8,
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": "image/png",
                                        "data": encoded,
                                    },
                                },
                                {"type": "text", "text": PROMPT},
                            ],
                        }
                    ],
                )
                # Claude returns a list of content blocks. We only sent text+image.
                text = (resp.content[0].text or "").strip().upper()
                if "FLAT" in text:
                    verdict = "FLAT"
                elif "PITCHED" in text:
                    verdict = "PITCHED"
                elif "MIXED" in text:
                    verdict = "MIXED"
                else:
                    verdict = "UNCLEAR"
                ok = True
    except Exception as e:
        logger.warning("Claude vision call failed: %s", e)
    finally:
        log_cost(
            search_id=search_id,
            api="claude_vision",
            operation="classify_roof",
            cost_usd=COST_VISION,
            latency_ms=int((time.time() - t0) * 1000),
            success=ok,
        )
    return verdict


async def classify_roof(candidate: Candidate, search_id: str) -> VisionVerdict:
    """Classify one candidate's roof. Honors mock mode."""
    settings = get_settings()
    if settings.app_mode == "mock":
        # Inferred from the candidate's place_id prefix in the mock fixtures.
        # In mock we only return verdicts the fixture provides; everything
        # else stays UNCLEAR.
        icao_guess = candidate.place_id.split("_")[1].upper() if "_" in candidate.place_id else ""
        fixture = _load_fixture(icao_guess)
        entry = fixture.get(candidate.place_id)
        if entry:
            return entry.get("verdict", "UNCLEAR")
        return "UNCLEAR"

    if not settings.google_maps_api_key:
        return "UNCLEAR"

    # Cache check first so repeat searches at the same address don't pay twice.
    cache_payload = {
        "src": "vision",
        "lat": round(candidate.latitude, 5),
        "lng": round(candidate.longitude, 5),
        "zoom": 20,
        "size": "600x600",
        "model": ANTHROPIC_MODEL,
    }
    key = cache_key(cache_payload)
    cached = cache_get("vision_cache", key)
    if cached is not None:
        return cached.get("verdict", "UNCLEAR")

    async with httpx.AsyncClient() as client:
        img = await _fetch_static_map(client, candidate.latitude, candidate.longitude, search_id)
    if not img:
        return "UNCLEAR"

    verdict = await _classify_with_claude(img, search_id)
    cache_put("vision_cache", key, cache_payload, {"verdict": verdict})
    return verdict


async def enrich_unknown_roofs(
    candidates: list[Candidate], search_id: str
) -> list[Candidate]:
    """Run vision classification on candidates whose Solar verdict was unknown.

    Parallelized. The old code awaited each call in a for-loop, which meant
    eight unknown candidates × four seconds each was thirty seconds of pure
    wall-clock. Now they run concurrently with a small semaphore so we don't
    burst Anthropic.
    """
    import asyncio

    targets = [c for c in candidates if c.roof_type == "unknown"]
    if not targets:
        return candidates

    logger.info("Vision fallback running for %d unknown-roof candidates.", len(targets))

    sem = asyncio.Semaphore(6)

    async def one(c: Candidate) -> None:
        async with sem:
            verdict = await classify_roof(c, search_id)
        if verdict == "UNCLEAR":
            return
        c.roof_type = verdict.lower()  # type: ignore[assignment]
        c.roof_source = "vision"

    await asyncio.gather(*(one(c) for c in targets), return_exceptions=True)
    return candidates
