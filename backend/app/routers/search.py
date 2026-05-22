"""/search router.

Orchestrates the pipeline. Routers stay thin; the actual work is in
services/. This file is the only place that knows about the stage
ordering and the cost-summary shape.
"""

from __future__ import annotations

import asyncio
import time

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db import cost_summary, outreach_get_many
from app.logging_config import get_logger
from app.models import (
    CostBreakdown,
    OutreachCounts,
    OutreachState,
    SearchRequest,
    SearchResponse,
)
from app.services import airports as airports_svc
from app.services import chain_detect, places, scorer
from app.services import overpass, solar, vision  # stubs for now

logger = get_logger(__name__)

router = APIRouter(prefix="/search", tags=["search"])


@router.post("", response_model=SearchResponse)
async def post_search(req: SearchRequest) -> SearchResponse:
    """Run the full pipeline and return ranked candidates.

    Pipeline (Stage 1 active steps shown; Stage 2+ steps are no-ops):
        1. Resolve airport
        2. Nearby search across business types
        3. Dedupe by place_id (handled inside places service)
        4. Chain detection
        5. Solar enrichment (Stage 2)
        6. Vision fallback for unknown roofs (Stage 4)
        7. Overpass building heights (Stage 2)
        8. Score
        9. Note generation (inside scorer)
        10. Cost summary
    """
    settings = get_settings()
    icao = req.icao.strip().upper()
    airport = airports_svc.lookup(icao)
    if airport is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown airport code {icao}. Try the 4-letter ICAO (e.g. KRDU, KCLT).",
        )

    search_id = places.new_search_id()
    t_start = time.time()
    logger.info("[%s] START %s radius=%smi", search_id, icao, req.radius_miles)

    # Step 1: Fast nearby search only. Skip Place Details for now.
    t0 = time.time()
    candidates, warnings = await places.search_nearby_basic(
        icao=airport.icao,
        origin_lat=airport.latitude,
        origin_lng=airport.longitude,
        radius_miles=req.radius_miles,
        search_id=search_id,
    )
    t_nearby = time.time() - t0
    logger.info("[%s] nearby done in %.1fs (%d candidates)", search_id, t_nearby, len(candidates))

    # Step 2: Chain detection on the names we already have. Cheap.
    t0 = time.time()
    for c in candidates:
        is_chain, match = chain_detect.detect(c.name)
        c.is_chain = is_chain
        c.chain_match = match
    before = len(candidates)
    if not req.include_chains:
        candidates = [c for c in candidates if not c.is_chain]
    t_chain = time.time() - t0
    logger.info(
        "[%s] chain detect done in %.2fs (dropped %d, %d remain)",
        search_id, t_chain, before - len(candidates), len(candidates),
    )

    # Step 2b: Outreach state lookup. One SQLite query for all surviving
    # place_ids. Annotate each candidate; filter out non-untouched ones if
    # hide_contacted is set. We do this BEFORE Place Details / Solar so we
    # don't burn API budget re-enriching candidates we already contacted.
    t0 = time.time()
    place_ids = [c.place_id for c in candidates]
    outreach_rows = outreach_get_many(place_ids)
    for c in candidates:
        row = outreach_rows.get(c.place_id)
        if row:
            c.outreach = OutreachState(**row)
    outreach_counts = _build_outreach_counts(candidates, hide_contacted=req.hide_contacted)
    before_hidden = len(candidates)
    if req.hide_contacted:
        candidates = [
            c for c in candidates
            if c.outreach is None or c.outreach.status == "untouched"
        ]
    t_outreach = time.time() - t0
    logger.info(
        "[%s] outreach filter done in %.2fs (hid %d, %d remain)",
        search_id, t_outreach, before_hidden - len(candidates), len(candidates),
    )

    # Step 3: Place Details ONLY for survivors. Saves $0.017 per candidate
    # we don't bother detailing, plus the latency that goes with it.
    t0 = time.time()
    candidates = await places.enrich_with_details(candidates, search_id)
    t_details = time.time() - t0
    logger.info("[%s] details done in %.1fs", search_id, t_details)

    # Step 4: Solar + Overpass run in parallel. They don't depend on each other.
    t0 = time.time()
    await asyncio.gather(
        solar.enrich_with_solar(candidates, search_id, airport_icao=airport.icao),
        overpass.enrich_with_overpass(candidates, search_id, airport_icao=airport.icao),
    )
    t_solar_op = time.time() - t0
    logger.info("[%s] solar+overpass done in %.1fs", search_id, t_solar_op)

    # Step 5: Vision fallback for any roof Solar couldn't see. Parallelized.
    t0 = time.time()
    candidates = await vision.enrich_unknown_roofs(candidates, search_id)
    t_vision = time.time() - t0
    logger.info("[%s] vision done in %.1fs", search_id, t_vision)

    # Step 6: Score and trim.
    t0 = time.time()
    candidates = scorer.score_candidates(candidates)
    candidates = candidates[: settings.max_results]
    t_score = time.time() - t0

    t_total = time.time() - t_start
    logger.info(
        "[%s] DONE total=%.1fs (nearby=%.1f chain=%.2f details=%.1f solar+overpass=%.1f vision=%.1f score=%.2f)",
        search_id, t_total, t_nearby, t_chain, t_details, t_solar_op, t_vision, t_score,
    )

    cost = cost_summary(search_id)
    return SearchResponse(
        search_id=search_id,
        airport=airport,
        radius_miles=req.radius_miles,
        candidate_count=len(candidates),
        candidates=candidates,
        cost=CostBreakdown(**cost),
        pipeline_stage="scored",
        mock_mode=settings.app_mode == "mock",
        warnings=warnings,
        outreach_counts=outreach_counts,
    )


def _build_outreach_counts(candidates, hide_contacted: bool) -> OutreachCounts:
    """Tally how many candidates have each outreach status.

    `total_known` is how many have ANY outreach row at all. `hidden` is
    the count that will be filtered out if hide_contacted is True (any
    status other than 'untouched').
    """
    by_status: dict[str, int] = {}
    hidden = 0
    total_known = 0
    for c in candidates:
        if c.outreach is None:
            continue
        total_known += 1
        status = c.outreach.status
        by_status[status] = by_status.get(status, 0) + 1
        if status != "untouched":
            hidden += 1
    return OutreachCounts(
        total_known=total_known,
        hidden=hidden if hide_contacted else 0,
        by_status=by_status,
    )
