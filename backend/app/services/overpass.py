"""OpenStreetMap Overpass API wrapper. STAGE 2 IMPLEMENTATION.

Placeholder for the Stage 1 checkpoint. The real implementation will:
    - Query Overpass for buildings within a small radius of each candidate's lat/lng
    - Extract `height` or `building:levels` tags
    - Estimate stories from height
    - Cache responses by rounded lat/lng
    - Be free (no API key) but throttled
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)


async def enrich_with_overpass(candidates: list[Candidate], search_id: str) -> list[Candidate]:
    """Stub. Returns candidates unmodified."""
    logger.debug("Overpass enrichment stub called for %d candidates (search %s).", len(candidates), search_id)
    return candidates
