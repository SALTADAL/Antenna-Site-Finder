"""Build app/data/airports.json from the OurAirports public dataset.

Source: https://davidmegginson.github.io/ourairports-data/airports.csv
License: CC0

We filter to US airports of type {large_airport, medium_airport,
small_airport} that have a non-empty ICAO/ident code. The output is a
list of dicts with: icao, iata, name, city, state, latitude, longitude,
is_er_covered.

Enhanced Radar's 80-airport list isn't public. We flag a stand-in set of
likely-covered hubs from the deep-dive context (KCLT, KSFO, KJFK, KAUS,
KORD, KATL, KRDU, etc.) and the field-ops user can update the
ER_COVERED_HINTS set later.

Run from inside the backend container:
    python scripts/build_airports.py

Or locally:
    cd backend && python scripts/build_airports.py
"""

from __future__ import annotations

import csv
import io
import json
import sys
import urllib.request
from pathlib import Path

OUR_AIRPORTS_URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"

# Conservative stand-in for ER's deployed-airport list. The user can edit
# this in airports.json directly after the build, or update the set here.
ER_COVERED_HINTS = {
    # Mentioned in the deep-dive doc directly
    "KCLT", "KSFO", "KJFK", "KAUS", "KORD", "KATL", "KRDU",
    # Mid-size hubs likely to be early ER deployments based on the doc framing
    "KMSP", "KDFW", "KIAH", "KMIA", "KMCO", "KBOS", "KLAX", "KSEA",
    "KDEN", "KPHX", "KLAS", "KSLC", "KPDX", "KSAN", "KDTW", "KPHL",
    "KEWR", "KLGA", "KDCA", "KIAD", "KBWI", "KSTL", "KCMH", "KMSY",
    "KSJC", "KOAK", "KMDW", "KTPA", "KFLL", "KPIT", "KCLE", "KIND",
    "KCVG", "KSAT", "KMEM", "KBNA", "KSMF", "KSNA", "KHOU", "KDAL",
    "KHNL", "KABQ", "KJAX", "KRSW", "KPVD", "KBUR", "KONT", "KOGG",
    "KBDL", "KRIC", "KORF", "KGSO", "KCHS", "KSAV", "KMKE", "KOMA",
    "KOKC", "KTUL", "KBHM", "KBUF", "KROC", "KSYR", "KALB", "KMHT",
    "KPWM", "KBTV", "KBOI", "KGEG", "KICT", "KDSM", "KMSN", "KGRR",
    "KFNT", "KTOL", "KAVL",
}

ALLOWED_TYPES = {"large_airport", "medium_airport"}


def fetch_csv() -> str:
    """Download the OurAirports CSV as text."""
    req = urllib.request.Request(
        OUR_AIRPORTS_URL,
        headers={"User-Agent": "antenna-site-finder/0.1 (internal tool)"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read().decode("utf-8")


def parse_and_filter(csv_text: str) -> list[dict]:
    """Filter to US large/medium airports with valid ICAOs."""
    reader = csv.DictReader(io.StringIO(csv_text))
    out: list[dict] = []
    for row in reader:
        if row.get("iso_country") != "US":
            continue
        if row.get("type") not in ALLOWED_TYPES:
            continue

        icao = (row.get("ident") or "").strip().upper()
        if not icao or len(icao) != 4:
            continue

        iata = (row.get("iata_code") or "").strip().upper()
        name = (row.get("name") or "").strip()
        city = (row.get("municipality") or "").strip()

        # OurAirports stores the state in iso_region as "US-NC"
        region = (row.get("iso_region") or "").strip()
        state = region.split("-")[-1] if "-" in region else ""

        try:
            lat = float(row["latitude_deg"])
            lng = float(row["longitude_deg"])
        except (KeyError, TypeError, ValueError):
            continue

        out.append(
            {
                "icao": icao,
                "iata": iata,
                "name": name,
                "city": city,
                "state": state,
                "latitude": round(lat, 6),
                "longitude": round(lng, 6),
                "is_er_covered": icao in ER_COVERED_HINTS,
            }
        )
    return out


def main() -> int:
    """Entry point. Writes app/data/airports.json next to this script's package."""
    out_dir = Path(__file__).resolve().parent.parent / "app" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "airports.json"

    print(f"Fetching {OUR_AIRPORTS_URL} ...")
    csv_text = fetch_csv()
    airports = parse_and_filter(csv_text)
    print(f"Filtered to {len(airports)} US large/medium airports.")
    covered = sum(1 for a in airports if a["is_er_covered"])
    print(f"Flagged {covered} as ER-covered stand-ins.")

    out_path.write_text(json.dumps(airports, indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
