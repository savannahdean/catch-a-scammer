# Deploying Catch-a-Scammer to a website

**Using Render instead?** Follow [DEPLOY_RENDER.md](DEPLOY_RENDER.md). This page is for running your own server.

This puts the game on your own domain with HTTPS, on one small Linux server.
Three containers run on that server:

```
  players ──https──►  Caddy  ──►  app (FastAPI + the built game)  ──►  db (Postgres)
                     ports 80/443     not reachable from outside       only on the server's 127.0.0.1
```

- **Caddy** gets and renews the HTTPS certificate by itself.
- **app** is built from the `Dockerfile` in the repo root. On every start it applies new database migrations. On the very first start it also builds the shared world.
- **db** keeps its data in a Docker volume, which survives restarts and updates.

The files are in [`deploy/`](../deploy): `compose.yml`, `Caddyfile`, `.env.example`, `entrypoint.sh` and `backup.sh`.

The whole setup costs about $5–7 a month for the server, plus $10–15 a year for the domain.

---

## 0. Before you start

- [ ] **Commit and push your work to GitHub.** The server gets the code with `git clone`, so it only gets what's on GitHub.
- [ ] **Decide about the study.** Collecting survey answers from the public is research on people. Ask your professor whether you need IRB/ethics approval first. Until then, leave `STUDY_ENABLED=off`: the game works the same, it just doesn't offer the study. See [STUDY_DATA.md](STUDY_DATA.md).

## 1. Buy a domain

Any registrar works: Cloudflare Registrar, Porkbun or Namecheap are cheap and simple. You only need its **DNS settings page** later.

## 2. Rent a server

Any VPS provider works (Hetzner, DigitalOcean, Linode, Vultr). Choose:

- **Ubuntu 24.04**, **2 GB RAM**, 1–2 CPUs (the smallest plan with 2 GB is enough)
- **SSH key** login. The provider shows how to add yours. On Windows, run `ssh-keygen` in PowerShell and paste the contents of `C:\Users\<you>\.ssh\id_ed25519.pub`.

Write down the server's **IPv4 address**.

## 3. Point the domain at the server

In the registrar's DNS settings, add two records:

| Type | Name | Value |
|---|---|---|
| A | `@` | your server's IP |
| A | `www` | your server's IP |

(If the server also has an IPv6 address, add matching `AAAA` records.) Changes usually show up within minutes. Check with `nslookup yourgame.com`: it should print the server's IP.

**If you use Cloudflare DNS**, set both records to **DNS only** (grey cloud) at first, so Caddy can get its certificate.

## 4. Set up the server

Connect from PowerShell (`ssh root@<server-ip>`), then:

```bash
# updates, and a firewall that only lets SSH and the website in
apt update && apt upgrade -y
ufw allow OpenSSH && ufw allow 80 && ufw allow 443/tcp && ufw allow 443/udp
ufw --force enable

# Docker (the official install script)
curl -fsSL https://get.docker.com | sh
```

## 5. Get the code and configure it

```bash
git clone https://github.com/savannahdean/catch-a-scammer.git /opt/catch-a-scammer
cd /opt/catch-a-scammer/deploy
cp .env.example .env
openssl rand -hex 24        # copy this: it's your database password
nano .env                   # set DOMAIN, DB_PASSWORD, STUDY_ENABLED; Ctrl+O, Enter, Ctrl+X to save
```

If the repository is **private**, `git clone` asks for a username and password. Use your GitHub username and a **personal access token** (GitHub → Settings → Developer settings → Fine-grained tokens, with read access to this repo) as the password.

`.env` never leaves the server and is never committed.

## 6. Start it

```bash
docker compose up -d --build
docker compose logs -f app      # watch the first start; Ctrl+C stops watching (not the server)
```

The first build takes a few minutes. On the first start you will see the migrations, then `first start: seeding the world`, then `Uvicorn running`. Open **https://yourgame.com**.

## 7. Back up the database every night

```bash
cd /opt/catch-a-scammer/deploy
chmod +x backup.sh
./backup.sh                      # try it once: writes backups/cas-<date>.dump
crontab -e                       # add this line, then save:
0 3 * * *  cd /opt/catch-a-scammer/deploy && ./backup.sh >> backups/backup.log 2>&1
```

It keeps the newest 14. A backup on the same server doesn't help if the server dies, so download one now and then from your own PC:

```powershell
scp root@<server-ip>:/opt/catch-a-scammer/deploy/backups/cas-*.dump .
```

To restore one: `docker compose exec -T db pg_restore -U cas -d osint --clean --if-exists < backups/<file>.dump`

## 8. Update the site

After you push changes to GitHub:

```bash
cd /opt/catch-a-scammer && git pull
cd deploy && docker compose up -d --build
```

New migrations apply by themselves when the app restarts. Players' cases and study data are kept.

---

## Everyday commands

Run these in `/opt/catch-a-scammer/deploy`.

| To | Run |
|---|---|
| See what's running | `docker compose ps` |
| Read the game server's log | `docker compose logs -f app` |
| Restart the game | `docker compose restart app` |
| Stop everything | `docker compose down` (data is kept) |
| Open a SQL prompt | `docker compose exec db psql -U cas osint` |
| Export the study data | see [STUDY_DATA.md](STUDY_DATA.md) |

Never run `docker compose down -v`: the `-v` deletes the database.

## Settings (`deploy/.env`)

| Setting | What it does |
|---|---|
| `DOMAIN` | The site's address, without `https://`. |
| `DB_PASSWORD` | The database password. |
| `STUDY_ENABLED` | `on` offers the research study on the title screen; `off` hides it and refuses new participants and answers. Existing participants can always withdraw. |
| `WORLD_SEED` | Which shared world is generated on the first start. |
| `RATE_NEW_CASE`, `RATE_MESSAGE`, `RATE_JOIN_STUDY`, `RATE_ANSWERS` | Limits per player IP, as `count/seconds`. A player over the limit sees "Too many requests. Try again in N seconds." |

After changing `.env`: `docker compose up -d`.

## What protects the public site

- **Case keys.** Only the browser that started a case can open it. Guessing another case's number gets "unknown case".
- **Rate limits** on new cases, client messages, and joining or answering the study.
- **The old UUID API is off** (`LEGACY_API=off`), because it skips case keys. The API docs page is off too (`API_DOCS=off`).
- **The database can't be reached from the internet.** It only listens on the server's own `127.0.0.1`.
- **HTTPS everywhere**, with security headers set in the `Caddyfile`.

The code for the first three is in `backend/server/guard.py`.

## Troubleshooting

| Problem | Likely cause |
|---|---|
| The browser says the site isn't secure / no certificate | DNS doesn't point at the server yet, or ports 80/443 are blocked. `docker compose logs caddy` says why. |
| `502 Bad Gateway` | The game is still starting (first start seeds the world). Wait a minute and check `docker compose logs app`. |
| "unknown case" after an update | That browser's case was started before case keys existed. Start a new case. |
| The build stops with "Killed" | The server ran out of memory while building. Use a 2 GB server, or add swap: `fallocate -l 2G /swapfile && chmod 600 /swapfile && mkswap /swapfile && swapon /swapfile`. |

## Trying the production setup on your own PC

With Docker Desktop running, you can run the exact production stack locally (it won't touch your dev database):

```powershell
cd deploy
# a throwaway env file: DOMAIN=localhost, any DB_PASSWORD, HTTP_PORT=8080, HTTPS_PORT=8443, DB_LOCAL_PORT=5439
docker compose -p cas-local --env-file local.env up -d --build
```

Then open https://localhost:8443 and accept the browser's warning about the local certificate. Remove it all with `docker compose -p cas-local --env-file local.env down -v`.
