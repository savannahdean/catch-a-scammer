# File Dictionary

What every file in the repository does, why it exists, what's inside it, what calls it, and what to be careful of when you change it. Files are grouped by folder in the order data flows: **database → server → client → tooling → docs**.

Generated folders are not described file by file: `frontend/node_modules/` (npm packages), `frontend/dist/` (a production build), `backend/.venv/` (the Python virtual environment) and `__pycache__/`. All of them are recreated by the setup steps and are ignored by git.

**Jump to:** [How the pieces fit](#how-the-pieces-fit) · [Repository root](#repository-root) · [.vscode/](#vscode) · [docs/](#docs) · [deploy/](#deploy-the-public-website) · [backend/ (top level)](#backend-top-level) · [backend/database/](#backenddatabase-the-database-schema) · [backend/server/](#backendserver-the-api) · [backend/server/generator/](#backendservergenerator-the-case-generator) · [backend/scripts/](#backendscripts) · [frontend/ (top level)](#frontend-top-level) · [frontend/src/](#frontendsrc-the-react-client)

---

## How the pieces fit

```
Player's browser
  └─ frontend/src  (React)                       ── fetch('/api/...') ──┐
       App.tsx → screens (title, consent, surveys) → os/Desktop         │
       Desktop → windows → apps/* → records/RecordView                  │
       state/session.tsx is the only place that calls api/client.ts     │
                                                                         ▼
backend/server  (FastAPI, uvicorn on :8000)
  app.py         mounts the routers below, serves frontend/dist when it exists
  compat.py      /api/... : cases, exhibits, every tool, evidence, report, graph
  cards.py       turns one database entity into one "card" the client draws
  messenger.py   /api/.../messenger : the client chat engine and personalities
  study.py       /api/study/... : consent, surveys, withdrawal
  scoring.py     grades a Case Report
  generator/     builds a new case into the database when one is requested
                                                                         │ SQL (psycopg)
                                                                         ▼
PostgreSQL 16 in Docker (backend/docker-compose.yml)
  schema + SQL functions from backend/database/migrations/*.sql
```

The client holds **no answers**. Everything it shows comes from the server, and everything the player does goes back to the server, which records it for research.

---

## Repository root

### `README.md`
The front door for the team: what the game is, what to download (Git, VS Code, Python, Node.js, Docker Desktop), first-time setup (VS Code task or PowerShell), how to run and debug in VS Code, a short how-to-play, a table of **how to edit** common things, the research tables with example SQL, the repository layout and troubleshooting. Keep it in sync when you add a task, change a port or add a top-level folder.

### `Dockerfile`
Builds the **production image** in two stages: `node:22-slim` runs `npm ci` and `npm run build` for the React client, then `python:3.13-slim` installs `server/requirements.txt`, copies `backend/`, puts the built client in `/app/frontend/dist` (where `server/app.py` looks for it) and runs `deploy/entrypoint.sh` as an unprivileged user. Used by `deploy/compose.yml`.

### `render.yaml`
The **Render Blueprint**: a Docker web service `catch-a-scammer` (built from the `Dockerfile`, health check `/health`, `DATABASE_URL` wired from the database, the study off, `LEGACY_API` and `API_DOCS` off, the rate limits) and a Postgres 16 database `catch-a-scammer-db` (`osint`/`cas`, reachable only from the game: `ipAllowList: []`). Both start on Render's free plans; the free database is deleted after 30 days. Walkthrough: `docs/DEPLOY_RENDER.md`.

### `.dockerignore`
Keeps `node_modules`, builds, the virtualenv, `.env` files, exports, backups, `.git` and `docs/` out of the image.

### `.gitattributes`
Forces LF line endings for `*.sh` and the `Caddyfile`, which run on Linux; a Windows checkout would otherwise give them CRLF and break them.

---

## .vscode/

### `.vscode/tasks.json`
Defines the **Tasks: Run Task** entries, so nobody has to remember commands:
- *Setup: 1/2/3* create `backend/.venv` and install `server/requirements.txt`, copy `.env.example` to `.env`, and run `npm install` in `frontend/`. *Setup: everything (first time)* runs them in order, then starts the database, migrates and seeds.
- *DB: start/stop Postgres*, *DB: apply migrations*, *DB: seed the world*.
- *API: run server* (uvicorn on :8000) and *Client: run dev server* (Vite on :5173) are **background** tasks: their problem matchers wait for "Application startup complete" / "ready in" so a task that depends on them knows when they're up.
- *Run game (database + API + client)* chains the three.
- *Client: build for production* and *Test: playtest every scenario*.

Python tasks use `backend/.venv/bin/python`, with a `windows` override for `backend\.venv\Scripts\python.exe`. Tasks are `process` or `npm` type rather than shell commands, so they behave the same in PowerShell, cmd and bash.

### `.vscode/launch.json`
Run and Debug configurations: **API: debug the FastAPI server** (debugpy running uvicorn in `backend/`), **Client: open the game in Edge/Chrome** (starts the dev server first, maps breakpoints to `frontend/`), **Test: debug the playtest**, and a compound that starts the API debugger and the browser together.

### `.vscode/extensions.json`
Extensions VS Code offers when the folder opens: Python, Pylance, Python Debugger, Docker, SQLTools and its PostgreSQL driver.

### `.vscode/settings.json`
Workspace settings: the Python interpreter (`backend\.venv\Scripts\python.exe`; macOS/Linux users change it to `bin/python`), `backend/` added to Pylance's import path so `server.*` imports resolve, `__pycache__`/`node_modules` hidden from the explorer, tasks run in `cmd.exe` (`terminal.integrated.automationProfile.windows`, because an MSYS2 or Git Bash login shell drops the Windows PATH and can't find `npm`), and a ready-made **SQLTools connection** to the Docker database (`cas`/`cas` @ `localhost:5432/osint`).

---

## docs/

### `docs/GAME_WIKI.md`
The game wiki and **answer key** (spoilers). It explains how a case works, every tool, the client Messenger (intents, the four disclosure rules, all nine personalities with their numbers, the mood meter), the difficulty knobs, scoring, a player-facing overview of each scam type, a full walkthrough of every scenario (fields, the path to each answer, the client's secret, what proves it, the traps), how unmasking the real person works on HARD/EXPERT, and the traps shared by every case. Update it whenever a scenario, personality or scoring rule changes.

### `docs/FILE_DICTIONARY.md`
This file.

### `docs/DEPLOY_RENDER.md`
Deploying on Render: making sure Render can see the repo, creating the Blueprint, the first deploy, a custom domain (DNS records), what the free plans can't do and when to upgrade, automatic updates on push, settings, exporting the study data from your PC (allow-listing your IP), and troubleshooting.

### `docs/DEPLOY.md`
Step by step from nothing to the game on your own domain with HTTPS: buying a domain, renting an Ubuntu server, DNS records, firewall, installing Docker, cloning, `deploy/.env`, the first start, nightly backups and downloading them, updating, everyday commands, every setting, what protects the public site, troubleshooting, and running the production stack locally.

### `docs/STUDY_DATA.md`
The research study for whoever analyses it: what is and isn't recorded, what withdrawal deletes, the ethics-approval and consent-text checklist, turning the study on and off, **exporting the data to CSV and downloading it**, what each CSV contains, live SQL through an SSH tunnel with example queries, and looking after the data.

---

## backend/ (top level)

### `backend/.env.example`
The template for `backend/.env`: `DATABASE_URL=postgresql://cas:cas@localhost:5432/osint` (the Docker database), `API_PORT`, `WORLD_SEED` (the random seed for the world) and `DB_POOL_MAX` (connection pool size). Copied to `.env` by setup.

### `backend/.env` *(not in git)*
Your local copy of the above. `server/env.py` reads it automatically, so the server, migrations, world seed and tests find the database without exporting anything. Ignored by `backend/.gitignore` because it can hold a password.

### `backend/.gitignore`
Keeps `.env`, `.venv/`, `build/`, `__pycache__/` and the optional Kaggle CSV (`data/*.csv`) out of git.

### `backend/docker-compose.yml`
One service, `db`: the official `postgres:16` image with user/password `cas`/`cas`, database `osint`, port 5432 published on localhost, a named volume `cas_pgdata` so data survives restarts, and a `pg_isready` health check (which `docker compose up --wait` waits for). Only the database runs in Docker; the API and client run on your machine so you can edit them freely.

### `backend/Makefile`
Shortcuts for macOS/Linux/WSL (Windows users use the VS Code tasks instead): `setup` (venv, `.env`, `npm install`), `db-up`/`db-down`, `db-migrate`, `db-seed`, `db-reset` (drops everything via `database/reset.sql`, then migrates and seeds), `server`, `web` (client dev server), `web-build`, `test` (starts a temporary API, runs the playtest, stops it), `scenarios` (lists the catalog), `psql`. `-include .env` + `export` pass `.env` to every command.

### `backend/README.md`
Backend deep-dive: the architecture, the 12 scenarios and the twist each one tests, the full table of `/api` routes per client window (tools, Messenger, study), the realism layers (time-bounded DNS, CDN fronting, WHOIS history, false flags, the client...), scoring, the ER diagram of the supertype/subtype schema, research hooks, the ethics of the fake data, and how to add a scenario.

### `backend/data/.gitkeep`
Keeps the empty `data/` folder in git. Drop the optional Kaggle file `osint_public_profiles_dataset.csv` here before seeding and the Directory's people are drawn from it (names, usernames and companies only; its IPs and domains are deliberately ignored because they could be real).

---

## backend/database/ (the database schema)

Plain PostgreSQL 16. (Older notes may call this folder `supabase/`: the project started on hosted Supabase, moved to a local Docker Postgres, and the folder was renamed.) Migrations run **once each, in filename order**, tracked in the `_migrations` table by `scripts/migrate.py`. Never edit a migration that has already been applied anywhere; add a new numbered file instead.

### `migrations/20260930000001_schema.sql`
The core schema.
- **Extensions:** `pg_trgm` (fuzzy search), `citext` (case-insensitive text), `btree_gist` (range indexes).
- **Enums:** `entity_kind` (domain, ip, certificate, persona...), `verdict`, `rel_type` (resolves_to, cert_covers, uses_email...), `case_role` (initial_clue, chain, supporting, red_herring, false_flag, noise), `difficulty`, `case_status`.
- **`sources`:** where a fact came from, with an Admiralty reliability grade A–F.
- **`cases`:** one row per generated case: code, scenario, difficulty, RNG seed, incident and report times, victim, briefing, status, attempts, hints, score.
- **`entities`:** the **supertype**. Every investigable thing is a row here (kind, searchable value, label, verdict, `case_id` NULL for shared "world" rows). Each kind has a 1:1 **subtype table** keyed by `entity_id`: `domains`, `ip_addresses`, `whois_records`, `certificates`, `urls`, `url_scans`, `email_messages`, `malware_samples`, `threat_actors`, `personas`, `persons`, `crypto_wallets`, `breaches`, `web_articles`, and more. This lets one relationship table keep real foreign keys on both ends.
- **`entity_relationships`:** the one generalized edge table. Each edge has a `valid` time range (DNS changes over time), a source, a confidence and an optional case.
- **Hidden answer tables:** `case_entities` (the role of each record in a case), `case_ground_truth`, `case_hints`.
- **Player activity:** `case_evidence` (the board), `query_log` (every search), `submissions`.
- **`difficulty_profiles`:** every difficulty knob as data, seeded for the four levels.
- Turns on **row-level security** for every table with no policies, so only the server's own connection can read anything.

### `migrations/20260930000002_functions.sql`
SQL functions the tools call, all **case-scoped** (they see world rows plus this case's rows, never another player's): `visible_entities` / `visible_edges`, `intel_search` (exact, substring and trigram matches), `pdns` (passive DNS in both directions with time windows), `ct_search`, `pivot` (who else shares a tracking ID / favicon / JARM / nameserver / registrant email / imphash), `neighbors`, **`reachable_evidence`** (a recursive CTE that walks the player's evidence from the initial clue; DNS edges only count within ±2 days of the incident; this is what scoring uses), `case_is_solvable` (the generator's oracle), and the `v_player_paths` research view.

### `migrations/20261005000003_scam_enums.sql`
New enum values for the social-engineering scams: entity kinds (image, social_post, document, audio_recording, sms_message, payment_account, lure_template, complaint) and relationship types (posted, uses_image, pays_to, transfers_to, voice_cloned_from, calls_back_to...). Kept in its own file because Postgres can't use a new enum value in the transaction that added it.

### `migrations/20261005000004_scam_tables.sql`
Subtype tables for those kinds (`images` with perceptual hash and AI-face score, `social_posts`, `documents` with exiftool-style metadata, `audio_recordings` with voiceprint, STIR/SHAKEN and synthetic score, `sms_messages`, `phone_numbers`, `payment_accounts`, `lure_templates`, `complaints`), extra persona columns (display name, verified, follower count...), visual-match columns on URL scans, the generic **`answer_slots`** JSON on `case_ground_truth` (each scenario declares its own report fields), the **`scenarios`** catalog table, and the `reverse_image` and `money_trail` (recursive CTE) functions. Also redefines `case_is_solvable` for arbitrary answer slots.

### `migrations/20261005000005_sent_via.sql`
Adds the `sent_via` relationship (an email or SMS sent using a domain), so a message links cleanly to its sending domain.

### `migrations/20261006000006_case_discoveries.sql`
Adds integer `seq` identity columns to `cases` and `entities` (the ids the client uses), the **`case_discoveries`** table (every record a tool has shown the player, so the Case Report and pinning only allow what was found) and the `v_discovery_timeline` research view.

### `migrations/20261007000007_ad_enum.sql`
Adds the `serves_ad` relationship (a website displayed an ad leading somewhere) for the adult-ad scenario. Its own file for the same enum reason as 003.

### `migrations/20261007000008_study_and_messenger.sql`
Everything for the research study and the client Messenger:
- **Study:** `study_participants` (consent version and time, when each survey was finished), `survey_questions` (the question bank: phase, section, prompt, kind, options as JSON, required, `show_if` conditions, quiz `correct` key, and `measure` to pair pre/post questions), `survey_answers`, and `cases.participant_id`. Seeds the questions: demographics (age 18+, optional name, college status, a **major** question shown only to people who attended college, technology background and experience), scam experience, OSINT familiarity, confidence (pre and post), a six-question **knowledge quiz asked before and after**, and post-game questions (enjoyment, learning, difficulty, Messenger usefulness, client realism, most useful tool, feedback).
- **Messenger:** `client_profiles` (the nine personalities and their numbers), `difficulty_profiles.client_can_fire` (false on EASY), `case_client` (per case: personality, patience, the skeptic's theory, timers, chase count, when they withdrew), `case_client_facts` (what the client knows, written by the scenario: topics, keywords, the truth, whether it's the secret, the lie, which records it unlocks, which records prove it) and `client_messages` (the whole conversation).
- Adds the `card_merchant` payment method.
- **Research views:** `v_study_learning` (pre vs post per measure), `v_study_participants` (one row per participant with quiz before/after and case outcomes) and `v_messenger_stats` (per case: questions asked, misunderstandings, evidence shown, secrets uncovered, whether the client walked).

### `migrations/20261008000009_case_keys.sql`
Adds `cases.access_key`, a random UUID per case. `server/guard.py` refuses `/api/cases/{n}` requests that don't send it, so a case number alone no longer opens a case. Cases created before this migration get keys nobody has.

### `database/reset.sql`
Drops every table, view, function and type this project created, and nothing else in the database. Used by `make db-reset`. Run migrations and the world seed again afterwards.

---

## backend/server/ (the API)

### `server/__init__.py`
Empty; makes `server` an importable package.

### `server/requirements.txt`
The Python dependencies: `fastapi`, `uvicorn[standard]` (the web server), `psycopg[binary]` and `psycopg_pool` (PostgreSQL driver and connection pool), `pydantic` (request validation).

### `server/env.py`
`load_env()` reads `backend/.env` into the environment without overriding variables that are already set. Called by `db.py`, `scripts/migrate.py`, `scripts/playtest.py` and the world seed, so nobody has to export `DATABASE_URL`.

### `server/db.py`
The connection pool. `pool()` lazily opens a `psycopg_pool.ConnectionPool` from `DATABASE_URL` (rows come back as dicts, server-side prepared statements off) and sets `search_path`. `tx()` is the context manager every route uses: one transaction per request, committed on success, rolled back on any error.

### `server/app.py`
The FastAPI application (`server.app:app`, which uvicorn runs).
- Mounts three routers: `compat.router` (the `/api` game API), `messenger.router` and `study.router`, and the `guard.remember_case_key` middleware. `/docs` and `/openapi.json` exist only while `API_DOCS` is on.
- On startup, `sync_catalog()` writes every scenario's title and report fields into the `scenarios` table.
- Also keeps the **original UUID API** (`/scenarios`, `/health`, `/cases`, `/cases/{id}/search`, `/pdns`, `/whois`, `/ct`, `/urlscan`, `/pivot`, `/malware`, `/breach`, `/web`, `/directory`, `/reverse_image`, `/money_trail`, `/social`, `/phone`, `/sms`, `/document`, `/audio`, `/payment`, `/complaints`, `/graph`, `/evidence`, `/hint`, `/submit`, `/abandon`, `/debrief`). The playtest's first section uses it; the React client uses `/api` (only `/scenarios` and `/health` are shared). Except `/scenarios` and `/health`, these routes live on the `legacy` router, which is mounted only while `LEGACY_API` is on, because they skip case keys. Production turns it off.
- When `frontend/dist/` exists (after `npm run build`), serves the built game at `/` with a catch-all route registered last, so API routes always win and a mistyped `/api/...` path still returns a JSON 404.

### `server/compat.py`
The **`/api` routes the React client uses** (the name is historical: it began as a compatibility layer for the old client's integer ids).
- **Ids:** the client uses integer `seq` ids; `case_uuid()` and `ent_uuid()` translate them. `case_uuid()` goes through `guard.case_by_seq()`, so every case route needs the case's `X-Case-Key`.
- **Case lifecycle:** `POST /api/cases` (rate limited: `RATE_NEW_CASE`) generates a case (random scenario unless one is given), links it to a study participant if one is given, returns the case's `case_key` (the only time it is sent), and starts the client (`messenger.init_client` with a chosen or random personality). `brief_payload()` builds what CaseDesk shows: the briefing with local times, the "open link" shortcut, report fields, status, the resolution (once solved or failed) and the client's name and personality.
- **`/exhibits`:** what the client handed over: the first message and its thread, attachments, follow-ups with payment details, and payment details they were given, minus anything the client is still **withholding** (`messenger.withheld`). The first card is the victim themself, with buttons to check their own exposure (social media, breach data).
- **The original record shapes** (`domain_record`, `ip_record`, `malware_record`, `campaign_record`, `actor_record`, `person_record`, `article_record`) and `envelope()`, which groups search hits into those shapes plus cards.
- **One route per tool:** `/intel`, `/intel/domain/{n}`, `/intel/ip/{n}`, `/malware`, `/directory`, `/websearch`, `/social`, `/reverseimage`, `/phone`, `/sms`, `/documents`, `/audio`, `/payments`, `/moneytrail`, `/complaints`, `/dns`, `/whois`, `/certs`, `/urlscan`, `/pivot`, `/breach`, `/card/{n}` (any single record). Every search writes `query_log` through `qlog()`, which records which hidden roles the results contained.
- **Evidence board:** list, pin (only records the player has discovered; tells the Messenger so a client can object to a red herring) and unpin.
- **Hints**, **report options** (only discovered entities of each field's kind), **submit** (grades through `scoring.grade`, writes `submissions`, closes the case if correct, tells the Messenger, returns per-field verdicts and analyst feedback including what the client never told you; on HARD+ a wrong report only reports the count), and **graph** (pinned records plus neighbours for the Evidence Map).

### `server/cards.py`
Turns one entity into one **card**, the generic record the client draws: header, subtitle, status badge, key/value fields with a tone (ok/warn/danger), and blocks (text, monospace "terminal" text, a 0–1 meter, rows of clickable pivots), plus the pin button. One builder per kind: `persona_card`, `post_card`, `image_card` (with reverse-image sightings), `phone_card`, `sms_card`, `document_card` (exiftool block), `audio_card`, `payment_card`, `wallet_card`, `complaint_card`, `email_card` (headers, Received chain, links, attachments, crypto addresses), `email_address_card`, `url_card`, `scan_card` (tracking ID / favicon / JARM pivots), `whois_card`, `cert_card`, `sample_card`, `campaign_card`. Cards only show what the real tool would show: analyst notes stored on edges are never printed. Every builder records what it shows in `case_discoveries` through `Ctx.seen()`. Helpers: `before_incident()` ("41 days before the incident"), `phone_pretty()`, `indicator_row()` (sends an indicator a victim listed to the right tool, including payment identifiers to Payments), `APP_FOR_KIND`.

### `server/messenger.py`
The **client Messenger engine**.
- `INTENTS`: what the client understands (story, when, contact, link, login, money, amount, device, who, phone, pressure, reassure, apology, thanks, bye, insult, theory, advise, acknowledgements). A pattern is a word, a phrase, or a prefix ending in `*`. `classify()` turns a message into intents.
- `VOICE`: every line each personality can say, per situation (`open`, `confused`, `deflect`, `deny`, `admit`, `nag`, `low`, `fired`, `wrong_pin`, `no_fact`...). Missing lines fall back to `default`. `say_fact()` puts a fact in the personality's voice (the rude client lowercases and adds "happy?", the busy one shortens).
- `init_client()` runs when a case is created: picks the theory for the know-it-all, posts the opening messages (upfront clients tell their story at once; the rude one sets a time limit).
- `player_message()` answers a message: shows of evidence first, then every fact the message points at (by topic or by the fact's own keywords), applying the **disclosure rule** in `_secret()` (upfront / asked / pressed / proof). Then pressure, social replies, the oversharer's irrelevant details, and the "what are you saying?" fallback.
- `_evidence()`: a shown record that is in a secret's proof list cracks it; otherwise the client confirms, rejects or doesn't recognize it.
- `handover()`: when a secret comes out, the records it unlocks are marked discovered and returned as cards in the chat.
- **Mood:** `_apply()` changes patience, warns at 30%, and at zero (MEDIUM+) calls `_fire()`, which closes the case as `failed`. `process_nags()` lazily adds chase messages for the time the player left the client waiting.
- **Hooks from other routes:** `on_pin()` (a recognizable red herring was pinned), `on_report()` (wrong report costs patience; a correct one gets thanks), `withheld()` (what CaseDesk must not show yet).
- **Routes:** `GET /api/personalities`, `GET /api/cases/{n}/messenger` (state + messages; runs the chase check), `POST /api/cases/{n}/messenger` (`text` and/or `evidence_id`, which must be a discovered record; rate limited: `RATE_MESSAGE`). Its `case_uuid()` also checks the case key.

### `server/study.py`
The **opt-in research study**. `GET /api/study/config` (whether `STUDY_ENABLED` is on; the client hides the opt-in when it isn't), `GET /api/study/consent` (the consent text and version), `POST /api/study/participants` (requires `consent` and `adult`; returns a random participant id), `GET /api/study/participants/{id}` (which surveys are done, cases played), `DELETE /api/study/participants/{id}` (withdraw: deletes the participant and every answer), `GET /api/study/questions?phase=pre|post` (never includes the quiz key), and `POST /api/study/participants/{id}/answers`, which validates every answer against its question (number range, likert range, listed choices, text length), honours `show_if`, rejects missing required answers, stores them, and after the post survey returns the participant's quiz score before and after. With `STUDY_ENABLED` off, joining and answering return 403; withdrawing always works. Joining and answering are rate limited (`RATE_JOIN_STUDY`, `RATE_ANSWERS`). Edit `CONSENT_TEXT` (and bump `CONSENT_VERSION`) for your ethics approval.

### `server/guard.py`
What keeps a public deployment safe. **Case keys:** `remember_case_key` (middleware) reads the `X-Case-Key` header, and `case_by_seq()` returns a case only when the key matches, otherwise the same 404 as a missing case. **Rate limits:** `rate_limit(name, default)` is a route dependency allowing `count` requests per `seconds` per client IP (in memory, per process), configurable as `RATE_<NAME>=count/seconds`; requests from 127.0.0.1/::1 are exempt, so local play and the playtest never hit them. **Switches:** `STUDY_ENABLED`, `LEGACY_API` and `API_DOCS` (environment, `on`/`off`, all default on for local development; `deploy/compose.yml` turns the last two off).

### `server/scoring.py`
`grade()` scores a Case Report: each answer slot's weight (actor 0.30, person 0.20, the rest shared), −10% of the base for correct answers your evidence doesn't connect to (via `reachable_evidence`), −5% per red herring or false flag pinned (at most 6), −15% per earlier wrong attempt, minus hint costs. `resolve()` accepts an answer as a UUID, an actor alias, or a unique value.

---

## backend/server/generator/ (the case generator)

### `generator/__init__.py`
Empty; makes `generator` a package.

### `generator/fakes.py`
The fictional building blocks: adjectives and nouns for business domains, the impersonated **brands** (Northbridge Credit Union, Paylane, OneMail Workspace...), campaign-name parts ("Operation Glass Harbor"), forum and social platforms, handle parts, first and last names, cities, job titles, phishing-kit, fake-exchange, fake-alert and fake-age-gate **page artifacts**, old passwords quoted by sextortion mail, X-Mailer strings, and helpers: `hexstr`, `ssdeep`, `jarm`, `handle`, `person_name`, `unique_op_name`, `benign_domain`, `lookalike` (combosquat, typosquat, hyphenated and `.test` variants), `token`, `fake_password_hash`. The safety rule is written at the top: reserved IP ranges and `.example`/`.test` only.

### `generator/writer.py`
`Writer`, the small helper every generator uses to write rows: `ent()` inserts a supertype row plus its subtype row in one call; `edge()` inserts a relationship with a time range, source and confidence; `role()` records an entity's hidden role in the case, with rules that keep the initial clue and chain roles from being downgraded; `source()` looks up source ids.

### `generator/world.py`
Seeds the persistent **world** (rows with `case_id` NULL) shared by every case: the sources with reliability grades, 12 hosting providers with ASNs and IP blocks (cloud, CDN, VPS, bulletproof, residential, university), Tor exits and a VPN pool, the sinkhole `203.0.113.250`, registrars and nameservers, the brands' real domains, hundreds of benign shared-hosting and CDN-customer domains, eight malware families (some commodity), eight threat actors with **different names per vendor**, their historic campaigns, people (optionally from the Kaggle CSV), personas, and five breaches with hundreds of records that are *not* the suspect. `python -m server.generator.world` **truncates everything, including all cases**, and reseeds (deterministic for a given `WORLD_SEED`).

### `generator/base.py`
`Scenario`, the base class every scam inherits, plus `Profile` (one row of `difficulty_profiles`).
- `run()` picks the incident time, brand, actor and a decoy actor, the victim, and the case code, inserts the `cases` row, makes the hidden operator on HARD+, calls the subclass's `build()`, then `_finish()`.
- **Roles:** `clue()`, `chain()` (on the true path, in hop order), `support()`, `herring()` (red herring or false flag), `slot()` (an answer field).
- **`fact()`**: what the reporting party knows, in their own words: its topics, keywords, whether it's the **secret**, the lie, which records it **unlocks** and which records are **proof**. `_write_facts()` saves them to `case_client_facts`.
- **Builders:** `alloc_ip()`, `mk_domain()` (with registrar, nameservers and WHOIS snapshots, including a leaked first snapshot for unmasking), `mk_url()`, `mk_scan()`, **`site()`** (a complete phishing site with DNS history, optional CDN fronting, sinkhole, previous tenants, stale traps, a certificate linking siblings, kit fingerprints, and another actor's site on the same IP), `redirector()`, `payload()`, `email_msg()` (full headers, Received chain, SPF/DKIM/DMARC), `mail_domain()`, `phone()`, `persona()`, `post()`, `image()`, `document()`, `audio()`, `sms()`, `payment()`, `wallet()`, `lure()`, `complaints()` (corroborating and noise reports), `attribution()` (campaign, vendor report naming a vendor alias, decoy blogs, false flags), `unmask()` (operator email → breaches → forum persona → personal profile → person, plus a look-alike decoy).
- Helpers `at()`, `local()`, `said()` (how the client says a time), `when_of()`, `payment_details()`, `fict_number()` (555-01xx), `pretty()`.
- `_finish()` writes `case_ground_truth` with weights, the hints (costing 50·n), the "CASE REPORT NEEDS" line, marks all other case rows as noise, and writes the client facts.

### `generator/registry.py`
`SCENARIOS` maps each key to its class (twelve, plus the alias `credential_phish` for `bulk_phish`). `sync_catalog()` upserts every scenario's metadata and report fields into the `scenarios` table (adding the HARD+ "person" field). `profile_for()` loads a difficulty. `generate_case()` picks a seed and scenario and runs it. **Add a new scenario class here** or it won't exist.

### `generator/scenarios/__init__.py`
Empty; makes `scenarios` a package.

### `generator/scenarios/phishing.py`
The seven phishing variants, each a `Scenario` subclass with its report fields, a `build()` that creates the lure and infrastructure, chain and hints, and its client facts and secret: **CredentialPhish** (`bulk_phish`), **SpearPhish**, **Whaling**, **ClonePhish**, **AnglerPhish**, **Smishing**, **Vishing**. Their answer keys are in the wiki, section 7.1–7.7.

### `generator/scenarios/social.py`
The classic social-engineering scams: **Romance** (stolen or AI photos, handle reuse, a payment trail), **AdvanceFee** (forged certificate whose metadata exposes the forger), **TechSupport** (fake warning page, toll-free call-back, gift cards), **PigButchering** (fake trading platform, multi-hop wallet layering). Wiki sections 7.8–7.11.

### `generator/scenarios/extortion.py`
**AdultAd** (`adult_ad`): the adult-site ad and sextortion scenario. A sextortion email spoofed from the victim's own address quotes a password from an old breach (ShopLane 2021) and demands Bitcoin. Its "preview" link sits on a sibling of a fake age-verification site the victim reached from an ad (ad network click tracker → 302) on an adult video site. That site took their email and card through a card-merchant account, and both money streams cash out to the same wallet. The client's secret is the ad click; the liar denies being on "sites like that" until shown the age-check site, its scan, the click URL or the merchant. The module docstring explains the design. Wiki section 7.12.

---

## backend/scripts/

### `scripts/migrate.py`
Applies `database/migrations/*.sql` in filename order, once each, recording them in `_migrations`. Detects a database where 001/002 were applied by hand and marks them done. Needs no `psql`. Run it after pulling new migrations; safe to run any time.

### `scripts/playtest.py`
The end-to-end test, run against a live API (`python scripts/playtest.py 1`).
1. For every scenario at EASY and EXPERT: generate through the UUID API, assert `case_is_solvable`, submit the true answer (must be correct) and a decoy answer (must not be).
2. Tool coverage spot checks (reverse image, money trail, audio, documents).
3. **`play_like_client()`**: a breadth-first bot that plays every scenario at EASY and HARD through the `/api` routes, using only what the screens offer. It interviews the client (`INTERVIEW`), follows card rows and record buttons, reads aliases in text, **shows a lying client the records it found** until they admit the secret, takes the records they hand over, then must find every answer field in the report form, pin the chain, and get a correct grade. HARD uses the liar personality.
4. **`messenger_checks()`**: for every personality, a nonsense message costs patience, the secret comes out exactly by that personality's rule, and clients who chase you do (by back-dating `last_activity_at`); a rude client withdraws a MEDIUM case but not an EASY one; pinning a recognizable red herring makes the client object.
5. **`study_checks()`**: an under-18 age is rejected, both surveys save, a case links to the participant, the quiz score comes back, withdrawal deletes the participant, and joining requires the adult checkbox.

Prints `ALL CHECKS PASSED` or a list of failures, and exits non-zero on failure. `call()` remembers each case's key from `POST /api/cases` and sends it on that case's requests. Needs `LEGACY_API` on (the default).

### `scripts/export_study.py`
Exports the research study to CSV, **opted-in players only**: `participants`, `answers_long`, `answers_wide`, `learning`, `cases`, `searches`, `messages`, `evidence` (with what each pinned record really was), `submissions` and `messenger`, plus a `README.txt` describing each file and listing every question. Writes a folder and a `.zip` of it (default `exports/study-<date>`; `--out` to choose). Leaves out the user-agent string. See `docs/STUDY_DATA.md`.

---

## deploy/ (the public website)

Everything for running the game on a server with a domain. The walkthrough is `docs/DEPLOY.md`.

### `deploy/compose.yml`
The production stack: `db` (Postgres 16, data in the `pgdata` volume, listening only on the server's 127.0.0.1 for backups and SSH tunnels), `app` (built from the `Dockerfile`; `LEGACY_API` and `API_DOCS` off, the study switch and rate limits from `.env`) and `caddy` (ports 80/443, automatic HTTPS). Reads `deploy/.env`; stops with a clear message if `DOMAIN` or `DB_PASSWORD` is missing. `HTTP_PORT`, `HTTPS_PORT` and `DB_LOCAL_PORT` let you run it locally next to the dev database.

### `deploy/Caddyfile`
Serves `DOMAIN` over HTTPS (Caddy gets and renews the certificate), compresses responses, proxies to `app:8000`, sets security headers (HSTS, nosniff, no framing, referrer policy), and redirects `www.` to the bare domain.

### `deploy/entrypoint.sh`
What the app container runs on every start: `scripts/migrate.py`, then the world seed **only if the world is empty** (seeding wipes every case), then uvicorn with `--proxy-headers` (so rate limits see players' IPs) and `--no-access-log` (so visitors' IP addresses aren't kept), on `$PORT` when set (Render sets it) or 8000. The Render image uses this same script.

### `deploy/.env.example`
The settings to copy into `deploy/.env` on the server: `DOMAIN`, `DB_PASSWORD`, `STUDY_ENABLED` (off until you have approval), `WORLD_SEED` and the four rate limits.

### `deploy/backup.sh`
Writes a compressed `pg_dump` to `deploy/backups/` and keeps the newest 14. Meant for a nightly cron job; the restore command is in its header.

### `deploy/.gitignore`
Keeps `.env`, any `*.env` and `backups/` out of git.

---

## frontend/ (top level)

### `frontend/package.json`
The client's npm manifest. Scripts: `dev` (Vite dev server on :5173), `build` (`tsc --noEmit` type-check, then `vite build` into `dist/`), `preview`, `typecheck`. Dependencies: `react` and `react-dom` 19. Dev dependencies: `vite`, `@vitejs/plugin-react`, `typescript`, `@types/react`, `@types/react-dom`. No UI library: everything is hand-written.

### `frontend/package-lock.json`
npm's exact record of every installed package version, so every teammate gets the same dependency tree. Commit it; never edit it by hand (`npm install` updates it).

### `frontend/vite.config.ts`
Vite configuration: the React plugin, port 5173, and a **proxy** that forwards `/api`, `/scenarios` and `/health` to the FastAPI server (`API_URL`, default `http://127.0.0.1:8000`), so the browser talks to one origin and no CORS setup is needed.

### `frontend/tsconfig.json`
TypeScript settings: strict mode, ES2022, `react-jsx`, bundler module resolution, unused locals/parameters as errors, Vite's client types. Covers `src/` (the Vite config itself is checked by Vite).

### `frontend/index.html`
The single HTML page: the title, a description, the favicon, the `#root` div React mounts into, and the `src/main.tsx` module script.

### `frontend/public/favicon.svg`
The tab icon: a magnifying glass over a gold dot. Files in `public/` are served as-is.

### `frontend/.gitignore`
Keeps `node_modules/`, `dist/`, logs and Vite's cache out of git.

---

## frontend/src/ (the React client)

### Entry and screen flow

| File | What it does |
|---|---|
| `src/main.tsx` | Mounts `<App/>` into `#root` inside React's `StrictMode` and imports the five stylesheets in order (theme first). |
| `src/App.tsx` | Decides which **full screen** shows: `title` → (study opt-in) `consent` → `pre` survey → `boot` → `desktop`, and `post` survey → `thanks` later. Players who don't opt in skip every survey. Once booted, the Desktop stays mounted (hidden) during a survey so open windows survive. Provides `ScreensContext` (`toTitle`, `toPostSurvey`) and wraps everything in `SessionProvider`. |
| `src/theme.ts` | Brand strings (`GAME`, `OS_NAME` "SLEUTHOS", version, agency: change them here to re-brand), `statusColor()`, `toneColor()`, `kindColor()` (Evidence Map node colour by record family), `kindLabel()`, `appForKind()` (which tool shows a kind; mirrors the server's `APP_FOR_KIND`), and `MOOD_COLOR`. |

### `src/api/`

| File | What it does |
|---|---|
| `api/types.ts` | TypeScript types for **every server response**: `Card`, `Row`, `Block`, `Pin`, the seven original record shapes, `Envelope`, `Brief`, `EvidenceItem`, `Scenario`, `Personality`, `ReportOptions`, `Verdict`, graph nodes/edges, `MessengerState`/`ChatMessage`/`Mood`, and the survey types. `isCard()` tells a card from an original record. When a server response changes, change it here first: the compiler then points at every place that needs updating. |
| `api/client.ts` | The **only module that calls the server**. `request()` wraps `fetch` with JSON, adds the case's `X-Case-Key` (kept in local storage as `caseKey.<n>`; `newCase` saves it from the server's reply), turns network failures into `ApiError(0, ...)` and server errors into `ApiError(status, detail)`. `api.*` has one function per route (cases, exhibits, hint, evidence, report, graph, tool search, record fetch, messenger, study). Paths are relative: Vite's proxy handles development, and in production FastAPI serves the app itself. |

### `src/state/`

| File | What it does |
|---|---|
| `state/session.tsx` | **The Session**, the shared state every window uses (a React context). Holds the open case and brief, the evidence board, the last hint, toasts, the client chat, unread count, and the study participant and status. Functions: `startNewCase`, `refreshBrief`, `refreshEvidence`, `pin`/`unpin`/`isPinned`, `requestHint`, `closeCase`, `requestOpen` (asks the Desktop to open a window; apps never open each other directly), `sendChat`/`refreshChat`/`markChatRead`, `joinStudy`/`leaveStudy`/`refreshStudy`. It **polls the Messenger every 8 seconds** while a case is open (which also lets the server add chase messages) and turns new client messages into toasts when the Messenger isn't in front. It pings `/health` every 15 seconds for the connected/offline dot, and restores the open case and participant id from local storage after a reload. |
| `state/screens.tsx` | `ScreensContext`/`useScreens()`: lets a window (CaseDesk, the Start menu) jump to the title screen or the post-game survey without knowing how `App.tsx` arranges screens. |
| `state/storage.ts` | A guarded `localStorage` wrapper (`get`, `set`, `remove`, `getNumber`, `setNumber`) with a `cas.` prefix. Every call is wrapped in try/catch, because private windows and blocked storage throw; the game works without it. It stores only conveniences: the open case id, the participant id, and which chat messages you've read. |

### `src/screens/` (full screens outside the desktop)

| File | What it does |
|---|---|
| `screens/TitleScreen.tsx` | The title screen: logo, title, tagline, pitch, **START / CONTINUE INVESTIGATING**, **HOW TO PLAY** (opens the Field Manual), the **optional study checkbox** (or a "you're in the study" note), an offline warning, and the fictional-data footer. A rotating radar sweep sits behind it (disabled for reduced motion). |
| `screens/ConsentScreen.tsx` | Loads the consent text from the server; the player must tick "I am 18 or older" and "I agree" to **JOIN**, or choose **NO THANKS, JUST PLAY**. Nothing is stored before joining. |
| `screens/SurveyScreen.tsx` | Draws the pre or post survey from `/api/study/questions`, grouped by section. One component per question kind: number, text, long text, single choice, multiple choice, and a 1–5 **likert** scale with end labels. Questions with `show_if` appear only when an earlier answer matches (e.g. "What is your major?"). It counts answered questions, checks required ones before sending, shows the server's validation message, and can be skipped. |
| `screens/BootScreen.tsx` | The 2.2-second SleuthOS boot animation with a progress bar and status lines. Click to skip. |
| `screens/ThanksScreen.tsx` | After the post-game survey: thanks, and the participant's own **quiz score before → after**. |

### `src/os/` (the fake operating system)

| File | What it does |
|---|---|
| `os/Desktop.tsx` | The desktop: wallpaper with radar rings and watermark, the **icon grid** (one per app, with an unread badge on the Messenger), every **window**, the Start menu, toasts, the taskbar, the Field Manual, the tutorial and the Dictionary tooltip. It owns window positions, sizes, open/minimized/maximized state, **z-order**, and the "open signal" passed to an app when it's opened with a query or a record. `openApp()` is the single place windows open; it registers itself as the session's open listener. On first boot it opens CaseDesk (and the Messenger if a case is running), and it opens the Messenger whenever a new case starts. Keyboard: **F1** Field Manual, **F2** Dictionary, **Esc** closes menus. Opening any window closes the Field Manual. Each icon carries `data-tour="icon-<app>"` so the tutorial can point at it. Initial window positions cascade right of the icon columns, with the Messenger on the right edge. |
| `os/Window.tsx` | One window frame: title bar with the app's accent dot, title and unread badge, **drag to move** (pointer capture, clamped to the screen), minimize / maximize (double-click the title bar too) / close, and a **resize grip** (minimum 420×300). The frame carries `data-tour="win-<app>"` for the tutorial. Closed and minimized windows stay mounted but hidden, so each tool keeps its search and results. |
| `os/Taskbar.tsx` | The bottom bar: the **SLEUTHOS** Start button, a button per open window (click to raise, click the active one to minimize; Messenger shows unread), and the tray: the client's mood (click to open the Messenger), the case number, the connected/offline dot, and the clock. |
| `os/StartMenu.tsx` | Every app grouped by investigation stage, plus FIELD MANUAL, **TUTORIAL: YOUR FIRST CASE** (replays the tutorial), **POST-GAME SURVEY** (study participants who finished the pre survey), **LEAVE THE STUDY** (with a confirmation; deletes their answers) and BACK TO TITLE SCREEN. |
| `os/Toasts.tsx` | The notification stack in the bottom-right. Client messages appear as chat notifications with the client's name; clicking one opens the Messenger. |
| `os/FieldManual.tsx` | The F1 how-to-play overlay: the investigation loop, how clients behave and the mood meter, where to look up words (the Dictionary), what makes cases hard, and scoring. It points first-timers at the tutorial. Its jargon is underlined. |

### `src/apps/` (what's inside the windows)

| File | What it does |
|---|---|
| `apps/types.ts` | The contract between the Desktop and an app: `OpenSignal` (nonce + optional query or record to load), `AppProps` (`signal`, `active`) and `AppDef` (id, title, short name, glyph, accent colour, default size, whether it needs an open case, Start-menu group, and `render`). |
| `apps/registry.tsx` | **The list of apps**, in desktop/taskbar/Start-menu order: CaseDesk, Messenger, Dictionary, the six infrastructure tools, the ten people/messages/money tools, Web Search, Directory, Evidence Map, Case Report. The 18 lookup tools are generated from `lookupTools.ts`. Add an entry and the app appears everywhere. Also `GROUP_LABEL`. |
| `apps/lookupTools.ts` | The **18 search tools** as data: id, title, short name, glyph, accent colour, the `/api` route, the search placeholder, the help text shown before the first search, and the group. Adding a tool is one row here plus its server route. |
| `apps/LookupApp.tsx` | One search window, used by all 18 tools: query bar (BACK, search box, SEARCH, CLEAR), then a spinner, an error, the help text, a single record, or a search **envelope**. A link to a record of **this** tool loads in place, pushing the current result onto a history for BACK; a link to another tool asks the Desktop to open it. Reacts to open signals from other windows. |
| `apps/CaseDesk.tsx` | With no case: the **intake form** (scam type with its real-world basis, **client personality** or random, and four difficulty buttons with what each means). With a case: the ticket header (code, difficulty, status, client badge, attempts/hints/score), the action strip (open the link in IntelSearch, message the client, request a hint, file the report, new case), the study prompt when a participant's case has closed, the hint note, the resolution once closed (solved, or "what really happened" if the client withdrew), the briefing, and the **exhibits** as cards. Exhibits reload when the client hands something over. The new-case dialog reuses the intake form. |
| `apps/Messenger.tsx` | The **client chat**: header (initials avatar, name, role, personality badge and summary), the **mood bar** (patience, mood word, and a live **reply countdown** for clients who chase you), the message list (client bubbles on the left, yours on the right, centred system notes, records the client **hands over** drawn as compact cards, a "shared: ..." tag on records you showed), a **typing indicator** that reveals each new client message after a delay based on its length, the **SHOW EVIDENCE** picker (your evidence board), starter questions on EASY, the message box (Enter sends, Shift+Enter adds a new line), and after the case closes, **what the client was holding back** and whether you found it. |
| `apps/Glossary.tsx` | The **Dictionary** window (no case needed): every technical word in plain English, grouped by topic (scams, websites, email, files and malware, phones, people, money, investigating). A search box matches names first, then meanings; a topic filter narrows the list. Each entry has a short meaning, an optional longer note, an OPEN button for the tool it belongs to, and "see also" links. Opened with a term id (from a clicked underlined word), it scrolls to that entry and highlights it. |
| `apps/EvidenceMap.tsx` | The relationship graph of your pinned evidence and its neighbours, drawn in **SVG** with a small **force simulation** (every pair repels, edges pull like springs, a weak pull to the centre). It runs for a few seconds after anything changes, then rests. Pan by dragging the background, zoom with the wheel, drag nodes, select a node to see its links, open it in its tool, or pin it. Pinned nodes have a gold border and a ★. Includes a colour legend. |
| `apps/CaseReport.tsx` | The final report: one dropdown per conclusion the scenario asks for, each listing **only what you've found** (keeping your picks when the options refresh), the evidence board with UNPIN, SUBMIT and REFRESH FINDINGS, and the **verdict**: accepted/returned, attempt and score, a per-field OK/XX table (?? on HARD+ when it's wrong), the narrative, and the analyst feedback. |

### `src/records/`

| File | What it does |
|---|---|
| `records/RecordView.tsx` | Draws any record the server sends. **`CardView`** draws a generic card: header with kind label, title and status badge, subtitle, key/value fields with tones, and the four block types (text, terminal-style mono, meter, clickable rows). A `compact` mode collapses details for chat. The original shapes have their own views: `DomainView` (addresses with time windows, staged payloads, pivot buttons), `IpView` (location, network, reputation, co-hosted domains, beaconing malware), `MalwareView`, `CampaignView`, `ActorView`, `PersonView`, `ArticleView`. `EnvelopeView` draws a whole search result in a fixed order. Every link goes through a `RecordNav` (`open` another tool, `fetch` one record), so the hosting window decides what a click does; `useOpenNav()` is the default (always open the target tool). The pin buttons call the session and show IN EVIDENCE once pinned. |

### `src/glossary/` (the Dictionary words)

| File | What it does |
|---|---|
| `glossary/terms.ts` | **Every Dictionary entry** as data: id, name, other spellings to underline (`also`), topic, a one-line meaning (the hover text), an optional longer note, the tool it belongs to, and related entries. Add a word here and it is underlined everywhere and listed in the Dictionary. Acronyms and `also` spellings with a capital letter match only that exact case, so "SAN" never underlines "San Jose". `not` lists phrases where the word means something else ("Registrar's Office"), and `match` replaces the underlined spellings with exact-case ones (lower-case "beacon", so the campaign name "Operation Gilded Beacon" is left alone). |
| `glossary/match.ts` | `findTerms(text)`: finds Dictionary words in a piece of text (longest spelling wins, plurals allowed, never inside a domain, email or file name, each term once). Free of React so the rules can be tested on their own. |
| `glossary/GlossaryText.tsx` | Draws text with its Dictionary words as dotted-underlined `.gloss` buttons that carry a term id and no handlers. Used for tool help text, record kind labels, notes and text blocks, campaign descriptions, the case briefing, the report narrative, the Field Manual, and (through `widgets.tsx`) section labels and field names. |
| `glossary/GlossaryTooltip.tsx` | One tooltip for the whole desktop. It listens at the window for hover and focus on any `.gloss` word to show its meaning, and catches clicks (in the capture phase, so overlays can't swallow them) to open the Dictionary on that entry. |

### `src/tutorial/` (the first-case tutorial)

| File | What it does |
|---|---|
| `tutorial/steps.ts` | **The tutorial as data**: thirteen steps through a real EASY bulk-phishing case with the Super sweet client (`TRAINING_CASE`): get the case, read the briefing, ask the client a question, pin the email, open the link in IntelSearch, pin the domain, open DNS History, pin the IP live at the incident time, pin the campaign from Web Search, pin the threat actor from the Directory, look at the Evidence Map, file the report, and a wrap-up. Each step has a title, body text (it can quote the case's own incident time and domain), the elements to point at (`target`, first one on screen wins), an optional action button, and a `done` check that reads the Session (evidence kinds pinned, a message sent, a window open, the case solved). Steps without `done` wait for NEXT. Edit the wording or order here. |
| `tutorial/Tutorial.tsx` | The **coach panel** and the **glowing ring**. Offered once to a player with no case (state kept in local storage as `cas.tutorial`, so it survives a reload), replayable from the Start menu. Every render it ticks off any step the player has already done ("✓ Done. Next step:"), so doing things out of order is fine. Every 300 ms it finds the step's target, rings it (clipped to its window's scroll area), and moves the panel to whichever corner is clear of the ring; once per step it brings the target's window to the front and scrolls the target into view. It warns when a different case is on the desk, can be hidden to a pill or closed, and offers "skip this step" if a check never fires. |

Elements the tutorial points at carry `data-tour` attributes: `briefing`, `exhibits`, `open-link` and `hint` (CaseDesk), `starters` and `chat-input` (Messenger), `pin` and `pivot-<app>` (records), `submit` (Case Report), plus `win-<app>` and `icon-<app>`. Renaming one means updating `steps.ts`.

### `src/ui/`

| File | What it does |
|---|---|
| `ui/widgets.tsx` | Small shared pieces: `Badge`, `SectionLabel`, `Spinner` (with a label, announced to screen readers), `Notice` (info/error panel), `Meter` (a 0–1 bar going green → amber → red), `ActionRow` (a clickable row with text and an action label) and `KeyValue`. Plain-text section labels and field names get their Dictionary words underlined. |

### `src/styles/`

| File | What it does |
|---|---|
| `styles/theme.css` | **Design tokens** as CSS variables (desktop, window, title bar, text, accent, ok/warn/danger, fields, buttons, terminal, fonts), the page reset, and the shared widget styles: buttons (`.btn`, `-primary`, `-small`, `-large`, `-ghost`, `.link-btn`), fields and form labels, checkboxes, badges, section labels, the spinner, notices, meters, rows, key/value grids, chips and dots. Change colours here and every screen follows. |
| `styles/screens.css` | Full screens: the shared dark radial background, the **radar rings** (with the sweep animation on the title screen), the title layout and study opt-in box, the form card used by consent and surveys, survey sections, questions, the likert scale, the quiz result, and the boot screen. |
| `styles/desktop.css` | The OS: desktop and wallpaper, the icon grid and badges, windows (frame, title bar, buttons, resize grip, active shadow), the taskbar and tray, the Start menu, toasts, overlays and the Field Manual, and the tutorial (coach panel, collapsed pill, pulsing ring, and toasts stepping aside when the panel takes the bottom-right corner). Hides some tray items on narrow screens. |
| `styles/records.css` | Records: card frame and header, fields, sections and notes, the terminal block, pivot buttons, pin buttons, compact chat cards, and news-style articles (a blue edge marks reliable sources). |
| `styles/apps.css` | Window contents: the generic app layout and query bar; CaseDesk's ticket header, action strip, callouts, briefing and intake form; the Case Report's verdict table; the Messenger (header, avatar, mood bar and pulsing countdown, chat bubbles, typing dots, handover cards, starters, evidence picker, input); the Evidence Map (bar, SVG canvas, edges and labels, nodes, side panel, legend); and the Dictionary (underlined words, the tooltip, entries and the highlight flash). |
