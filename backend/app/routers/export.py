"""/export router. CSV download of a /search result.

Stage 1: accepts the same input as /search, runs the pipeline, and
streams a CSV. Stage 2 will add cached-result lookup by search_id so the
user doesn't pay twice for the same data.
"""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from app.logging_config import get_logger
from app.models import SearchRequest
from app.routers.search import post_search

logger = get_logger(__name__)

router = APIRouter(prefix="/export", tags=["export"])


CSV_COLUMNS = [
    "rank",
    "score",
    "business_name",
    "address",
    "city",
    "state",
    "zip",
    "phone",
    "latitude",
    "longitude",
    "google_place_id",
    "distance_miles",
    "roof_area_sqft",
    "roof_type",
    "roof_source",
    "building_height_m",
    "likely_independent",
    "chain_match",
    "rating",
    "user_ratings_total",
    "business_status",
    "note",
    "google_maps_url",
]


@router.post(".csv")
async def export_csv(req: SearchRequest) -> StreamingResponse:
    """Re-run /search and stream the result as CSV.

    Why re-run instead of caching the SearchResponse: searches are cached
    at the API-call level (places, solar, overpass), so a repeat /search
    with the same input is fast even though we don't cache the assembled
    response yet.
    """
    try:
        result = await post_search(req)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("CSV export failed")
        raise HTTPException(status_code=500, detail=f"Export failed: {e}")

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for i, c in enumerate(result.candidates, start=1):
        writer.writerow(
            {
                "rank": i,
                "score": c.score,
                "business_name": c.name,
                "address": c.address,
                "city": c.city,
                "state": c.state,
                "zip": c.zip,
                "phone": c.phone,
                "latitude": c.latitude,
                "longitude": c.longitude,
                "google_place_id": c.place_id,
                "distance_miles": c.distance_miles,
                "roof_area_sqft": c.roof_area_sqft if c.roof_area_sqft is not None else "",
                "roof_type": c.roof_type,
                "roof_source": c.roof_source,
                "building_height_m": c.building_height_m if c.building_height_m is not None else "",
                "likely_independent": "false" if c.is_chain else "true",
                "chain_match": c.chain_match or "",
                "rating": c.rating if c.rating is not None else "",
                "user_ratings_total": c.user_ratings_total if c.user_ratings_total is not None else "",
                "business_status": c.business_status or "",
                "note": c.note,
                "google_maps_url": c.google_maps_url,
            }
        )

    buf.seek(0)
    filename = f"antenna_candidates_{result.airport.icao}_{result.search_id}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
