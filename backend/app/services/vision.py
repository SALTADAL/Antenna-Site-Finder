"""Claude vision roof classifier. STAGE 4 IMPLEMENTATION.

Placeholder for the Stage 1 checkpoint. The real implementation will:
    - Pull a satellite tile via Google Maps Static API for each candidate's lat/lng
    - Send the tile to claude-3-5-sonnet (vision) with a constrained prompt
    - Parse the FLAT/PITCHED/MIXED/UNCLEAR answer
    - Cache by lat/lng + zoom + size
    - Log cost (~$0.003 per call) and latency
"""

from __future__ import annotations

from typing import Literal

from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)

VisionVerdict = Literal["FLAT", "PITCHED", "MIXED", "UNCLEAR"]


async def classify_roof(candidate: Candidate, search_id: str) -> VisionVerdict:
    """Stub. Returns UNCLEAR for everything."""
    logger.debug("Vision classify stub for %s (search %s).", candidate.place_id, search_id)
    return "UNCLEAR"
