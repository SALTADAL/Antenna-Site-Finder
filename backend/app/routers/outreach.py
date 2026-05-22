"""/candidates/{place_id}/state and /outreach routers.

CRUD over the outreach_state SQLite table. The /search router consumes
this state to annotate candidates and (optionally) filter out anything
already touched.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.db import (
    outreach_delete,
    outreach_get,
    outreach_list,
    outreach_set,
)
from app.logging_config import get_logger
from app.models import OutreachState, OutreachUpdateRequest

logger = get_logger(__name__)

router = APIRouter(tags=["outreach"])


@router.get("/candidates/{place_id}/state", response_model=OutreachState)
def get_candidate_state(place_id: str) -> OutreachState:
    """Fetch outreach state for one candidate. Returns 'untouched' if no row exists."""
    row = outreach_get(place_id)
    if not row:
        return OutreachState(place_id=place_id, status="untouched")
    return OutreachState(**row)


@router.put("/candidates/{place_id}/state", response_model=OutreachState)
def put_candidate_state(place_id: str, body: OutreachUpdateRequest) -> OutreachState:
    """Upsert outreach state for a candidate.

    Setting status='untouched' is allowed; we keep the row so the
    notes/contacted_by history isn't lost. To fully reset, DELETE the row.
    """
    try:
        result = outreach_set(
            place_id=place_id,
            status=body.status,
            notes=body.notes,
            contacted_by=body.contacted_by,
            business_name=body.business_name,
            airport_icao=body.airport_icao.upper(),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    logger.info("Outreach updated: %s -> %s", place_id, body.status)
    return OutreachState(**result)


@router.delete("/candidates/{place_id}/state")
def delete_candidate_state(place_id: str) -> dict:
    """Hard-reset a candidate to untouched (removes the SQLite row)."""
    removed = outreach_delete(place_id)
    return {"deleted": removed, "place_id": place_id}


@router.get("/outreach", response_model=list[OutreachState])
def list_outreach(airport: str | None = None) -> list[OutreachState]:
    """List every outreach row. Pass ?airport=KRDU to filter by ICAO."""
    rows = outreach_list(airport_icao=airport)
    return [OutreachState(**r) for r in rows]
