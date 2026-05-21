"""Google Solar API wrapper. STAGE 2 IMPLEMENTATION.

Placeholder for the Stage 1 checkpoint. The real implementation will:
    - Call buildingInsights:findClosest at a candidate address
    - Parse roofSegmentStats for pitch + area
    - Return total area where pitch < 5 degrees
    - Cache responses by address hash
    - Log cost (~$0.10 per call) and latency
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)


async def enrich_with_solar(candidates: list[Candidate], search_id: str) -> list[Candidate]:
    """Stub. Returns candidates unmodified.

    Stage 2 will populate roof_type, roof_area_sqft, roof_source for each.
    """
    logger.debug("Solar enrichment stub called for %d candidates (search %s).", len(candidates), search_id)
    return candidates
