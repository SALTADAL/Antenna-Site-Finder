# How to Operate the Antenna Site Finder

A practical, step-by-step guide. Read top to bottom the first time. After that you'll mostly need the "Daily use" section.

## 1. First-time setup (one time, ~10 minutes)

### 1.1 Install Docker Desktop

Download from https://www.docker.com/products/docker-desktop. Open it once after installation so the daemon is running. You should see the whale icon in your menu bar.

To confirm:

```bash
docker --version
docker compose version
```

Both should print a version number.

### 1.2 Clear the stuck git lock

There's a leftover lock file from the build session. Open a terminal at the repo root and run:

```bash
cd "/Users/atlaslad/Documents/Claude/Projects/Enhanced Radar/Antenna_Site_Finder"
rm -f .git/index.lock
git add -A && git commit -m "Stages 2-4 v1"
```

### 1.3 Create your .env file

Copy the template and open it in any text editor:

```bash
cp .env.template .env
open -a TextEdit .env
```

For the first run, leave everything as-is. `APP_MODE=mock` means the app uses local fixture data for KRDU. No API keys needed yet.

When you're ready for live data, edit `.env`:

- `GOOGLE_MAPS_API_KEY=...` (paste your billing-enabled key)
- `ANTHROPIC_API_KEY=...` (paste your Anthropic key)
- `APP_MODE=live`

Save the file. The app re-reads it on next start.

## 2. Starting the app

From the repo root:

```bash
docker compose up
```

What happens:

- Docker builds two containers the first time (~3 to 5 minutes)
- Backend boots on http://localhost:8000
- Frontend boots on http://localhost:5173
- Both stay running until you press Ctrl+C in the terminal

To run in the background instead (so you can close the terminal):

```bash
docker compose up -d
```

To check it's healthy:

```bash
curl http://localhost:8000/healthz
```

You should see `{"status":"ok","mode":"mock"}` or `"mode":"live"`.

## 3. Daily use

### 3.1 Open the UI

Go to http://localhost:5173 in your browser. Bookmark it.

### 3.2 Run a search

1. The left panel has three inputs:
   - **Airport code**: type 4 letters (KRDU, KCLT, KSFO) or 3 letters (RDU, CLT, SFO)
   - **Radius**: slider from 1 to 25 miles. Default is 15.
   - **Include known chains**: checkbox, off by default. Chains usually go nowhere because procurement is at the corporate level, so leave this off unless you specifically need them.
2. Click **Search**.
3. The right side shows the pipeline progress (6 steps). In mock mode this finishes in under a second. In live mode it takes 60 to 180 seconds the first time and under 5 seconds on repeat searches because everything is cached.

### 3.3 Read the results

The results land in the **Table** tab first. Columns:

- **#**: rank by score, 1 is best
- **Score**: 0 to 85, color-coded
  - **Green chip (70+)**: strong candidate, worth a same-day call
  - **Yellow chip (50 to 69)**: solid, verify roof access in person before outreach
  - **Red chip (below 50)**: weak, only chase if higher-tier list runs out
- **Business**: the storefront name from Google Places
- **Dist**: miles to the airport (closer is better)
- **Roof**: flat / mixed / pitched / unknown (color-coded same way)
- **Area**: flat roof area in square feet (more is better)
- **Height**: building height in meters (3-4 stories is the sweet spot, scored highest)
- **Type**: Indie or Chain
- **City**

Click any column header to sort by it. Click again to flip the direction.

### 3.4 Open a candidate

Click any row to open the **candidate card**. It shows:

- The full address and phone number
- Roof type with the source it came from (solar = ground truth, vision = Claude's read of the satellite tile)
- Score breakdown across all 6 factors so you can see *why* the score is what it is
- A field-ops note in plain language ("Strong candidate. Worth a same-day call.")
- Two action buttons:
  - **Call**: opens your phone app via the `tel:` link
  - **Open in Google Maps**: opens the location in Maps so you can see the satellite view and street view yourself

Close the card with the X or by clicking outside it.

### 3.5 Map view

Click the **Map** tab at the top of the results panel. You'll see:

- A blue navy circle with ✈ at the airport
- Up to 50 circle markers (the top 50 candidates), colored by score
- Hover any pin for a quick tooltip (name + score + distance)
- Click a pin to open the same candidate card

The map uses OpenStreetMap tiles (free) so it works without a Google Maps JS key.

### 3.6 Download CSV

In the left panel after a search runs, click **Download CSV**. You get a file named `antenna_candidates_KRDU.csv` (or whatever airport) with all 23 columns. Open it in Excel, Numbers, or Google Sheets.

The CSV is the right format for sharing with the field-ops person doing outreach, importing into a CRM, or appending to a hand-curated tracking sheet.

## 4. Switching from mock mode to live mode

When you have your Google Maps API key with billing enabled:

1. Stop the app: `Ctrl+C` in the terminal (or `docker compose down` if you used `-d`).
2. Edit `.env`:
   - `GOOGLE_MAPS_API_KEY=` paste your key
   - `ANTHROPIC_API_KEY=` paste your Anthropic key
   - `APP_MODE=live`
3. Save the file.
4. Restart: `docker compose up`.
5. Open http://localhost:5173. You should see a green banner: **Live mode ready. All API keys validated.**

If the banner is red, it will tell you exactly which key failed and why. Common causes:

- **HTTP 403 or REQUEST_DENIED**: billing not enabled on the Google Cloud project, or the Places/Solar API isn't turned on for that key. Open https://console.cloud.google.com/apis/library and enable them.
- **HTTP 400 with "API project is not authorized"**: the key has restrictions that block your machine's IP. Either remove the restriction or add your current IP.
- **Anthropic 401**: the key is wrong or revoked. Generate a new one at https://console.anthropic.com/.

The preflight itself costs less than $0.01.

### 4.1 Run your first live search

Type **KRDU** and click Search. This time the pipeline runs against real Google data and takes 60 to 180 seconds.

After it finishes, the left panel shows a **By API** breakdown so you can see exactly what each API leg cost:

```
Places       42 calls   $1.4280
Solar        14 calls   $1.4000
Overpass     14 calls   $0.0000
Static Maps   2 calls   $0.0040
Claude Vision 2 calls   $0.0060
                       --------
                        $2.8380
```

That's an expensive search but a typical one. Repeat searches at the same airport are nearly free because every API call is cached in `backend/data_runtime/cache.db`.

## 5. Stopping the app

If you started with `docker compose up`:

- Press `Ctrl+C` in the terminal where it's running.

If you started with `docker compose up -d`:

```bash
docker compose down
```

Both leave the cache and logs on disk, so the next start picks up where you left off.

## 6. Common operations

### 6.1 Run a search without opening the browser (curl)

```bash
curl -s -X POST http://localhost:8000/search \
  -H 'Content-Type: application/json' \
  -d '{"icao":"KRDU","radius_miles":15,"include_chains":false}' | jq
```

(Install `jq` with `brew install jq` if you don't have it. It just pretty-prints JSON.)

### 6.2 Download a CSV from the command line

```bash
curl -s -X POST http://localhost:8000/export.csv \
  -H 'Content-Type: application/json' \
  -d '{"icao":"KRDU","radius_miles":15,"include_chains":false}' \
  -o krdu_$(date +%Y%m%d).csv
```

Useful if you're scripting a nightly run for a list of airports.

### 6.3 Add a new chain you discovered

Open `backend/scripts/build_chains.py`. Find the closest category and add the brand name to the list. Then:

```bash
docker compose exec backend python scripts/build_chains.py
```

The new chain is live on the next search.

### 6.4 Update the airports list

```bash
docker compose exec backend python scripts/build_airports.py
```

This re-pulls the OurAirports CSV and rebuilds `airports.json`. Run this once a quarter to pick up new commercial airports.

### 6.5 Mark ER-covered airports

Open `backend/scripts/build_airports.py` and edit the `ER_COVERED_HINTS` set. Add or remove ICAO codes. Save and rerun `python scripts/build_airports.py`. The `is_er_covered` flag in the JSON updates accordingly.

### 6.6 Clear the cache

If you want to force the next search to hit live APIs (debugging, or after a long enough gap that data went stale):

```bash
docker compose down
rm -f backend/data_runtime/cache.db*
docker compose up
```

The cache rebuilds on the next search.

## 7. Troubleshooting

### "Backend not reachable" banner

The backend container isn't running. Check:

```bash
docker compose ps
```

If `asf_backend` is missing or has status `Exit`, look at the logs:

```bash
docker compose logs backend | tail -30
```

Usually it's a typo in `.env` or a port collision on 8000.

### Port already in use

Another app is on 8000 or 5173. Either close that app or edit `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"   # change the left side; the right stays
```

Then use `localhost:8001` everywhere.

### Search returns 0 candidates for a non-KRDU airport in mock mode

Expected. Mock mode only has a fixture for KRDU. Either switch to live mode or add `backend/app/fixtures/places/KCLT.json` (and matching solar/overpass/vision fixtures).

### Searches are slow even after caching

The cache hashes by request payload. A single character difference in the airport code (`KRDU` vs `KRDU ` with a trailing space, or `RDU` vs `KRDU`) results in different cache keys. The frontend normalizes uppercase but trailing spaces leak through if you paste from elsewhere. Just retype.

### Costs are higher than expected

Open the **By API** breakdown in the left panel. Solar is the biggest line item per call ($0.10 each). If a search hit Solar for 90 candidates, that's $9. To reduce: tighten the radius, leave chains filtered out (they don't go through Solar), or pre-cache by running once and reusing the result.

### "ANTHROPIC_API_KEY is empty" in preflight

The vision fallback is unavailable. Live searches still work for any candidate Solar covers; the few buildings Solar misses just show `roof_type: unknown` instead of being classified by vision. If that's acceptable, ignore the warning. If not, add the key and restart.

## 8. Where things live on disk

- The repo: `/Users/atlaslad/Documents/Claude/Projects/Enhanced Radar/Antenna_Site_Finder/`
- Your `.env`: same folder, gitignored, never commit it
- The cache: `backend/data_runtime/cache.db` (gitignored)
- Logs: `backend/logs/app.log` (rotated at 5MB, 3 backups)
- Downloaded CSVs: wherever your browser saves files (usually `~/Downloads`)

## 9. Quick reference card

| What you want | How |
|---|---|
| Start the app | `docker compose up` |
| Stop the app | `Ctrl+C` or `docker compose down` |
| Use the UI | http://localhost:5173 |
| Check API health | `curl localhost:8000/healthz` |
| Check API keys | http://localhost:8000/preflight (or use the banner in the UI) |
| Interactive API docs | http://localhost:8000/docs |
| Add a chain | Edit `backend/scripts/build_chains.py`, run `python scripts/build_chains.py` |
| Update airports | Run `python backend/scripts/build_airports.py` |
| Clear cache | `rm -f backend/data_runtime/cache.db*` |
| Switch mock to live | Edit `.env`, set `APP_MODE=live` and paste keys, restart |

## 10. First-time runbook (copy-paste)

```bash
# One time
cd "/Users/atlaslad/Documents/Claude/Projects/Enhanced Radar/Antenna_Site_Finder"
rm -f .git/index.lock
git add -A && git commit -m "v1 ready"
cp .env.template .env

# Every time you want to use the app
docker compose up

# Then open http://localhost:5173 and search KRDU
```
