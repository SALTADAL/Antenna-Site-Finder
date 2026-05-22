"""Pydantic models for request/response shapes.

Keeping these in one place because both the routers and services touch
them. If we ever expose an OpenAPI client, this is what generates it.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


RoofType = Literal["flat", "mixed", "pitched", "unknown"]

OutreachStatus = Literal[
    "untouched",
    "contacted",
    "followup",
    "interested",
    "declined",
    "won",
    "lost",
]


class SearchRequest(BaseModel):
    """Input for /search."""

    icao: str = Field(
        ...,
        min_length=3,
        max_length=4,
        description="ICAO airport code, e.g. KRDU. Three-letter IATA also accepted and resolved.",
    )
    radius_miles: float = Field(15.0, gt=0, le=50)
    include_chains: bool = Field(
        False,
        description="If true, chains are kept in the result list with chain=true and a 0 chain-bonus score.",
    )
    hide_contacted: bool = Field(
        True,
        description="If true, candidates with any outreach status other than 'untouched' are filtered out. Set false to see your full history at this airport.",
    )


class OutreachState(BaseModel):
    """Per-candidate outreach tracking."""

    place_id: str
    status: OutreachStatus = "untouched"
    last_contact_at: int | None = None  # unix seconds
    notes: str = ""
    contacted_by: str = ""
    business_name: str = ""
    airport_icao: str = ""
    updated_at: int | None = None


class OutreachUpdateRequest(BaseModel):
    """Body for PUT /candidates/{place_id}/state."""

    status: OutreachStatus
    notes: str = ""
    contacted_by: str = ""
    business_name: str = ""
    airport_icao: str = ""


class Airport(BaseModel):
    """Minimal airport record."""

    icao: str
    name: str
    city: str
    state: str
    latitude: float
    longitude: float
    is_er_covered: bool = False


class Candidate(BaseModel):
    """A single rooftop-host candidate. One row in the output CSV."""

    place_id: str
    name: str
    address: str
    city: str
    state: str
    zip: str = ""
    phone: str = ""
    latitude: float
    longitude: float
    distance_miles: float

    # Roof analysis (populated in Stage 2)
    roof_type: RoofType = "unknown"
    roof_area_sqft: float | None = None
    roof_source: Literal["solar", "vision", "none"] = "none"
    building_height_m: float | None = None

    # Chain detection (Stage 1)
    is_chain: bool = False
    chain_match: str | None = None

    # Business activity signal
    rating: float | None = None
    user_ratings_total: int | None = None
    business_status: str | None = None

    # Scoring (Stage 2)
    score: int = 0
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    note: str = ""

    google_maps_url: str = ""

    # Outreach tracking (Stage 5). None = untouched (no row in DB).
    outreach: OutreachState | None = None


class CostBreakdown(BaseModel):
    by_api: dict[str, dict[str, float]] = Field(default_factory=dict)
    total_usd: float = 0.0


class OutreachCounts(BaseModel):
    """Aggregated counts for the search summary panel."""

    total_known: int = 0
    hidden: int = 0
    by_status: dict[str, int] = Field(default_factory=dict)


class SearchResponse(BaseModel):
    """Output for /search."""

    search_id: str
    airport: Airport
    radius_miles: float
    candidate_count: int
    candidates: list[Candidate]
    cost: CostBreakdown
    pipeline_stage: Literal["places", "scored", "complete"] = "complete"
    mock_mode: bool = False
    warnings: list[str] = Field(default_factory=list)
    outreach_counts: OutreachCounts = Field(default_factory=OutreachCounts)
