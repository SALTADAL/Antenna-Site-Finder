"""/preflight router.

Lets the user verify their API keys work before burning budget on a real
search. We make one cheap Place Details call (Basic Data tier, ~$0) and
one trivial Anthropic message (a few tokens).

The frontend shows the preflight result before enabling the "Search"
button when APP_MODE=live.
"""

from __future__ import annotations

import time

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from app.config import get_settings
from app.db import log_cost
from app.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/preflight", tags=["preflight"])


class PreflightCheck(BaseModel):
    ok: bool
    label: str
    detail: str = ""
    cost_usd: float = 0.0
    latency_ms: int = 0


class PreflightResponse(BaseModel):
    mode: str
    overall_ok: bool
    checks: list[PreflightCheck]
    total_cost_usd: float = 0.0


# A stable Place ID we can ping for the cheapest possible Place Details
# call. Google's docs use Sydney HQ as the canonical example, which never
# returns 404 and has a static name.
SANITY_PLACE_ID = "ChIJN1t_tDeuEmsRUsoyG83frY4"


@router.get("", response_model=PreflightResponse)
async def get_preflight() -> PreflightResponse:
    """Sanity check the API keys. Cheap.

    Returns ok=True when both keys (or the relevant key for the current
    mode) are present and working. The frontend uses this to gate the
    first live-mode search behind a one-click validation.
    """
    settings = get_settings()
    checks: list[PreflightCheck] = []

    # Mock mode is a no-op preflight.
    if settings.app_mode == "mock":
        checks.append(PreflightCheck(
            ok=True,
            label="Mock mode",
            detail="Running against local fixtures. No external API calls.",
        ))
        return PreflightResponse(
            mode=settings.app_mode,
            overall_ok=True,
            checks=checks,
            total_cost_usd=0.0,
        )

    # Live mode: validate Google Maps key with one Place Details call.
    google_check = await _check_google_maps(settings.google_maps_api_key)
    checks.append(google_check)

    # Validate Anthropic key with a tiny token request.
    anthropic_check = await _check_anthropic(settings.anthropic_api_key)
    checks.append(anthropic_check)

    overall = all(c.ok for c in checks)
    total = round(sum(c.cost_usd for c in checks), 4)
    return PreflightResponse(
        mode=settings.app_mode,
        overall_ok=overall,
        checks=checks,
        total_cost_usd=total,
    )


async def _check_google_maps(key: str) -> PreflightCheck:
    if not key:
        return PreflightCheck(
            ok=False,
            label="Google Maps API",
            detail="GOOGLE_MAPS_API_KEY is empty. Set it in .env.",
        )
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {"place_id": SANITY_PLACE_ID, "fields": "name", "key": key}

    t0 = time.time()
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params=params, timeout=15.0)
        latency = int((time.time() - t0) * 1000)
        if resp.status_code != 200:
            return PreflightCheck(
                ok=False,
                label="Google Maps API",
                detail=f"HTTP {resp.status_code}. Check the key, billing, and API enablement.",
                latency_ms=latency,
                cost_usd=0.0,
            )
        data = resp.json()
        status = data.get("status", "UNKNOWN")
        if status != "OK":
            return PreflightCheck(
                ok=False,
                label="Google Maps API",
                detail=f"Places returned status={status}. {data.get('error_message', '')}".strip(),
                latency_ms=latency,
                cost_usd=0.005,
            )
        log_cost(
            search_id="preflight",
            api="places",
            operation="preflight",
            cost_usd=0.005,
            latency_ms=latency,
            success=True,
        )
        return PreflightCheck(
            ok=True,
            label="Google Maps API",
            detail="Place Details call succeeded. Key, billing, and Places API look good.",
            cost_usd=0.005,
            latency_ms=latency,
        )
    except Exception as e:
        return PreflightCheck(
            ok=False,
            label="Google Maps API",
            detail=f"Request failed: {e}",
        )


async def _check_anthropic(key: str) -> PreflightCheck:
    if not key:
        return PreflightCheck(
            ok=False,
            label="Anthropic API",
            detail="ANTHROPIC_API_KEY is empty. The vision fallback will be unavailable; live searches still work for candidates with Solar coverage.",
        )
    try:
        from anthropic import AsyncAnthropic
    except ImportError:
        return PreflightCheck(
            ok=False,
            label="Anthropic API",
            detail="anthropic package not installed.",
        )

    t0 = time.time()
    try:
        client = AsyncAnthropic(api_key=key)
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4,
            messages=[{"role": "user", "content": "ok"}],
        )
        latency = int((time.time() - t0) * 1000)
        _ = resp.content[0].text  # smoke read
        log_cost(
            search_id="preflight",
            api="anthropic",
            operation="preflight",
            cost_usd=0.0001,
            latency_ms=latency,
            success=True,
        )
        return PreflightCheck(
            ok=True,
            label="Anthropic API",
            detail="Haiku ping succeeded. Vision fallback ready.",
            cost_usd=0.0001,
            latency_ms=latency,
        )
    except Exception as e:
        return PreflightCheck(
            ok=False,
            label="Anthropic API",
            detail=f"Request failed: {e}",
        )
