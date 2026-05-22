# Deploying Antenna Site Finder

This guide walks through deploying the app to two free-tier services:

| Piece | Where | Why |
|---|---|---|
| Frontend (React + Vite) | **Netlify** | Free, instant deploys from GitHub, perfect for static SPAs |
| Backend (FastAPI Python) | **Render** | Free Python hosting with Docker support, persistent disk for SQLite |

Why split: Netlify is built for static sites and short-running serverless functions (10-second timeout). Our search pipeline takes 30 to 180 seconds in live mode, so the backend needs a real long-running server.

**Total monthly cost: $0** for the free tier. Upgrade to Render Starter ($7/mo) only if you want the backend to stay awake instead of sleeping after 15 minutes of inactivity.

---

## Prerequisites (15 minutes)

You'll need accounts at three services. All have free tiers and use Google or email signup.

1. **GitHub** at https://github.com — to host the code
2. **Netlify** at https://app.netlify.com — to host the frontend
3. **Render** at https://render.com — to host the backend

You also need the two API keys from `API_KEYS_SETUP.md`:

- `GOOGLE_MAPS_API_KEY` (with billing enabled, Places + Solar + Static Maps enabled)
- `ANTHROPIC_API_KEY`

---

## Step 1: Push the code to GitHub (5 minutes)

If you haven't already pushed this repo to GitHub, do it now. Render and Netlify both deploy by pulling from a GitHub repo.

```bash
cd "/Users/atlaslad/Documents/Claude/Projects/Enhanced Radar/Antenna_Site_Finder"

# Make sure the git lock from earlier is gone
rm -f .git/index.lock

# Stage everything and commit. Skip if you've been committing all along.
git add -A
git commit -m "Prep for first deployment"
```

Now create a new empty repo on GitHub:

1. Go to https://github.com/new
2. Repository name: `antenna-site-finder` (or whatever you like)
3. Set it to **Private** (this is internal field-ops tooling)
4. Do NOT initialize with a README, .gitignore, or license. We have those.
5. Click "Create repository"

GitHub will show you a page with commands. Use the "push an existing repository" block. It'll look like:

```bash
git remote add origin https://github.com/<your-username>/antenna-site-finder.git
git branch -M main
git push -u origin main
```

Paste those into your terminal and run them. You'll be prompted for your GitHub credentials (use a personal access token, not your password — generate one at https://github.com/settings/tokens with `repo` scope).

After the push completes, refresh the GitHub repo page. You should see all the files.

---

## Step 2: Deploy the backend to Render (10 minutes)

Render reads the `render.yaml` file at the repo root and figures out what to build.

1. Go to https://dashboard.render.com
2. Click **New** at the top right, then choose **Blueprint**
3. Click **Connect a repository** if this is your first time. Authorize Render to read your GitHub repos.
4. Select your `antenna-site-finder` repo
5. Render will detect `render.yaml` and show a preview: one web service called `asf-backend` plus a 1 GB persistent disk
6. Click **Apply** at the bottom

Render starts building. The Docker build takes about 3 to 5 minutes the first time (pip install, layer caching kicks in for future deploys).

**While it's building, set your API keys.** Render won't let the service serve traffic without them.

1. In the Render dashboard, click into the `asf-backend` service
2. Go to **Environment** in the left sidebar
3. Find each of these variables and click the **eye/edit icon** to fill in the value:

| Key | Value |
|---|---|
| `GOOGLE_MAPS_API_KEY` | paste your Google key |
| `ANTHROPIC_API_KEY` | paste your Anthropic key |
| `FRONTEND_ORIGIN` | leave empty for now; we fill this in after Netlify gives us a URL |

Click **Save Changes**. Render redeploys automatically (about 2 minutes).

**Verify the backend is live.** Once Render shows a green "Live" badge:

1. Click the service URL near the top (looks like `https://asf-backend-XXXX.onrender.com`)
2. Visit `<that URL>/healthz`. You should see `{"status":"ok","mode":"live"}`
3. Visit `<that URL>/preflight`. You should see all checks passing (overall_ok: true)

**Important: copy that Render URL.** You need it for the next step.

If preflight fails, the response tells you which key broke. Common fixes are in the `API_KEYS_SETUP.md` troubleshooting table.

---

## Step 3: Deploy the frontend to Netlify (5 minutes)

1. Go to https://app.netlify.com
2. Click **Add new site** then **Import an existing project**
3. Choose **GitHub** as the provider
4. Authorize Netlify to read your repos if it's your first time
5. Select your `antenna-site-finder` repo

Netlify reads the `netlify.toml` we shipped and pre-fills the build settings:

- **Base directory**: `frontend`
- **Build command**: `npm install && npm run build`
- **Publish directory**: `frontend/dist`

You don't need to change these.

**Before clicking deploy**, scroll down and click **Show advanced** → **Add environment variable**. Add one variable:

| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | the Render URL you copied, e.g. `https://asf-backend-XXXX.onrender.com` |

This tells the frontend where to find the backend. **No trailing slash.**

Now click **Deploy site**. Netlify builds the frontend in about 90 seconds.

When it finishes, Netlify gives you a URL like `https://random-name-12345.netlify.app`. Copy it. You can rename it to something nicer under **Site configuration → Change site name**.

---

## Step 4: Wire CORS so frontend can talk to backend (2 minutes)

The backend currently rejects requests from any origin except localhost. We need to tell it the Netlify URL is allowed.

1. Go back to Render → `asf-backend` service → **Environment**
2. Edit the `FRONTEND_ORIGIN` variable
3. Paste your Netlify URL (the full thing with `https://`, no trailing slash)
4. Click **Save Changes**

Render redeploys (2 minutes). When the green Live badge is back, you're done with deployment.

---

## Step 5: First search on the deployed app (1 minute)

1. Open your Netlify URL in a browser
2. You should see the dark/yellow UI
3. The preflight banner at the top should be green: "Live mode ready"
4. Type **KRDU** in the airport box
5. Click **Search**

The first search will take a bit longer than usual because:

- The backend wakes up from sleep (Render free tier sleeps after 15 min)
- Render's free tier has slower CPU than your laptop

Subsequent searches at the same airport are near-instant from the cache.

**The deploy is done.** Bookmark your Netlify URL. Share the link with your team.

---

## Auto-deploy from now on

Both Render and Netlify watch your GitHub repo. Every time you push to `main`, both rebuild automatically:

```bash
# Make some change
git add -A && git commit -m "Add KCLT fixture"
git push
```

Render redeploys the backend (~3 min). Netlify redeploys the frontend (~90s). No further action needed.

---

## Common issues and fixes

### "CORS error" in the browser console

The backend's `FRONTEND_ORIGIN` env var doesn't match the URL you're visiting. Double-check it includes the `https://` and has no trailing slash. After fixing, Render redeploys automatically.

### Backend wakes up slow on the first request

Render's free tier sleeps after 15 minutes idle. First request after sleep takes 30-60 seconds while the container boots. Either accept this for an internal tool or upgrade to Render Starter ($7/mo) for always-on.

### Preflight shows "ANTHROPIC_API_KEY is empty" or similar

The env var is missing in Render's Environment tab. Fill it in, save, wait for the redeploy.

### Search hangs at "Running pipeline" forever

Look at the Render logs (service dashboard → Logs tab). You'll see per-stage timing once a search completes:

```
[a1b2c3] DONE total=45.2s (nearby=4.1 chain=0.01 details=3.2 solar+overpass=28.4 vision=8.4 score=0.05)
```

If Solar+Overpass is over 60 seconds, your Google Maps quota might be throttled or Overpass is being rate-limited from Render's IP. Both should resolve themselves within a few minutes.

### "Build failed" on Netlify

Check the deploy log under Netlify's **Deploys** tab. Most common cause: a TypeScript or ESLint error introduced in your last commit. Fix locally, push again.

### "Build failed" on Render

Check the build log under **Logs**. Most common cause: a missing Python dependency in `requirements.txt`. Add it, commit, push.

### SQLite cache disappeared

If you didn't set up the persistent disk in Render (the `render.yaml` does this automatically, but if you set up the service manually you might have skipped it), the cache resets on every deploy. To check: in Render's service dashboard, look for a "Disks" section in the left sidebar. There should be one disk called `asf-data` mounted at `/var/data`. If not, add it: 1 GB at `/var/data`.

---

## Optional: custom domain on Netlify

Netlify gives you a custom subdomain for free. To use a domain you own:

1. Netlify dashboard → your site → **Domain management**
2. Click **Add custom domain**
3. Type your domain (e.g., `radar.yourcompany.com`)
4. Netlify shows you which DNS records to create at your registrar (CNAME or A record)
5. After DNS propagates (5 min to 24 hours), Netlify provisions a Let's Encrypt cert automatically

Then update Render's `FRONTEND_ORIGIN` env var to the new domain.

---

## Optional: protect the app behind a password

The free Netlify tier doesn't include password protection. Two options:

- **Netlify Pro** ($19/mo per site) gives you basic auth and per-role access
- **Free workaround**: put Cloudflare Access in front of your Netlify URL (free for up to 50 users, supports Google Workspace SSO)

---

## What lives where after deploy

| Thing | Location | Persistent? |
|---|---|---|
| Frontend bundle | Netlify CDN | Yes |
| Backend container | Render | Yes (rebuilt on push) |
| SQLite cache + outreach state | Render persistent disk at `/var/data` | Yes |
| API keys | Render env vars | Yes |
| Local cache from your laptop | not deployed | No (separate from production cache) |

Production cache starts empty on first deploy. Your first few KRDU searches in production will be full-price ($5 to $15 each); after that the cache kicks in and they're nearly free.

---

## Tearing it down

If you ever want to nuke the deployment:

- **Render**: Dashboard → service → Settings → Delete Service. Confirms a few times.
- **Netlify**: Dashboard → site → Site configuration → Delete this site.

Neither charges anything for deletion. Your GitHub repo stays intact.
