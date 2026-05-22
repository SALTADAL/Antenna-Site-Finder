# Getting Your API Keys

You need two keys for live mode. Both take about 10 minutes each to set up. Mock mode needs neither.

| Key | Used for | Approximate cost |
|---|---|---|
| Google Maps Platform | Places search, Solar API, satellite tiles | $5 to $15 per first-time airport search |
| Anthropic | Claude vision fallback when Solar has no data | Pennies per search |

Both are pay-as-you-go. Neither charges you anything until the app actually makes a call. You can cap spending on both, instructions below.

---

## Part 1: Google Maps Platform key

### Step 1. Create a Google Cloud account

Open https://console.cloud.google.com in your browser.

If this is your first time, sign in with any Google account (your personal Gmail is fine for an internal tool). Accept the Terms of Service. Google asks for a country and a phone number for verification.

### Step 2. Create a new project

At the very top of the page, next to the "Google Cloud" logo, you'll see a dropdown that says "Select a project" (or shows an existing project name).

1. Click that dropdown.
2. A modal opens. Click **New Project** in the top right.
3. Name it `antenna-site-finder` (or anything you like).
4. Click **Create**.
5. Wait 10 to 20 seconds. The dropdown will switch to the new project automatically.

### Step 3. Enable billing

This is the step beginners get stuck on. Google won't let any "paid" API serve requests until billing is attached, even if the call would have been free under the monthly credit.

1. In the left sidebar, click the hamburger menu (three lines top left), then **Billing**.
2. If you see "This project has no billing account," click **Link a billing account**.
3. Click **Create billing account**.
4. Fill in your name, address, and a credit card. Google verifies the card with a $1 hold that drops off in a few days.
5. Once created, link it to the `antenna-site-finder` project.

Tip: set a **budget alert** so you never get a surprise bill.

1. In Billing, click **Budgets & alerts** on the left.
2. Click **Create Budget**.
3. Name it "Monthly cap."
4. Set the amount to whatever you're comfortable with ($50/month is plenty for this app unless you're searching hundreds of airports).
5. Set alerts at 50%, 90%, and 100%. Google emails you when each threshold hits. It does NOT auto-stop spending, but you'll know.

### Step 4. Enable the three APIs

Go to https://console.cloud.google.com/apis/library

You'll search for and enable three APIs. For each one:

1. Type the name in the search bar.
2. Click the matching tile.
3. Click the blue **Enable** button.
4. Wait a few seconds for it to confirm "API enabled."
5. Click the back arrow and search the next one.

The three APIs:

1. **Places API** (the legacy one, not "Places API (New)")
2. **Solar API**
3. **Maps Static API**

After all three are enabled, you can confirm by going to https://console.cloud.google.com/apis/dashboard. You should see all three listed.

### Step 5. Create the API key

Go to https://console.cloud.google.com/apis/credentials

1. Click **+ Create Credentials** at the top.
2. Choose **API key** from the dropdown.
3. A popup shows your new key, something like `AIzaSyD-...`.
4. Click **Copy** and paste it somewhere safe for a moment (a sticky note app is fine, just don't email it).
5. Click **Close**.

### Step 6. Restrict the key (do this, don't skip it)

An unrestricted key on the public internet is a free shopping spree for anyone who finds it. Restrictions are the safety net.

In the credentials page, click the pencil icon next to your new key.

**Application restrictions** (top section):

- For local testing on your laptop: choose **None** for now. The key sits in your gitignored `.env` and never goes anywhere.
- For a more careful setup: choose **IP addresses** and add your current public IP (Google shows your IP if you click the help icon).

**API restrictions** (bottom section):

- Click **Restrict key**.
- Check the boxes for exactly three APIs:
  - Places API
  - Solar API
  - Maps Static API
- Click **Save** at the bottom.

This means even if the key leaks, an attacker can only use it for these three APIs, not for the 200+ other Google services.

### Step 7. Paste it into .env

Open `.env` in the repo:

```bash
cd "/Users/atlaslad/Documents/Claude/Projects/Enhanced Radar/Antenna_Site_Finder"
open -a TextEdit .env
```

Find the line:

```
GOOGLE_MAPS_API_KEY=
```

Paste your key after the equals sign, no quotes, no spaces:

```
GOOGLE_MAPS_API_KEY=AIzaSyD-yourActualKeyHere
```

Save the file.

---

## Part 2: Anthropic API key

### Step 1. Create an Anthropic account

Open https://console.anthropic.com in your browser.

Sign up with email or Google. Verify your email.

### Step 2. Add billing

Anthropic also wants billing on file before any call goes through. The free trial credits won't cover production use of vision, so you'll want a real card attached.

1. In the left sidebar, click **Plans & Billing** (or **Settings → Plans**).
2. Click **Add payment method**.
3. Enter card info.

Set a usage cap:

1. Same page, find **Spend limit**.
2. Set it to something safe like $50/month. Anthropic will hard-stop calls if you hit the cap.

### Step 3. Create the API key

1. In the left sidebar, click **API Keys**.
2. Click **Create Key**.
3. Give it a name like `antenna-site-finder`.
4. Click **Create Key**.
5. A modal shows your key, something like `sk-ant-api03-...`. This is the **only time** Anthropic shows it. Copy it now.
6. Click **Close**.

If you lose it, no panic, just generate a new one and delete the old one.

### Step 4. Paste it into .env

In the same `.env` file:

```
ANTHROPIC_API_KEY=sk-ant-api03-yourActualKeyHere
```

Save.

---

## Part 3: Flip the switch

In the same `.env` file, change:

```
APP_MODE=mock
```

to

```
APP_MODE=live
```

Save the file.

## Part 4: Verify everything works

From the repo root:

```bash
docker compose down
docker compose up
```

(The `down` first kicks the containers so they re-read `.env`.)

Open http://localhost:5173 in your browser.

You should see a green banner at the top: **Live mode ready. All API keys validated.**

If you see a red banner instead, it tells you which key failed. Common fixes:

| Banner says | What to do |
|---|---|
| "GOOGLE_MAPS_API_KEY is empty" | The key in `.env` is blank or has a typo. Re-paste from the source. |
| "Places returned status=REQUEST_DENIED" | Either billing isn't attached to the project, or you haven't enabled the Places API. Go back to Step 3 and 4 of Part 1. |
| "Places returned status=OVER_QUERY_LIMIT" | You've hit the API quota for the day. Wait 24 hours or request a quota increase in the Google Cloud console. |
| "HTTP 403" | Key restrictions are too tight. Either widen the IP allowlist or set Application restrictions to None temporarily. |
| "ANTHROPIC_API_KEY is empty" | Same as above for the Anthropic line in `.env`. |
| "Anthropic 401" | The key was revoked or copy-pasted wrong. Generate a new one. |

The preflight check itself costs less than $0.01. If it succeeds, you're cleared for real searches.

---

## Part 5: Doing a real live search (and what it costs)

Type **KRDU** in the airport box, leave the radius at 15, click **Search**.

This time the pipeline runs against real Google data. It takes 60 to 180 seconds the first time. While it runs, the left panel shows the pipeline progress. After it finishes, the left panel shows a cost breakdown:

```
Places         42 calls   $1.4280
Solar          14 calls   $1.4000
Overpass       14 calls   $0.0000
Static Maps     2 calls   $0.0040
Claude Vision   2 calls   $0.0060
                          --------
                          $2.8380
```

Roughly $3 for a real KRDU search. The second time you search KRDU, it's nearly free because every API response is cached locally in SQLite.

The single biggest line item is Solar at $0.10 per candidate. If a search returns 90 candidates, that's $9 just for Solar. To reduce:

- Tighten the radius (10 miles instead of 15)
- Leave the "Include known chains" box unchecked (chains don't run through Solar)
- Run a search once and reuse the cached result

---

## Cheat sheet: every URL you'll need

| What | URL |
|---|---|
| Google Cloud Console (home) | https://console.cloud.google.com |
| Enable APIs | https://console.cloud.google.com/apis/library |
| API credentials | https://console.cloud.google.com/apis/credentials |
| Billing | https://console.cloud.google.com/billing |
| Quota usage | https://console.cloud.google.com/apis/dashboard |
| Anthropic Console | https://console.anthropic.com |
| Anthropic API Keys | https://console.anthropic.com/settings/keys |
| Anthropic Billing | https://console.anthropic.com/settings/plans |

## What to do if you ever leak a key

Don't panic. The key only works for what you authorized.

1. Google: go to https://console.cloud.google.com/apis/credentials, click your key, click **Delete**. Create a new one. Paste it into `.env`.
2. Anthropic: go to https://console.anthropic.com/settings/keys, click the three dots next to your key, click **Delete**. Create a new one. Paste it into `.env`.
3. Restart the app: `docker compose down && docker compose up`.

Total recovery time: 2 minutes.
