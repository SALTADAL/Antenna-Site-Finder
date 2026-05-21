"""Suitability scoring.

The full rubric (Stage 2) is 0-100 across seven factors. In Stage 1 we
score only on what we know without Solar/Overpass/Vision:
    - Distance to airport (20 points)
    - Chain status (15 points: 0 if chain, 15 if independent)
    - Active business signal (5 points: based on recent Places ratings)
    - Reserve: 60 points held for the Stage 2 factors

Stage 1 scores will look low. That's intentional. We don't want the user
acting on a "score: 95" that was computed without ever looking at the roof.
The frontend will show a "Stage 1 (no roof data)" badge until Stage 2
lights up Solar/Vision enrichment.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)

# Distance scoring uses a linear taper to 25 miles. Candidates beyond the
# search radius shouldn't reach here, but if they do they score 0.
DISTANCE_TAPER_MILES = 25.0
DISTANCE_POINTS = 20

CHAIN_INDEPENDENT_POINTS = 15
ACTIVE_BUSINESS_POINTS = 5


def _distance_score(distance_miles: float) -> float:
    """Closer is better. Linear taper, clamped to [0, DISTANCE_POINTS]."""
    if distance_miles >= DISTANCE_TAPER_MILES:
        return 0.0
    fraction = max(0.0, 1.0 - (distance_miles / DISTANCE_TAPER_MILES))
    return round(DISTANCE_POINTS * fraction, 2)


def _chain_score(is_chain: bool) -> float:
    """Independent = full points, chain = 0."""
    return 0.0 if is_chain else float(CHAIN_INDEPENDENT_POINTS)


def _active_score(rating: float | None, count: int | None, status: str | None) -> float:
    """Active business signal from Places metadata.

    Heuristic: rating present, at least 5 reviews, status not CLOSED.
    Stage 2 will add a freshness check if Places exposes last-review-time.
    """
    if status and status.upper() not in {"OPERATIONAL", ""}:
        return 0.0
    if rating is None or count is None:
        return ACTIVE_BUSINESS_POINTS * 0.5  # half credit for unknown
    if count < 5:
        return ACTIVE_BUSINESS_POINTS * 0.5
    return float(ACTIVE_BUSINESS_POINTS)


def _note_for(score: int, candidate: Candidate) -> str:
    """One-line guidance for the field-ops user."""
    if candidate.is_chain:
        return f"Chain detected ({candidate.chain_match}). Skip unless you have a local-franchise contact."
    if score >= 80:
        return "Strong candidate. Independent, close to airport. Worth a same-day call."
    if score >= 60:
        return "Solid candidate. Verify roof access in person."
    if score >= 40:
        return "Possible candidate. Roof type needs confirmation before outreach."
    return "Weak. Include only if higher-tier list runs out."


def score_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Score and annotate candidates. Stage 1 partial scoring.

    Sorts the returned list descending by score.
    """
    out: list[Candidate] = []
    for c in candidates:
        d = _distance_score(c.distance_miles)
        ch = _chain_score(c.is_chain)
        act = _active_score(c.rating, c.user_ratings_total, c.business_status)

        total = d + ch + act
        c.score = int(round(total))
        c.score_breakdown = {
            "distance": d,
            "chain": ch,
            "active": act,
            "roof_pending": 0.0,
            "height_pending": 0.0,
            "area_pending": 0.0,
            "reserve_buffer": 0.0,
        }
        c.note = _note_for(c.score, c)
        out.append(c)

    out.sort(key=lambda x: x.score, reverse=True)
    return out
