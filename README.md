# Catch a Scammer

An open-source intelligence (OSINT) investigation game, built for our Database Management Systems course.

**➤ Play it now: [catch-a-scammer.onrender.com] (https://catch-a-scammer.onrender.com/)**.
Just open the website; there is nothing to install. Everything below is only for editing the game yourself.

Someone has been scammed. You play an analyst on **SleuthOS**, a fake investigator desktop. You read the case, **question the client** in a chat app (some of them lie), and follow the evidence through about twenty tools: DNS history, WHOIS, certificate logs, URL scans, social media, reverse image search, phone lookups, breach data, money trails and more. Then you name who is behind it, without being fooled by decoys.

- **12 scam types**: phishing (bulk, spear, whaling, clone, angler), smishing, voice-clone vishing, romance, advance-fee, tech-support, pig-butchering and adult-site ad sextortion. Every case is generated fresh.
- **9 client personalities**, from *super sweet* to *liar* and *extremely rude*, with a mood meter that can lose you the case.
- **An optional research study**: pre- and post-game surveys plus a quiz, stored in the database.
- **Everything is fictional.** Domains end in `.example`/`.test`, IPs come from reserved documentation ranges, phone numbers are 555-01xx, and every company and person is invented.

```
 React client (frontend/)  ──HTTP/JSON──▶  FastAPI server (backend/server/)  ──SQL──▶  PostgreSQL 16 (Docker)
 SleuthOS desktop, Messenger,               case generator, tools, client            schema, search functions,
 surveys. Holds no answers.                 Messenger engine, scoring, study          recursive chain validation
```

**Documentation**

| Document | What's in it |
|---|---|
| [docs/GAME_WIKI.md](docs/GAME_WIKI.md) | How to play, every tool, every client personality, scoring, and the **answer key** for all 12 scenarios (spoilers) |
| [docs/FILE_DICTIONARY.md](docs/FILE_DICTIONARY.md) | What every file in the repo does, in detail |
| [backend/README.md](backend/README.md) | The backend in depth: API routes, realism layers, schema, research hooks |
| [docs/DEPLOY_RENDER.md](docs/DEPLOY_RENDER.md) | Putting the game on the web with **Render** (uses `render.yaml`), including your own domain |
| [docs/DEPLOY.md](docs/DEPLOY.md) | The alternative: your own Linux server with Docker and HTTPS (uses `deploy/`) |
| [docs/STUDY_DATA.md](docs/STUDY_DATA.md) | The research study: what's recorded, turning it on, exporting the data to CSV |
| This README | What to download, how to run it, how to edit it |

---

## 1. What to download (developers only)

Install these once. The versions are what we test with; newer is fine.

| Tool | Version | Why | Get it |
|---|---|---|---|
| **Git** | any | clone the repo | https://git-scm.com/downloads |
| **VS Code** | any | editor, tasks, debugger | https://code.visualstudio.com/ |
| **Python** | 3.12 or newer (we use 3.14) | the game server | https://www.python.org/downloads/ (on Windows tick **"Add python.exe to PATH"**) |
| **Node.js** | 22 LTS or newer (we use 24 LTS) | builds and runs the React client | https://nodejs.org/ (the LTS installer includes `npm`) |
| **Docker Desktop** | any | runs the PostgreSQL database | https://www.docker.com/products/docker-desktop/ (on Windows Home it asks you to enable **WSL 2**: say yes and reboot) |

When you open the folder, VS Code offers to install the recommended extensions (Python, Pylance, Python Debugger, Docker, SQLTools + its PostgreSQL driver). Accept them. **SQLTools** lets you browse the game's tables from the sidebar: the connection "catch-a-scammer (Docker)" is already configured.

You do **not** need C++, CMake, MSYS2 or raylib any more.

---

## 2. First-time setup

### Option A: VS Code (recommended)

1. Start **Docker Desktop** and wait until it says it's running.
2. `File → Open Folder…` and pick the `catch-a-scammer` folder.
3. `Ctrl+Shift+P` → **Tasks: Run Task** → **Setup: everything (first time)**.
   This creates the Python virtual environment, installs the server and client packages, creates `backend/.env`, starts Postgres, applies the migrations and seeds the world (about 1,500 fictional records). It takes a few minutes the first time.

### Option B: by hand (PowerShell on Windows)

```powershell
cd backend
docker compose up -d --wait                       # Postgres on localhost:5432
copy .env.example .env                            # DATABASE_URL for the Docker database
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
.venv\Scripts\python scripts\migrate.py           # create/upgrade the schema (safe to re-run)
.venv\Scripts\python -m server.generator.world    # seed the world (wipes existing cases)
cd ..\frontend
npm install
```

On macOS/Linux use `cp` instead of `copy` and `.venv/bin/python` instead of `.venv\Scripts\python`, or run `make setup db-up db-migrate db-seed` inside `backend/`.

The server and scripts read `backend/.env` themselves, so you never need to set `DATABASE_URL` by hand.

---

## 3. Running the game

### In VS Code

1. Start **Docker Desktop**.
2. `Ctrl+Shift+P` → **Tasks: Run Task** → **Run game (database + API + client)**.
   This starts Postgres, the API on port 8000 and the client dev server on port 5173, each in its own terminal panel.
3. Open **http://localhost:5173**.

To **debug**, open the Run and Debug panel (`Ctrl+Shift+D`):

| Launch configuration | What it does |
|---|---|
| **API: debug the FastAPI server** | runs the server with breakpoints in any `backend/` Python file. Stop the "API: run server" task first: only one process can use port 8000. |
| **Client: open the game in Edge / Chrome** | starts the dev server and opens the game with breakpoints in `frontend/src/*.tsx` |
| **Full game: debug API + open client in Edge** | both at once |
| **Test: debug the playtest** | the end-to-end test with breakpoints |

All the tasks are in `.vscode/tasks.json`:

| Task | Does |
|---|---|
| Setup: everything (first time) | everything in section 2 |
| DB: start / stop Postgres (Docker) | `docker compose up -d --wait` / `docker compose down` |
| DB: apply migrations | runs any new `backend/database/migrations/*.sql` |
| DB: seed the world (wipes all cases) | rebuilds the fictional world |
| API: run server | FastAPI on http://127.0.0.1:8000 (API docs at `/docs`) |
| Client: run dev server | Vite on http://localhost:5173, hot-reloads as you edit |
| Client: build for production | builds `frontend/dist/`; the API then serves the game at http://127.0.0.1:8000 by itself |
| Test: playtest every scenario | the end-to-end test (needs the API running) |

### By hand

Two terminals:

```powershell
# terminal 1: the API
cd backend
.venv\Scripts\python -m uvicorn server.app:app --port 8000

# terminal 2: the client
cd frontend
npm run dev            # then open http://localhost:5173
```

For a one-process demo (for example on a classroom PC): run `npm run build` inside `frontend/`, then run only the API and open **http://127.0.0.1:8000**.

> **OneDrive note:** if the repo is inside a OneDrive folder, `uvicorn --reload` doesn't notice file changes and can leave stray worker processes behind. Run without `--reload` and restart the server after editing Python files. If port 8000 is "already in use", end the leftover `python.exe` processes in Task Manager.

---

## 4. How to play (short version)

1. **Title screen** → *Start investigating*. Tick the study box first if you're taking part (it's optional).
2. **CaseDesk** → choose a scam type (or Random), a client (or Random for the difficulty), and a difficulty.
3. **Messenger** → question your client: what happened, when, how they were contacted, whether they clicked, paid or downloaded anything, and whether they're leaving something out. Liars only admit the truth when you **SHOW EVIDENCE** that proves it.
4. Work the **tools**: every record links to the next one. **ADD TO EVIDENCE** on the records that connect the first exhibit to your conclusions.
5. **Case Report** → fill in every field and submit.

Press **F1** in the game for the Field Manual. The full guide and answer key are in [docs/GAME_WIKI.md](docs/GAME_WIKI.md).

---

## 5. How to edit the game

Find the change you want below. [docs/FILE_DICTIONARY.md](docs/FILE_DICTIONARY.md) explains every file in more depth.

| I want to… | Where | How |
|---|---|---|
| **Add a scam scenario** | `backend/server/generator/scenarios/` | Write a `Scenario` subclass with `build()` (see `extortion.py` for a complete, commented one). Use the shared builders in `base.py`: `site()`, `email_msg()`, `persona()`, `payment()`, `wallet()`, `complaints()`, `attribution()`, `unmask()`, and `fact()` for what the client knows and hides. Declare `report_fields`, then add the class to `SCENARIOS` in `registry.py`. The playtest picks it up automatically. |
| **Change what a client says** | `backend/server/messenger.py` → `VOICE` | Each personality has lists of lines per situation (`open`, `confused`, `deflect`, `nag`, `fired`...). Add lines to a list for more variety. |
| **Add a client personality** | migration + `messenger.py` | `INSERT INTO client_profiles ...` in a new migration (patience, costs, chase timer, disclosure rule, which difficulties deal it), then add a `VOICE` entry with its lines. Missing lines fall back to `default`. |
| **Teach the client new words** | `backend/server/messenger.py` → `INTENTS` | Add a word, a phrase, or a prefix ending in `*` to an intent. Per-scenario words go in that scenario's `fact(..., keywords=[...])`. |
| **Retune difficulty or a personality** | the database | No code needed: `UPDATE difficulty_profiles SET ...` or `UPDATE client_profiles SET patience = 50 WHERE key = 'rude'`. For a permanent change, put the `UPDATE` in a new migration. |
| **Add or change a survey question** | new migration | `INSERT INTO survey_questions (...)`. The client draws whatever is in the table. Kinds: `number`, `text`, `longtext`, `choice`, `multi`, `likert`. `show_if` makes it conditional; `measure` pairs a pre and post question. |
| **Change the consent text** | `backend/server/study.py` | `CONSENT_TEXT`. Bump `CONSENT_VERSION` too. |
| **Add an investigation tool** | 3 places | A route in `backend/server/compat.py` that returns `result(q, cards, ...)`, a card builder in `backend/server/cards.py` if it's a new kind of record, and one row in `frontend/src/apps/lookupTools.ts`. |
| **Change the look** | `frontend/src/styles/theme.css` | Colours and fonts are CSS variables at the top. `frontend/src/theme.ts` has the OS name ("SLEUTHOS") and the colour per record kind. |
| **Change the desktop / windows** | `frontend/src/os/` | `Desktop.tsx` (icons, window placement), `Window.tsx` (dragging, resizing), `Taskbar.tsx`, `StartMenu.tsx`. Window order and icons come from `frontend/src/apps/registry.tsx`. |
| **Change the database schema** | `backend/database/migrations/` | Add a new numbered `.sql` file (never edit an applied one) and run **DB: apply migrations**. New enum values go in their own file (Postgres can't use a new enum value in the same transaction). |

After **Python** changes, restart the API. After **client** changes, the dev server reloads the page by itself. After **migrations**, run **DB: apply migrations**.

### Checking your change

```powershell
cd backend
.venv\Scripts\python scripts\playtest.py 1      # with the API running
```

The playtest generates every scenario at several difficulties, proves each is solvable, grades a right and a wrong answer, has a bot **play every scenario through the same API the client uses** (including interviewing a lying client and showing them proof), checks every client personality, and exercises the study endpoints. It ends with `ALL CHECKS PASSED` or lists what failed. For the client, `npm run build` inside `frontend/` type-checks everything.

---

## 6. The research study (for the course paper)

Players opt in on the title screen. The study's tables:

| Table / view | Holds |
|---|---|
| `study_participants` | one row per participant: consent version and time, when each survey was finished |
| `survey_questions` | the question bank (pre and post), including the quiz answer key |
| `survey_answers` | every answer, as JSON |
| `cases.participant_id` | which cases a participant played |
| `query_log`, `case_discoveries` | every search and every record each player surfaced, and when |
| `client_messages` | every message to and from the client |
| `v_study_participants` | per participant: background, quiz score before/after, cases played/solved/lost |
| `v_study_learning` | per participant and measure: pre value vs post value |
| `v_messenger_stats` | per case: questions asked, misunderstandings, secrets uncovered, whether the client walked |
| `v_player_paths`, `v_discovery_timeline` | step-by-step trails through each case |

A few starting queries (run them from SQLTools in VS Code):

```sql
-- Did players learn? Average quiz score before and after.
select round(avg(quiz_pre), 2) as before, round(avg(quiz_post), 2) as after, count(*) as n
from v_study_participants where post_done_at is not null;

-- Which client personalities cost players the case most often?
select personality, count(*) as cases, avg(client_fired::int) as fired_rate, avg(secrets_uncovered) as secrets_found
from v_messenger_stats group by personality order by fired_rate desc;

-- Learning gain by technology background.
select tech_background, round(avg(quiz_post - quiz_pre), 2) as gain, count(*)
from v_study_participants where post_done_at is not null group by tech_background;
```

Participants can leave from the Start menu. That deletes their survey answers and unlinks their cases.

---

## 7. Repository layout

```
catch-a-scammer/
├─ frontend/             React + TypeScript client (Vite). The game players see.
├─ backend/
│  ├─ server/            FastAPI app: API routes, cards, Messenger, study, scoring
│  │  └─ generator/      case generator: world seed, shared builders, 12 scenarios
│  ├─ database/migrations/   the PostgreSQL schema, in order
│  ├─ scripts/           migrate.py, playtest.py
│  └─ docker-compose.yml the local Postgres
├─ docs/                 GAME_WIKI.md, FILE_DICTIONARY.md
└─ .vscode/              tasks, launch configs, recommended extensions, settings
```

The old raylib/C++ client was replaced by `frontend/` and removed; it's still in git history (commit `dcfaaa9`) if anyone needs it.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| The title screen says the server isn't answering | The API isn't running, or Docker isn't. Start Docker Desktop, then **Run game**. |
| `docker: error during connect` / "pipe not found" | Docker Desktop isn't started yet. Open it and wait for "Engine running". |
| `could not connect to server ... port 5432` | Run **DB: start Postgres (Docker)**. |
| `relation "case_client" does not exist` | Run **DB: apply migrations**. |
| `address already in use` on port 8000 | Another API instance is still running. Stop the task, or end leftover `python.exe` processes. |
| Port 5173 in use | Close the other `npm run dev`, or run `npm run dev -- --port 5174`. |
| PowerShell won't run `Activate.ps1` | You don't need to activate: call `.venv\Scripts\python` directly as shown above. |
| `npm` is not recognized | Install Node.js LTS and restart VS Code so it picks up the new PATH. |
| The world looks empty / searches find nothing | Run **DB: seed the world** (note: it wipes existing cases). |

---

## Ethics of the fake data

IPs come only from reserved ranges (198.18.0.0/15 per RFC 2544; 192.0.2.0/24 and 203.0.113.0/24 per RFC 5737). Every domain ends in `.example` or `.test` (RFC 2606). Phone numbers use the 555-0100–0199 fiction block. Brands, vendors, malware, actors and people are invented. Nothing in the game points at a real server, company or person. The adult-ad scenario is deliberately non-explicit: the site is only ever "an adult video site".
