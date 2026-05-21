# Antenna Site Finder

Internal tool for Enhanced Radar field ops. Given a US airport code, returns a ranked list of nearby small businesses likely to have flat roof space suitable for hosting an aviation antenna.

Built to scale ER's site-acquisition pipeline from 80 to 200+ airports without proportionally scaling the field team.

## Status

This is **Stage 1 of 4**. The backend pipeline runs end-to-end against fixture data for KRDU and produces a ranked candidate list. The remaining stages add roof analysis, the frontend, and the polish layer.

| Stage | What ships | Status |
|-------|------------|--------|
| 1 | Backend scaffold, airports/chains data, Places service with mock-mode, chain detection, partial scoring, CSV export wired | Complete |
| 2 | Google Solar API, OpenStreetMap building heights, full 0-100 scoring rubric | Pending |
| 3 | React frontend (form, table, map, CSV download), docker-compose end-to-end | Pending |
| 4 | Claude vision fallback for roofs Solar can't see, cost tracking in UI, screenshots in README | Pending |

## What works today

- ICAO/IATA airport lookup against 916 US large and medium airports, with 80 flagged as ER-covered stand-ins
- Places search across 11 business types (mock fixtures for KRDU; live mode wired and ready for a Google Maps API key)
- Chain detection against 729 curated US chain names with two match modes (exact + safe substring)
- Per-candidate distance computation, active-business scoring, chain filtering
- CSV export with all 23 spec columns
- SQLite cache for every external API response (per-call hashing)
- Per-search cost log, ready to be surfaced in the UI in Stage 4
- Comprehensive logging (stdout + rotating file)
- Single-command Docker workflow (`docker compose up`)

## What does NOT work yet

- Roof type, area, and building height are placeholder fields. They'll populate once Stage 2 wires Solar API and Overpass.
- The Claude vision fallback returns UNCLEAR for everything. Stage 4 will wire it for real.
- No frontend. You can curl the backend or use the `/docs` interactive Swagger page.

## Quick start (Stage 1)

```bash
cd Antenna_Site_Finder
cp .env.template .env
# Leave APP_MODE=mock for now. No keys needed.
docker compose up backend
```

Then in another terminal:

```bash
# Health check
curl http://localhost:8000/healthz

# Run a search against KRDU
curl -s -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"icao":"KRDU","radius_miles":15,"include_chains":false}' | jq

# Download as CSV
curl -s -X POST http://localhost:8000/export.csv \
  -H 'Content-Type: application/json' \
  -d '{"icao":"KRDU","radius_miles":15,"include_chains":false}' \
  -o krdu_candidates.csv
```

Or, without Docker:

```bash
cd backend
pip install -r requirements.txt
APP_MODE=mock CACHE_DB_PATH=./cache.db LOG_FILE=./logs/app.log \
  uvicorn app.main:app --reload
```

Interactive API docs: http://localhost:8000/docs

## How the pipeline works

1. **Resolve airport** by ICAO (KRDU) or IATA (RDU) against `app/data/airports.json`
2. **Nearby search** for 11 business types across the radius. Mock fixtures today; Google Places when `APP_MODE=live`.
3. **Dedupe** by Place ID
4. **Chain detection** against `app/data/chains.json`
5. **Solar enrichment** (Stage 2: pitch + area per roof segment)
6. **Vision fallback** (Stage 4: Claude vision on a Static Maps satellite tile when Solar has no coverage)
7. **Building height** (Stage 2: OpenStreetMap Overpass)
8. **Score** 0-100 across distance, roof flatness, area, height, independence, active-business signal
9. **Annotate** each candidate with a one-line note for the field-ops user
10. **Cost summary** aggregated across the search and returned with the response

## API keys

You need two keys for live mode:

1. **Google Maps Platform** with billing enabled. Enable these APIs on the key:
   - Places API (legacy nearby + details)
   - Solar API
   - Maps Static API

   Restrict the key to your machine's IP for safety. Get it at https://console.cloud.google.com/apis/credentials

2. **Anthropic** for the Claude vision fallback. Get it at https://console.anthropic.com/

Paste both into `.env`. Set `APP_MODE=live` to start hitting real APIs.

## Cost expectations

| Search type | API spend (live mode) |
|-------------|----------------------|
| First search at a new airport | $5 to $15 |
| Repeat search at the same airport (within cache) | < $0.01 |

Cache hits are tracked. The UI in Stage 4 will show the per-search spend as a badge.

## Data freshness

The chain list and airport list are committed to the repo. Both regenerate from authoritative sources:

```bash
cd backend
python scripts/build_airports.py   # Re-pulls OurAirports
python scripts/build_chains.py     # Re-builds chains.json from the curated list in the script
```

When you discover a chain we missed, add it to `scripts/build_chains.py` and rerun.

## What the tool does NOT know

This section will grow in Stage 2-4. For now:

- We have no roof data. Every candidate shows `roof_type: unknown`. Stage 2 fixes this.
- The 80-airport ER-covered list in `airports.json` is a stand-in based on the deep-dive doc, not the actual deployed list. Edit `ER_COVERED_HINTS` in `scripts/build_airports.py` once you have the real list.
- The chain database covers the major chains we'd expect to see in field-ops searches, but it's not exhaustive. The quality bar (per the brief) is "no chain leaks through" — false positives hurt less than false negatives, so we err conservatively. Add chains as you discover gaps.

## Repo layout

```
Antenna_Site_Finder/
  backend/
    app/
      main.py                FastAPI entry point
      config.py              Settings via pydantic-settings
      logging_config.py      Stdout + rotating-file logging
      db.py                  SQLite cache + cost log
      models.py              Pydantic request/response shapes
      routers/
        search.py            POST /search
        export.py            POST /export.csv
      services/
        airports.py          ICAO lookup
        places.py            Google Places (live + mock)
        chain_detect.py      Chain matching (exact + substring)
        scorer.py            Suitability scoring rubric
        solar.py             [Stage 2 stub] Google Solar API
        overpass.py          [Stage 2 stub] OSM Overpass
        vision.py            [Stage 4 stub] Claude vision
      data/
        airports.json        US large+medium airports
        chains.json          729 known chain names
      fixtures/
        places/KRDU.json     Mock places data for KRDU
    scripts/
      build_airports.py      Regenerate airports.json
      build_chains.py        Regenerate chains.json
    tests/
      test_smoke.py          End-to-end pipeline smoke test
    Dockerfile
    requirements.txt
  frontend/                  [Stage 3]
  docs/screenshots/          [Stage 4]
  docker-compose.yml
  .env.template
  .gitignore
```

## Running tests

```bash
cd backend
APP_MODE=mock CACHE_DB_PATH=/tmp/asf_test.db LOG_FILE=/tmp/asf_test.log \
  python tests/test_smoke.py
```
