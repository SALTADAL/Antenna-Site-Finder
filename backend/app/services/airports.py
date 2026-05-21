"""Airport ICAO -> coordinates lookup.

The data file is generated from the OurAirports public dataset by
`scripts/build_airports.py`. We ship the curated JSON in the repo so the
container starts without any external dependency.
"""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Iterable

from app.config import get_settings
from app.logging_config import get_logger
from app.models import Airport

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def _load_airports() -> dict[str, Airport]:
    """Load airports.json once and index by ICAO.

    Also indexes by IATA as a fallback, because field-ops occasionally
    types the 3-letter code (RDU) instead of the ICAO (KRDU).
    """
    path = get_settings().data_dir / "airports.json"
    if not path.exists():
        logger.warning("airports.json missing at %s; lookup will return empty.", path)
        return {}

    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)

    index: dict[str, Airport] = {}
    for item in raw:
        airport = Airport(
            icao=item["icao"].upper(),
            name=item.get("name", ""),
            city=item.get("city", ""),
            state=item.get("state", ""),
            latitude=float(item["latitude"]),
            longitude=float(item["longitude"]),
            is_er_covered=bool(item.get("is_er_covered", False)),
        )
        index[airport.icao] = airport
        iata = (item.get("iata") or "").upper()
        if iata and iata not in index:
            index[iata] = airport
    return index


def lookup(code: str) -> Airport | None:
    """Resolve an ICAO or IATA code. Returns None if not found."""
    return _load_airports().get(code.strip().upper())


def all_airports() -> Iterable[Airport]:
    """Iterate every airport in the dataset. Deduped by underlying ICAO."""
    seen = set()
    for airport in _load_airports().values():
        if airport.icao in seen:
            continue
        seen.add(airport.icao)
        yield airport
