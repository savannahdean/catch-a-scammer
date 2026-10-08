# Getting the research study data

Players can opt into the study on the title screen. This page covers what that records, how to turn the study on, and how to get the data onto your own computer.

## What is recorded

Only for players who tick **"Take part in our research study"** and agree to the consent screen:

| Stored | Where |
|---|---|
| A random participant ID, the consent version, and when they agreed | `study_participants` |
| Their pre-game and post-game survey answers (background, a knowledge quiz before and after, confidence, feedback) | `survey_answers` |
| Everything they did in their cases: every search, every Messenger message, what they pinned, every report they submitted, hints, scores and timings | the game's own tables, linked through `cases.participant_id` |

**Not recorded:** names, email addresses or accounts (there are none). The production server also doesn't keep an access log of visitors' IP addresses. The browser's user-agent string is stored with the participant, but the export leaves it out.

**Withdrawing** (Start menu → LEAVE THE STUDY) deletes the participant and all their survey answers. Their cases stay in the database but are no longer linked to them, so they never appear in an export again.

Players who don't opt in still play normally, but nothing ties their games to a participant, and the export skips them.

## Before you collect data from the public

1. **Ask about ethics approval.** Surveying people and recording their behavior is human-subjects research. Ask your professor whether your institution's IRB (or ethics board) has to approve it, or whether a class-project exemption applies. Don't turn the study on for the public until that's settled.
2. **Update the consent text** if the board asks for changes: researchers' names, a contact email, the approval number, how long you keep the data. It's `CONSENT_TEXT` in [`backend/server/study.py`](../backend/server/study.py). When you change it, also bump `CONSENT_VERSION` (for example to `2026-11-v2`). Each participant's row records which version they agreed to.
3. **Turn the study on.** On Render: **catch-a-scammer → Environment**, set `STUDY_ENABLED` to `on`, and save. On your own server: set `STUDY_ENABLED=on` in `deploy/.env`, then run `docker compose up -d`. To close it later, set it back to `off`. Existing participants can still withdraw, but nobody new can join and no new answers are accepted.

## Getting the data: CSV export (the usual way)

The export script writes one folder of CSV files plus a `.zip` of it. They open in Excel, Google Sheets, R or pandas.

**On Render**, you run the export on your own PC against the Render database: see [DEPLOY_RENDER.md → Getting the study data](DEPLOY_RENDER.md#getting-the-study-data). On your own server, follow the three steps below.

**1. On the server** (`ssh root@<server-ip>`):

```bash
cd /opt/catch-a-scammer/deploy
docker compose exec app python scripts/export_study.py --out /tmp/study
docker compose cp app:/tmp/study.zip ./study-$(date +%F).zip
```

**2. On your PC** (PowerShell), download it:

```powershell
scp root@<server-ip>:/opt/catch-a-scammer/deploy/study-*.zip .
```

**3. Delete the copy on the server** once you have it: `rm /opt/catch-a-scammer/deploy/study-*.zip`.

During development you can export from your local database the same way: `cd backend` then `.venv\Scripts\python scripts\export_study.py`. The files land in `backend/exports/`, which git ignores.

### What's in the export

Every file has a `participant_id` column, so you can join them. `README.txt` in the export describes each file and lists every question key with its wording.

| File | One row per | Use it for |
|---|---|---|
| `participants.csv` | participant | Background, **quiz score before and after**, cases played, solved, lost, average score |
| `answers_long.csv` | answer | Every survey answer with its question text; `is_correct` for quiz items |
| `answers_wide.csv` | participant | The same answers with one column per question (easiest in Excel/SPSS) |
| `learning.csv` | participant × measure | Before and after values for each paired measure (quiz items 1/0, confidence 1–5) |
| `cases.csv` | case | Scam type, difficulty, client personality, outcome, attempts, hints, score, minutes taken |
| `searches.csv` | search | Every tool search in order, and whether it hit a real clue (`chain`) or a decoy (`noise`, `false_flag`) |
| `messages.csv` | message | The whole Messenger conversation, what the game understood, the client's patience after each message |
| `evidence.csv` | pinned record | What they pinned and what it really was (a real link, a red herring, or unrelated) |
| `submissions.csv` | report | Each Case Report: right or wrong, score, per-field breakdown |
| `messenger.csv` | case | How they handled the client: messages, misunderstandings, secrets uncovered, whether the client quit |

The headline result, **did players learn?**, is `quiz_pre` vs `quiz_post` in `participants.csv`, or item by item in `learning.csv`.

## Getting the data: live SQL (optional)

**On Render**, add your IP to the database's allow list and connect SQLTools with the parts of the **External Database URL** (host, port 5432, database `osint`, user `cas`, its password, SSL on). Remove your IP afterwards. **On your own server**, use an SSH tunnel:

The database is only reachable from the server itself, so the tunnel is the way in.

```powershell
ssh -N -L 5433:127.0.0.1:5432 root@<server-ip>     # leave this window open
```

Then add a connection in SQLTools: server `localhost`, port **5433**, database `osint`, user `cas`, and the `DB_PASSWORD` from the server's `deploy/.env` (choose "ask for password" rather than saving it). The research views are ready to query:

```sql
-- did people learn? average quiz score before and after
select count(*) as participants, round(avg(quiz_pre), 2) as before, round(avg(quiz_post), 2) as after
from v_study_participants where post_done_at is not null;

-- the same, split by technical background
select tech_background, count(*), round(avg(quiz_post - quiz_pre), 2) as avg_gain
from v_study_participants where post_done_at is not null group by 1 order by 1;

-- how many joined, finished the first survey, and finished both
select count(*) joined, count(pre_done_at) pre_done, count(post_done_at) both_done from study_participants;
```

Treat this connection as read-only. Anything you change here changes the live game.

## Looking after the data

- Keep exports wherever your approval says, and nowhere public: not in this git repo, a public drive, or a chat channel. `backend/exports/` and `deploy/backups/` are already ignored by git.
- Database backups (Render's, or the nightly ones from [DEPLOY.md](DEPLOY.md#7-back-up-the-database-every-night)) contain the study data too, so look after them the same way.
- On Render's **free** database plan, everything is deleted after 30 days. Upgrade before you collect real data.
- When the study is over, set `STUDY_ENABLED=off`. Delete the data when your approval says to: `delete from study_participants;` removes every participant and their answers.
