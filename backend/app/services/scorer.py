"""Suitability scoring. Full Stage 2 rubric (0-100 scale).

The rubric, per the brief:

    Distance to airport      20 pts  closer is better, linear taper to 25mi
    Roof flatness confidence 20 pts  Solar flat = 20, vision FLAT = 16,
                                     vision/Solar MIXED = 8/10, else 0
    Roof area                15 pts  flat-segment area in sqft
                                       25-49   = 8
                                       50-199  = 12
                                       200+    = 15
    Building height          10 pts  3-4 stories is the sweet spot
                                       1-2 stories (3-8m)    = 5
                                       3-4 stories (8-15m)   = 10
                                       5+  stories (>15m)    = 7
                                       unknown height        = 4 (partial)
    Likely independent       15 pts  independent = 15, chain = 0
    Active business           5 pts  recent reviews, OPERATIONAL status
    Reserve buffer           15 pts  not awarded programmatically; reserved
                                     for the manual reviewer's judgment

Programmatic ceiling is therefore 85, not 100. That's a deliberate
design choice from the spec: the last 15 are for a human looking at the
candidate in person.

Why "unknown" gets partial credit on some factors:
    - Height unknown: lots of small commercial buildings aren't tagged in
      OSM. Don't punish them.
    - Roof unknown: hard punish. We don't recommend buildings whose roofs
      we couldn't see, because the user shouldn't cold-call a candidate
      assuming a flat roof we never verified.
"""

from __future__ import annotations

from app.logging_config import get_logger
from app.models import Candidate

logger = get_logger(__name__)

# Rubric constants. Keep in one place so reweighting is a one-line change.
DISTANCE_TAPER_MILES = 25.0
DISTANCE_POINTS = 20

FLATNESS_POINTS_MAX = 20
AREA_POINTS_MAX = 15
HEIGHT_POINTS_MAX = 10
INDEPENDENT_POINTS = 15
ACTIVE_POINTS_MAX = 5
RESERVE_BUFFER = 15  # documented in score_breakdown but not added

PROGRAMMATIC_CEILING = (
    DISTANCE_POINTS + FLATNESS_POINTS_MAX + AREA_POINTS_MAX
    + HEIGHT_POINTS_MAX + INDEPENDENT_POINTS + ACTIVE_POINTS_MAX
)
# == 85


def _distance_score(distance_miles: float) -> float:
    """Linear taper to DISTANCE_TAPER_MILES. Clamped to [0, DISTANCE_POINTS]."""
    if distance_miles >= DISTANCE_TAPER_MILES:
        return 0.0
    fraction = max(0.0, 1.0 - (distance_miles / DISTANCE_TAPER_MILES))
    return round(DISTANCE_POINTS * fraction, 2)


def _flatness_score(c: Candidate) -> float:
    """Roof flatness, valued by source confidence."""
    if c.roof_source == "solar":
        if c.roof_type == "flat":
            return float(FLATNESS_POINTS_MAX)
        if c.roof_type == "mixed":
            return 10.0
        if c.roof_type == "pitched":
            return 0.0
    if c.roof_source == "vision":
        if c.roof_type == "flat":
            return 16.0
        if c.roof_type == "mixed":
            return 8.0
        if c.roof_type == "pitched":
            return 0.0
    return 0.0  # unknown source/type


def _area_score(c: Candidate) -> float:
    """Tiered by flat-area thresholds from the spec."""
    if c.roof_area_sqft is None:
        return 0.0
    a = c.roof_area_sqft
    if a < 25:
        return 0.0
    if a < 50:
        return 8.0
    if a < 200:
        return 12.0
    return float(AREA_POINTS_MAX)


def _height_score(c: Candidate) -> float:
    """3-4 stories is best. Unknown gets partial credit."""
    h = c.building_height_m
    if h is None:
        return 4.0
    if h < 3.0:
        return 3.0
    if h <= 8.0:
        return 5.0  # 1-2 stories
    if h <= 15.0:
        return float(HEIGHT_POINTS_MAX)  # 3-4 stories
    return 7.0  # 5+ stories


def _chain_score(is_chain: bool) -> float:
    """Independents get full points, chains get zero."""
    return 0.0 if is_chain else float(INDEPENDENT_POINTS)


def _active_score(rating: float | None, count: int | None, status: str | None) -> float:
    """Active-business signal from Places metadata."""
    if status and status.upper() not in {"OPERATIONAL", ""}:
        return 0.0
    if rating is None or count is None:
        return ACTIVE_POINTS_MAX * 0.5
    if count < 5:
        return ACTIVE_POINTS_MAX * 0.5
    return float(ACTIVE_POINTS_MAX)


def _note_for(score: int, candidate: Candidate) -> str:
    """One-line guidance for the field-ops user.

    Note text is tuned to the actual top-end score (~85) given the
    programmatic ceiling. We don't lie about scores in the 80s being
    "perfect" because the manual-review buffer still applies.
    """
    if candidate.is_chain:
        return f"Chain detected ({candidate.chain_match}). Skip unless you have a local-franchise contact."
    if candidate.roof_type == "unknown":
        if candidate.distance_miles <= 5.0:
            return "Roof type unknown. Worth a drive-by because the location is close to the airport."
        return "Roof type unknown. Verify in person before any outreach."
    if score >= 70:
        return "Strong candidate. Independent, flat roof, close to airport. Worth a same-day call."
    if score >= 55:
        return "Solid candidate. Verify roof access in person."
    if score >= 40:
        return "Possible candidate. Confirm roof type and building access before outreach."
    if candidate.roof_type == "pitched":
        return "Pitched roof. Generally not suitable. Include only if higher-tier list runs out."
    return "Weak. Include only if higher-tier list runs out."


def score_candidates(candidates: list[Candidate]) -> list[Candidate]:
    """Score, annotate, and sort descending.

    Each candidate ends up with:
        .score              integer 0..PROGRAMMATIC_CEILING (==85)
        .score_breakdown    per-factor floats for transparency in the UI
        .note               human-readable guidance
    """
    for c in candidates:
        d = _distance_score(c.distance_miles)
        f = _flatness_score(c)
        ar = _area_score(c)
        h = _height_score(c)
        ch = _chain_score(c.is_chain)
        act = _active_score(c.rating, c.user_ratings_total, c.business_status)

        total = d + f + ar + h + ch + act
        c.score = int(round(total))
        c.score_breakdown = {
            "distance": round(d, 2),
            "flatness": round(f, 2),
            "area": round(ar, 2),
            "height": round(h, 2),
            "independent": round(ch, 2),
            "active": round(act, 2),
            "reserve_buffer": float(RESERVE_BUFFER),
        }
        c.note = _note_for(c.score, c)

    candidates.sort(key=lambda x: x.score, reverse=True)
    return candidates
