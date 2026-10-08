# Deploying Catch-a-Scammer on Render

[Render](https://render.com) builds the game from this GitHub repo and runs it with HTTPS and a database. There is no server for you to manage. [`render.yaml`](../render.yaml) in the repo root describes everything (a "Blueprint"), so setup is mostly clicking through.

```
  players ──https──►  Render web service "catch-a-scammer"  ──►  Render Postgres "catch-a-scammer-db"
                      (the Dockerfile: FastAPI + the built game)   (reachable only from the game)
```

On every start, the game applies new database migrations. On the very first start it also builds the shared world.

(Would rather run your own server? See [DEPLOY.md](DEPLOY.md).)

---

## 0. Before you start

- [ ] **Push your work to GitHub.** Render builds whatever is on the branch you choose.
- [ ] **Make sure Render can see the repo.** Render connects to *your* GitHub account. If the repo belongs to a teammate (`savannahdean/catch-a-scammer`), either they connect Render to it, or they make you an admin of the repo, or you fork it to your own account and deploy the fork.
- [ ] **The study is on** (`STUDY_ENABLED=on` in `render.yaml`). Players only take part if they tick the box on the title screen and agree to the consent screen. Upgrade the database before collecting real data (see below). See [STUDY_DATA.md](STUDY_DATA.md).

## 1. Create the Blueprint

1. Sign up at [render.com](https://render.com) with your GitHub account.
2. In the dashboard: **New → Blueprint**. Pick the repository and the **branch** to deploy.
3. Render reads `render.yaml` and lists two resources: the web service **catch-a-scammer** and the database **catch-a-scammer-db**, both on the **Free** plan. Click **Apply** (or **Deploy Blueprint**).

## 2. Watch the first deploy

Open **catch-a-scammer → Logs**:

1. Render builds the Docker image (about 5 minutes the first time).
2. The game starts and applies the migrations, then prints `first start: seeding the world` (about a minute).
3. Then `Uvicorn running`, and the deploy turns **Live**.

Open the address at the top of the service page (`https://catch-a-scammer.onrender.com`, or a similar name if that one was taken). The game should load.

## 3. Use your own domain

1. **catch-a-scammer → Settings → Custom Domains → Add Custom Domain.** Add `yourgame.com`, then also add `www.yourgame.com`.
2. At your domain registrar, in its DNS settings, add:

   | Type | Name | Value |
   |---|---|---|
   | A | `@` | `216.24.57.1` |
   | CNAME | `www` | `catch-a-scammer.onrender.com` (your service's own `onrender.com` address) |

   Remove any `AAAA` records for the domain. **Cloudflare DNS:** use a CNAME for the root (`@` → your `onrender.com` address) instead of the A record, and set both records to **DNS only** (grey cloud).
3. Back in Render, click **Verify**. Once DNS has updated (usually minutes), Render issues the HTTPS certificate on its own.

Render's own guide, if your registrar's screens look different: [Configuring DNS](https://render.com/docs/configure-other-dns).

## 4. Before real players: upgrade the plans

The Free plans are for trying it out:

| | Free plan limit | What to do |
|---|---|---|
| **Database** | **Deleted 30 days after it's created**, with every case and all study data. 1 GB of space (thousands of cases). | Upgrade before day 30, and definitely before turning the study on: **catch-a-scammer-db → Settings → change the instance type**. The cheapest paid database is about $19/month. Paid databases also get automatic backups (the database's **Recovery** page); free ones have none. |
| **Web service** | Sleeps after 15 minutes without visitors, and the next visitor waits about a minute. No Shell. | Fine for a class demo. For an always-on site, upgrade **catch-a-scammer** to the smallest paid instance (about $7/month). |

Prices change, so check [render.com/pricing](https://render.com/pricing).

## 5. Updating the site

Push to the branch Render deploys, and Render rebuilds and redeploys automatically. New migrations apply by themselves when the new version starts. Cases and study data are kept.

## Settings

Change them in **catch-a-scammer → Environment**, then **Save, rebuild, and deploy**:

| Setting | What it does |
|---|---|
| `STUDY_ENABLED` | `on` offers the research study on the title screen; `off` hides it and refuses new participants and answers (existing participants can always withdraw). |
| `RATE_NEW_CASE`, `RATE_MESSAGE`, `RATE_JOIN_STUDY`, `RATE_ANSWERS` | Limits per player IP, as `count/seconds`. |
| `LEGACY_API`, `API_DOCS` | Keep these `off` on a public site. |
| `WORLD_SEED` | Which shared world is generated on the very first start. |

`DATABASE_URL` is filled in by Render from the database. Leave it alone.

## Getting the study data

The export runs on **your PC** and connects to the Render database over the internet. The database only accepts connections from the game (`ipAllowList: []` in `render.yaml`), so let yourself in for the export:

1. **catch-a-scammer-db → Networking** (or **Access Control**): add your current IP address.
2. **catch-a-scammer-db → Connect → External Database URL**: copy it.
3. In PowerShell:

   ```powershell
   cd backend
   $env:DATABASE_URL = "<paste the External Database URL>"
   .venv\Scripts\python scripts\export_study.py
   Remove-Item Env:DATABASE_URL
   ```

   The CSVs and a `.zip` land in `backend/exports/` (git ignores that folder).
4. Remove your IP from the database's allow list again.

What each file contains: [STUDY_DATA.md](STUDY_DATA.md).

## Troubleshooting

| Problem | Likely cause |
|---|---|
| The first deploy fails at the health check | The first start builds the world before the game listens. Open the log; if it was still seeding, click **Manual Deploy → Deploy latest commit**. The second start skips seeding. |
| The site takes a minute to load | The free web service was asleep. Upgrade it (step 4) to keep it awake. |
| "unknown case" | That browser's case belongs to an older database (before case keys, or a deleted free database). Start a new case. |
| The export says "connection refused" or times out | Your IP isn't on the database's allow list, or your IP changed. Add it again. |
| Custom domain stuck on "Verifying" | DNS hasn't updated yet, an old `AAAA` record is still there, or Cloudflare's proxy (orange cloud) is on. |
