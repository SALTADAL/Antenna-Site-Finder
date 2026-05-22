# Antenna Site Finder

Internal tool for Enhanced Radar field ops. Given a US airport code, returns a ranked list of nearby small businesses with flat roof space suitable for hosting an aviation antenna.

Built to scale ER's site-acquisition pipeline from 80 to 200+ airports without proportionally scaling the field team.

## What the tool does

You type **KRDU**. Sixty to 180 seconds later (under 5 seconds for a repeat) you have a CSV of 50 to 100 candidate businesses within 15 miles, each with:

- Business name, address, phone, Google Place ID, Maps link
- Distance to the airport (miles)
- Roof type (flat / mixed / pitched / unknown) and the source (Solar API or Claude vision)
- Roof area in square feet, building height in meters
- Chain detection (likely independent vs. known chain, with the matched brand name)
- Suitability score from 0 to 85 (programmatic), with 15 points reserved for the field-ops reviewer's in-person judgment
- A one-line action note ("Strong candidate. Worth a same-day call.")

Open the same data in the web UI for a sortable table, a Leaflet map with score-colored pins, and a tap-to-call detail card.

## Quick start

```bash
cd Antenna_Site_Finder
cp .env.template .env             # tweak APP_MODE and keys here
docker compose up                 # backend :8000, frontend :5173
```

Open http://localhost:5173 and search KRDU.

To run without Docker:

```bash
# Backend
cd backend
pip install -r requirements.txt
APP_MODE=mock CACHE_DB_PATH=./cache.db LOG_FILE=./logs/app.log \
  uvicorn app.main:app --reload

# Frontend (in another terminal)
cd frontend
npm install
npm run dev
```

## Two modes

**Mock mode** (`APP_MODE=mock` in `.env`): the default. Runs against bundled fixtures for KRDU. Zero API spend, zero key requirements. Use this for development and demos.

**Live mode** (`APP_MODE=live`): hits real Google Places, Solar, Static Maps, and Anthropic APIs. The frontend shows a green "Live mode ready" banner after preflight; if anything is misconfigured you'll get a red banner explaining what.

## Getting the API keys

### Google Maps Platform

You need one key with billing enabled and these APIs turned on:

- **Places API** (legacy or new, both work; we use legacy nearby + details)
- **Solar API**
- **Maps Static API** (for the Claude vision fallback)

Steps:

1. Open https://console.cloud.google.com/apis/credentials
2. Create a new API key. Restrict it to your machine's IP for safety.
3. In the API Library, enable the three APIs above.
4. Make sure billing is attached to the project. Google's free tier covers some of this but Solar will charge from request one.
5. Paste the key into `.env` as `GOOGLE_MAPS_API_KEY`.

### Anthropic

1. Open https://console.anthropic.com/
2. Generate an API key.
3. Paste into `.env` as `ANTHROPIC_API_KEY`.

Then flip `APP_MODE=live` in `.env`, restart with `docker compose up`, and click the preflight banner status to confirm both keys validate.

## Cost expectations

| Search type | Approximate cost |
|---|---|
| First search at a new airport (50-100 candidates) | $5 to $15 |
| Repeat search at the same airport (full cache hit) | < $0.01 |
| Preflight check | < $0.01 |

Per-call estimates the tool tracks:

| API | Cost per call | When called |
|---|---|---|
| Places Nearby Search | $0.032 | Once per business type, paginated |
| Places Details | $0.017 | Once per unique place_id |
| Solar API findClosest | $0.10 | Once per non-chain candidate |
| Static Maps satellite tile | $0.002 | Once per unknown-roof candidate (vision fallback only) |
| Claude vision (Sonnet) | $0.003 | Same as above |
| Overpass API | free | Once per candidate |

The UI shows per-API spend per search in the left panel under "By API".

## How the pipeline works

1. **Resolve airport** by ICAO (KRDU) or IATA (RDU) against `app/data/airports.json` (916 US airports, 80 flagged as ER-covered stand-ins)
2. **Nearby search** across 11 business types, paginated up to 60 per type
3. **Dedupe** by Place ID
4. **Chain detection** against 729 curated brand names with exact and safe-substring matching
5. **Solar enrichment** parses roof segment stats; sums area where pitch < 5 degrees
6. **Overpass building heights** from OpenStreetMap (free, throttled across two endpoints)
7. **Vision fallback** for any candidate Solar couldn't see: Google Static Maps satellite tile → Claude vision → FLAT / PITCHED / MIXED / UNCLEAR
8. **Score** across six factors on a 0-85 scale, sorted descending
9. **Annotate** each candidate with a one-line action note
10. **Cost summary** aggregated across the search

## Scoring rubric (0-85 programmatic + 15 manual reserve)

| Factor | Max | How it's awarded |
|---|---|---|
| Distance to airport | 20 | Linear taper to 25 miles |
| Roof flatness | 20 | Solar flat = 20, Solar mixed = 10, vision flat = 16, vision mixed = 8, else 0 |
| Roof area | 15 | <25 sqft = 0, 25-49 = 8, 50-199 = 12, 200+ = 15 |
| Building height | 10 | 1-2 stories = 5, 3-4 stories = 10, 5+ stories = 7, unknown = 4 |
| Likely independent | 15 | Independent = 15, chain = 0 |
| Active business | 5 | OPERATIONAL with recent reviews |
| **Manual reserve** | 15 | Held back for the field-ops reviewer to award after in-person check |

A score of 70+ means "strong candidate, call today." 50-69 is "worth a visit." Below 50 is "verify before outreach."

## What this tool does NOT know

This section matters more than the feature list. We're explicit about the limits so the field-ops user doesn't act on the wrong signal.

- **Roof access.** We can see that a roof is flat, but not whether the owner will let you on it, whether there's a usable ladder, whether the parapet wall is high enough for safe install, or whether HVAC takes up the prime square footage. Every "Strong candidate" still needs a site visit before a binding ask.
- **Property ownership.** Many "independent" businesses are tenants in a building owned by someone else. The signage is on the storefront, the lease decision is upstairs. The tool flags the storefront; the field rep needs to find the landlord.
- **Line-of-sight.** Distance to the airport is a proxy. Actual antenna LOS depends on terrain, trees, taller buildings between the host site and the tower. Stage 5 candidate: integrate Open-Elevation API for an LOS sanity check.
- **The 80-airport ER-covered list** in `airports.json` is a stand-in based on the deep-dive doc, not ER's actual deployed-airport list. Edit `ER_COVERED_HINTS` in `scripts/build_airports.py` once you have the real list and rerun.
- **Chain detection is conservative.** The 729-entry list covers the major US chains across all 11 search categories. New chains exist. When you find one we missed, add it to `scripts/build_chains.py` and re-run. We err on the side of false negatives (letting a chain through to the list) over false positives (flagging an independent as a chain) because false positives cost real leads and burn trust.
- **Phone numbers from Places are not always staffed.** Cold-call decision tree: phone → if voicemail twice, drive-by → if locked, look up parent property on the county tax assessor site.
- **The score is a ranking signal, not a guarantee.** A score of 80 means our six programmatic checks all passed. It does not mean the deal is closeable.

## Repo layout

```
Antenna_Site_Finder/
├── backend/
│   ├── app/
│   │   ├── main.py                 FastAPI entry point
│   │   ├── config.py               pydantic-settings configuration
│   │   ├── logging_config.py       stdout + rotating-file logging
│   │   ├── db.py                   SQLite cache + cost log
│   │   ├── models.py               Pydantic request/response shapes
│   │   ├── routers/
│   │   │   ├── search.py           POST /search
│   │   │   ├── export.py           POST /export.csv
│   │   │   └── preflight.py        GET  /preflight
│   │   ├── services/
│   │   │   ├── airports.py         ICAO/IATA lookup
│   │   │   ├── places.py           Google Places (live + mock)
│   │   │   ├── chain_detect.py     Chain matching (exact + substring)
│   │   │   ├── solar.py            Google Solar API (live + mock)
│   │   │   ├── overpass.py         OSM building heights
│   │   │   ├── vision.py           Claude vision fallback
│   │   │   └── scorer.py           Six-factor suitability scoring
│   │   ├── data/
│   │   │   ├── airports.json       916 US airports
│   │   │   └── chains.json         729 chain brand names
│   │   └── fixtures/
│   │       ├── places/KRDU.json    Mock Places response
│   │       ├── solar/KRDU.json     Mock Solar verdicts
│   │       ├── overpass/KRDU.json  Mock building heights
│   │       └── vision/KRDU.json    Mock vision verdicts (only for unknowns)
│   ├── scripts/
│   │   ├── build_airports.py       Regenerate airports.json
│   │   └── build_chains.py         Regenerate chains.json
│   ├── tests/
│   │   └── test_smoke.py           End-to-end pipeline smoke test
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx                 Layout + state
│   │   ├── api.js                  Tiny fetch client
│   │   ├── index.css               Tailwind base + a few polish rules
│   │   ├── main.jsx                React entrypoint
│   │   └── components/
│   │       ├── SearchForm.jsx
│   │       ├── ResultsTable.jsx
│   │       ├── ResultsMap.jsx
│   │       ├── CandidateCard.jsx
│   │       └── PreflightBanner.jsx
│   ├── package.json
│   ├── vite.config.js
│   ├── tailwind.config.js
│   ├── postcss.config.js
│   ├── index.html
│   └── Dockerfile
├── docker-compose.yml
├── .env.template
├── .gitignore
└── README.md
```

## Running the tests

```bash
cd backend
APP_MODE=mock CACHE_DB_PATH=/tmp/asf_test.db LOG_FILE=/tmp/asf_test.log \
  python tests/test_smoke.py
```

Smoke test asserts:
- Chain detection catches obvious chains and lets independents through
- KRDU mock fixture loads and produces 24 candidates
- Far-away fixture is filtered by radius
- Top candidate is an independent with a score in the strong-candidate range
- Solar + Overpass enrichment populates roof + height fields
- CSV export has all 23 spec columns

## Screenshots

_To be added once you launch `docker compose up` and grab the UI in action._

Expected screens:
- Search panel + empty state
- Mid-search loading panel with the pipeline progress steps
- Results table view with color-coded score chips
- Results map view with score-tinted pins around the airport
- Candidate card modal with the score breakdown and call/Maps actions

## Where to take it next

- **Owner lookup** via state Secretary of State business records (manual scraper for the top 5 states first)
- **LOS check** via Open-Elevation API per the section above
- **CRM exports** for Attio and HubSpot (column reordering + UTF-8 BOM + a Place ID-keyed dedup)
- **Manual review queue** with per-candidate state (contacted, interested, declined) persisted in SQLite alongside the cache
- **Wire ER's actual 80-airport list** by editing `scripts/build_airports.py`'s `ER_COVERED_HINTS` set and rerunning

## License

Internal to Enhanced Radar.
