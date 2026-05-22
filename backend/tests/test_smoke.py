"""End-to-end smoke test for Stage 1.

Verifies the pipeline runs against the KRDU mock fixture and that:
    - Airport lookup resolves
    - Places fixture loads
    - Chain detection flags the obvious ones (Starbucks, Subway, etc.)
    - Distance filter drops the "Far Distant Diner" fixture
    - Scoring runs and orders results descending
    - CSV columns line up

Run from the backend dir:
    APP_MODE=mock CACHE_DB_PATH=/tmp/asf_test.db LOG_FILE=/tmp/asf_test.log python -m pytest tests/test_smoke.py -v
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

# Allow running this file directly: `python tests/test_smoke.py`
BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("APP_MODE", "mock")
os.environ.setdefault("CACHE_DB_PATH", "/tmp/asf_test.db")
os.environ.setdefault("LOG_FILE", "/tmp/asf_test.log")

# Wipe a previous test cache so cost_log starts clean.
for p in ("/tmp/asf_test.db", "/tmp/asf_test.db-wal", "/tmp/asf_test.db-shm"):
    Path(p).unlink(missing_ok=True)

from app.db import init_db  # noqa: E402
from app.models import SearchRequest  # noqa: E402
from app.routers.search import post_search  # noqa: E402
from app.services import chain_detect  # noqa: E402


def test_chain_detection_basic() -> None:
    """Sanity check the chain detector on representative names."""
    assert chain_detect.detect("Starbucks")[0] is True
    assert chain_detect.detect("Starbucks #12345")[0] is True
    assert chain_detect.detect("McDonald's")[0] is True
    assert chain_detect.detect("The Home Depot")[0] is True
    assert chain_detect.detect("Big O Tires")[0] is True
    assert chain_detect.detect("Bovinos Italian Kitchen")[0] is False
    assert chain_detect.detect("Joe's Garage & Performance")[0] is False
    assert chain_detect.detect("")[0] is False


def test_krdu_pipeline_end_to_end() -> None:
    """Run /search against KRDU and check the shape + content."""
    init_db()
    req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=True)
    resp = asyncio.run(post_search(req))

    assert resp.airport.icao == "KRDU"
    assert resp.mock_mode is True
    assert resp.candidate_count > 0

    # Should have flagged at least the obvious chains
    chain_names = {c.name for c in resp.candidates if c.is_chain}
    assert "Starbucks" in chain_names, f"Expected Starbucks to be flagged. Got: {chain_names}"
    assert "Subway" in chain_names, f"Expected Subway to be flagged. Got: {chain_names}"
    assert "The Home Depot" in chain_names
    assert "Walmart Supercenter" in chain_names
    assert "7-Eleven" in chain_names

    # Independents should NOT be flagged
    indep_names = {c.name for c in resp.candidates if not c.is_chain}
    assert "Bovinos Italian Kitchen" in indep_names
    assert "Joe's Garage & Performance" in indep_names
    assert "Triangle Auto Body & Paint" in indep_names

    # The "Far Distant Diner" fixture is at lat 36.15 / lng -78.50, which is
    # >25 miles from KRDU. Should be filtered out by the radius check.
    all_names = {c.name for c in resp.candidates}
    assert "Far Distant Diner" not in all_names, "Distance filter failed."

    # Scores should be descending
    scores = [c.score for c in resp.candidates]
    assert scores == sorted(scores, reverse=True)

    # Top candidate must be an independent
    assert not resp.candidates[0].is_chain, (
        f"Top candidate is a chain: {resp.candidates[0].name}. "
        "Independents should outrank chains at equal distance."
    )

    print(f"\n[smoke] KRDU returned {resp.candidate_count} candidates.")
    print(f"[smoke] Top 5:")
    for i, c in enumerate(resp.candidates[:5], 1):
        flag = "[CHAIN]" if c.is_chain else "       "
        print(f"  {i}. {flag} score={c.score:3d}  dist={c.distance_miles:5.2f}mi  {c.name}")


def test_chains_excluded_by_default() -> None:
    """include_chains=False should drop the chains entirely."""
    req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=False)
    resp = asyncio.run(post_search(req))
    for c in resp.candidates:
        assert not c.is_chain, f"Chain leaked through: {c.name}"


def test_stage2_enrichment_populates_roof_data() -> None:
    """Solar and Overpass mock fixtures should populate roof + height fields."""
    req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=True)
    resp = asyncio.run(post_search(req))

    # After Stage 4 vision fallback, every candidate should have a known
    # roof type (Solar covered most; vision covered the two Solar nulls).
    known = [c for c in resp.candidates if c.roof_type != "unknown"]
    assert len(known) == len(resp.candidates), (
        f"Expected all candidates to have a known roof type after Stage 4 vision fallback, "
        f"got {len(known)}/{len(resp.candidates)}"
    )

    # Score breakdown should include all Stage 2 factors
    top = resp.candidates[0]
    for key in ("distance", "flatness", "area", "height", "independent", "active"):
        assert key in top.score_breakdown, f"Missing {key} in score_breakdown"

    # Top candidate should score >= 70 (the spec's "strong candidate" floor)
    assert top.score >= 70, f"Top candidate scored only {top.score}; rubric may be miscalibrated."


def test_stage4_vision_fallback_resolves_solar_gaps() -> None:
    """Candidates Solar can't see should be resolved by Claude vision."""
    req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=True)
    resp = asyncio.run(post_search(req))

    vision_resolved = [c for c in resp.candidates if c.roof_source == "vision"]
    # Mock fixture defines vision verdicts for exactly two candidates.
    assert len(vision_resolved) == 2, f"Expected 2 vision-resolved candidates, got {len(vision_resolved)}"
    names = {c.name for c in vision_resolved}
    assert "Carolina Hardware & Supply Co" in names
    assert "Park West Auto & Truck Repair" in names


def test_outreach_state_set_and_filter() -> None:
    """Setting outreach state should annotate candidates and filter them out."""
    from app.db import outreach_set, outreach_delete

    # Pick a candidate that's currently in the KRDU results.
    target_place_id = "fixture_krdu_001"  # Triangle Auto Body & Paint

    # Mark it as contacted
    outreach_set(
        place_id=target_place_id,
        status="contacted",
        notes="Left voicemail",
        contacted_by="Test Runner",
        business_name="Triangle Auto Body & Paint",
        airport_icao="KRDU",
    )

    try:
        # hide_contacted=True (default) should drop this candidate
        req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=False, hide_contacted=True)
        resp_hidden = asyncio.run(post_search(req))
        place_ids_visible = {c.place_id for c in resp_hidden.candidates}
        assert target_place_id not in place_ids_visible, (
            "Contacted candidate should be hidden when hide_contacted=True."
        )
        assert resp_hidden.outreach_counts.hidden >= 1, (
            f"Expected at least 1 hidden in outreach_counts, got {resp_hidden.outreach_counts.hidden}"
        )

        # hide_contacted=False should keep it AND attach the outreach state
        req2 = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=False, hide_contacted=False)
        resp_shown = asyncio.run(post_search(req2))
        match = next((c for c in resp_shown.candidates if c.place_id == target_place_id), None)
        assert match is not None, "Candidate should reappear when hide_contacted=False."
        assert match.outreach is not None, "Outreach state should be attached."
        assert match.outreach.status == "contacted"
        assert match.outreach.notes == "Left voicemail"
    finally:
        # Clean up so other tests stay isolated
        outreach_delete(target_place_id)


def test_csv_export_columns() -> None:
    """Export router should produce a CSV with all 23 spec columns."""
    import asyncio as aio
    from app.routers.export import CSV_COLUMNS, export_csv

    async def run() -> str:
        req = SearchRequest(icao="KRDU", radius_miles=15.0, include_chains=False)
        resp = await export_csv(req)
        body = b""
        async for chunk in resp.body_iterator:
            body += chunk.encode() if isinstance(chunk, str) else chunk
        return body.decode("utf-8")

    csv_text = aio.run(run())
    header_line = csv_text.splitlines()[0]
    cols = header_line.split(",")
    assert cols == CSV_COLUMNS, f"CSV header mismatch.\nGot: {cols}\nExpected: {CSV_COLUMNS}"
    assert len(csv_text.splitlines()) > 1, "CSV has no data rows"


if __name__ == "__main__":
    test_chain_detection_basic()
    print("[ok] chain detection unit tests passed.")
    test_krdu_pipeline_end_to_end()
    print("[ok] KRDU pipeline end-to-end passed.")
    test_chains_excluded_by_default()
    print("[ok] include_chains=False filter passed.")
    test_stage2_enrichment_populates_roof_data()
    print("[ok] Stage 2 enrichment populates roof data.")
    test_stage4_vision_fallback_resolves_solar_gaps()
    print("[ok] Stage 4 vision fallback resolves Solar gaps.")
    test_outreach_state_set_and_filter()
    print("[ok] Outreach state filter and annotation work.")
    test_csv_export_columns()
    print("[ok] CSV export columns match spec.")
    print("\nAll smoke tests passed.")
