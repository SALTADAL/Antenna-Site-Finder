"""/search router.

Orchestrates the pipeline. Routers stay thin; the actual work is in
services/. This file is the only place that knows about the stage
ordering and the cost-summary shape.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.db import cost_summary
from app.logging_config import get_logger
from app.models import CostBreakdown, SearchRequest, SearchResponse
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
    logger.info("Search %s starting: %s radius=%smi", search_id, icao, req.radius_miles)

    candidates, warnings = await places.search_nearby(
        icao=airport.icao,
        origin_lat=airport.latitude,
        origin_lng=airport.longitude,
        radius_miles=req.radius_miles,
        search_id=search_id,
    )

    # Chain detection
    for c in candidates:
        is_chain, match = chain_detect.detect(c.name)
        c.is_chain = is_chain
        c.chain_match = match
    if not req.include_chains:
        candidates = [c for c in candidates if not c.is_chain]

    # Stage 2/4 stubs (no-ops today, real work later)
    candidates = await solar.enrich_with_solar(candidates, search_id)
    candidates = await overpass.enrich_with_overpass(candidates, search_id)
    # vision is per-candidate, called from inside solar.enrich in Stage 2

    candidates = scorer.score_candidates(candidates)
    candidates = candidates[: settings.max_results]

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
    )
