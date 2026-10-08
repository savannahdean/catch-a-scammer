# Catch-a-Scammer — realistic OSINT backend (PostgreSQL)

```
React client (../frontend)  ──HTTP/JSON──▶  FastAPI (server/)  ──SQL──▶  PostgreSQL (Docker)
  SleuthOS desktop, Messenger,                case generator, tools,      schema, search functions,
  study surveys                               Messenger, study, scoring   recursive chain validation
```

Setup and day-to-day running (VS Code tasks, PowerShell) are in the [top-level README](../README.md);
the answer key for every scenario is in [docs/GAME_WIKI.md](../docs/GAME_WIKI.md).

The client never sees the database password or the answer tables. Every table
also has row-level security on with no policies, so only the server's own
connection can read them.

## Quick start

```bash
docker compose up -d      # local Postgres 16 on :5432 (needs Docker Desktop running)
make setup                # venv, C++ headers, creates .env (already points at the Docker DB)
make db-migrate           # apply all migrations (tracked, idempotent)
make db-seed              # the persistent "world" (~1,500 entities)
make test                 # every scenario: solvable, graded, played by a bot; Messenger + study checks
make server               # API on :8000   (leave running)
make web                  # React client on :5173 (in another terminal)
```

Without `make` (plain Windows PowerShell), from this `backend/` folder:

```powershell
docker compose up -d
copy .env.example .env                       # the server and scripts read DATABASE_URL from here
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
.venv\Scripts\python scripts\migrate.py
.venv\Scripts\python -m server.generator.world
.venv\Scripts\python -m uvicorn server.app:app --port 8000      # leave running
# in a second terminal:
.venv\Scripts\python scripts\playtest.py 1
```

The schema is plain PostgreSQL, in `database/migrations/` (applied in filename order by `scripts/migrate.py`).

Put the Kaggle file at `data/osint_public_profiles_dataset.csv` before `make db-seed`
and the Directory is filled from it (names, usernames, companies only; its IPs and
domains are ignored on purpose because they could be real).

## Scam scenarios

The game ships **12 scam types**, picked at case creation (`scenario` in `POST /cases`,
or `"random"`). `GET /scenarios` lists them with the Case Report fields each one needs,
so the client builds the right answer form per scam. Each is a real technique; the
"2.0" phishing variants add AI-era tailoring the player can see in the evidence.

Phishing family (shared web-infrastructure investigation):

| key | scam | the twist the player must catch |
|---|---|---|
| `bulk_phish`   | Bulk phishing 2.0   | one lure template reused across locales = mass campaign |
| `spear_phish`  | Spear phishing 2.0  | lure quotes a real detail from the victim's public posts |
| `whaling`      | Whaling / BEC 2.0   | exec impersonation from a look-alike domain; follow the mule account |
| `clone_phish`  | Clone phishing 2.0  | pixel-perfect clone, proven by a perceptual-hash match |
| `angler_phish` | Angler phishing 2.0 | impostor "support" account hijacks a public complaint |
| `smishing`     | Smishing 2.0        | audience-matched SMS from a VoIP number |
| `vishing`      | Vishing 2.0         | voice cloned from a real public recording |

Classic social-engineering scams (different toolset — images, docs, phone, money trail):

| key | scam | the twist the player must catch |
|---|---|---|
| `romance`        | Romance / catfishing      | reverse image search exposes the real photo owner (or an AI face) |
| `advance_fee`    | Advance-fee ("prince")    | document metadata exposes the forger |
| `tech_support`   | Tech-support scam         | fake pop-up → call-back number → gift-card payment |
| `pig_butchering` | Pig-butchering (crypto)   | multi-hop wallet trail from a fake trading platform |
| `adult_ad`       | Adult-site ad & sextortion | the "I recorded you" threat is a bluff (breach data); the client hides the ad click that gave away their card |

Every scenario also writes what the reporting party knows (`case_client_facts`, via
`Scenario.fact()`), including one thing they may hide. The client Messenger
(`server/messenger.py`) serves those facts in the voice of one of nine personalities.

At `hard`/`expert` every scenario also requires unmasking the **real person** behind the
operation (leaked email → breach corpus → forum persona → social handle → identity), with a
look-alike handle planted to punish jumping to conclusions.

Adding scam #13 is one class in `server/generator/scenarios/` plus a line in
`registry.py`; the tools, graph, scoring, Messenger and logging all work unchanged.

## The game client (`/api`, server/compat.py + server/cards.py)

The React game in the repo's top-level `frontend/` talks only to the `/api/...`
routes. It uses **integer** ids (the `seq` identity column every case and
entity gets on creation, next to its UUID) and is a thin renderer: it holds no game
data and no answer key. In development Vite proxies `/api` to this server; after
`npm run build` this server also serves the built client at `/`.

Every tool answers a search with one envelope:
`{"query", "found", "message", "cards": [...], ...}`. The original four tools
also return their older record lists (`domains`, `ips`, `malware`, `actors`,
`persons`, `articles`). All newer tools return **cards**: server-described
records (fields, text, raw tool output, detector meters, rows of pivots into
other tools, the pin button) built in `server/cards.py`, which the client draws
with one renderer. A new tool is one route, one builder, and one line in the
client's `apps_lookup.cpp`.

| Client app | Route (`/api/...`) | What a real analyst gets from it |
|---|---|---|
| CaseDesk | `POST cases`, `GET cases/{n}`, `GET cases/{n}/exhibits`, `POST .../hint` | the brief, and the exhibits the victim handed over (the message, the profile, the payment details) |
| IntelSearch | `intel`, `intel/domain/{n}`, `intel/ip/{n}` | domain and IP records, hosting, co-hosted domains |
| DNS History | `dns` | passive DNS both directions, with first/last seen |
| WHOIS History | `whois` | every registration snapshot, incl. pre-privacy leaks |
| CertSearch | `certs` | certificate transparency, SAN lists |
| URL Scanner | `urlscan`, `pivot` | page scans; pivot on tracking ID, favicon, JARM |
| MalwareDB | `malware` | families, and file analyses by hash / file name |
| Social Search | `social` | profiles by handle, name or bio; posts and DMs by text (a match returns the author too) |
| Reverse Image | `reverseimage` | every copy of a photo, oldest first; AI-face score |
| Phone Lookup | `phone` | carrier, line type, CNAM, spam reports |
| Spam Texts | `sms` | reported texts by number or wording |
| Audio Lab | `audio` | transcripts, STIR/SHAKEN, voiceprint match, synthetic-voice score |
| Document Lab | `documents` | exiftool-style metadata that exposes forgers |
| Payments | `payments` | accounts, payment handles, gift cards, wallets (1-char prefixes allowed) |
| Money Trail | `moneytrail` | follows transfers hop by hop (recursive CTE) to the cash-out |
| ScamWatch | `complaints` | other victims' reports: corroboration and noise |
| Breach Lookup | `breach` | exact email / username in leaked user tables |
| Web Search | `websearch` | vendor reports and blogs, plus any campaign they name |
| Directory | `directory` | actor aliases across vendors, and people |
| Evidence Map | `cases/{n}/graph` | pinned evidence and its neighbours |
| Case Report | `cases/{n}/report-options`, `cases/{n}/submit` | one field per answer slot the scenario declares |
| Messenger | `GET/POST cases/{n}/messenger`, `personalities` | the client: keyword-driven answers, secrets, the mood meter, chasing (server/messenger.py) |
| (any) | `card/{n}` | one record, for links between tools |
| (all) | `GET/POST/DELETE cases/{n}/evidence` | the evidence board (pinning a red herring the client recognizes upsets them) |
| Study | `study/consent`, `study/participants[/{id}[/answers]]`, `study/questions?phase=` | opt-in consent, pre/post surveys, withdrawal (server/study.py) |

**You can only name what you found.** Every record a tool shows is written to
`case_discoveries`. The Case Report offers, for each field, only entities of that
kind the player has surfaced, and pinning requires discovery too. That table is
also research data (`v_discovery_timeline`: when each player first saw each part
of the answer and each decoy).

**Every scenario is proven solvable through the client.** `make test` includes a
bot that starts from the exhibits and may only follow what the client's screens
offer (card rows, record buttons, names it reads in text, and records the client
hands over in the Messenger). It must surface every answer slot, pin the chain,
and get a correct grade, for all 12 scenarios at easy and hard. On hard the client
is a **liar**, so the bot has to show them proof, and the case includes unmasking
the real person. `make test` also checks every client personality and the study.

Every search still writes to `query_log`, so the research data is the same
whichever client is used.

## What makes it realistic (and hard)

Each item below is a real analyst skill the player has to use.

| Layer | What the data does | Skill it forces |
|---|---|---|
| **The client** | The reporting party is a chat contact with one of nine personalities. Some hide the embarrassing part; a liar only admits it when shown proof; a rude client chases you every 75 seconds and can withdraw the case. | Interviewing a victim: asking the right question, noticing what's missing, confronting with evidence. |
| **Time-bounded DNS** | Every `resolves_to` edge has a valid-time range. The domain later points to a **sinkhole**, and the IP hosted other sites months earlier. | "Where did it point *at the moment of the click*?" |
| **CDN fronting** | On harder cases the domain sits behind a shared CDN IP with hundreds of benign neighbours and a shared edge certificate. | Find the origin in older DNS history. |
| **Compromised redirector** | The email link goes to a *legitimate* small-business site that was hacked. | The first domain is a victim, not the attacker. |
| **WHOIS history** | Current WHOIS is privacy-redacted. On hard/expert, an earlier snapshot captured the registrant email before privacy was switched on. | Historical records beat current ones. |
| **Pivots** | Certificate SAN lists, a shared analytics tracking ID, JARM TLS fingerprint, actor-run nameservers, and the brand favicon hash (shared by *every* kit copying that brand, so it is noisy). | Pivot on strong selectors, distrust weak ones. |
| **Email forensics** | Full `Received:` chain, SPF passing for the attacker's own domain while DMARC fails for the spoofed brand, Reply-To mismatch, X-Mailer. On hard, the origin hop is a Tor/VPN exit (dead end). | Read headers, not the display name. |
| **Commodity malware** | On hard, the malware family is sold to many actors, and each has historic campaigns using it. | Malware alone does not attribute. |
| **Vendor naming chaos** | The same actor is `GLASS HERON`, `TA-417`, and `Silent Ledger` depending on the source. Reports use a non-primary alias. | Resolve aliases in the Directory. |
| **Source reliability** | Every fact has a source with an Admiralty grade (A–F) and a credibility score (1–6). | Weigh evidence instead of counting it. |
| **False flags** | Planted strings and YARA hits naming another actor, plus D/E-grade blogs blaming them. | Separate claims from infrastructure overlap. |
| **Shared hosting** | A *different* actor's phishing site lives on the same bulletproof IP during the incident. | Co-location is not attribution. |
| **Unmasking** (hard/expert) | Registrant email → breach corpus → forum persona → same handle elsewhere → real person. There is also a look-alike handle belonging to someone else, and people can share names. | OPSEC-failure chaining without jumping to conclusions. |

Freshly generated attacker infrastructure is labelled `unknown` or `suspicious`
on hard/expert, not `malicious`. Real threat-intel platforms rarely flag new
infrastructure in time, so the player can't just look for red labels.

All knobs live in the `difficulty_profiles` **table**, so you can tune difficulty
with an `UPDATE` instead of a code change.

## Scoring (server/scoring.py)

A correct answer is not enough. `reachable_evidence()` is a **recursive CTE**
that walks the player's evidence board from the initial clue. DNS edges only
count if they were live within ±2 days of the incident. The grader applies:

- points per correct conclusion: actor, campaign, primary domain, origin IP, and person on hard+
- −10% for each correct conclusion the evidence doesn't actually connect to
- −5% for each red herring or false-flag item used as support
- −15% per previous wrong submission, plus hint costs
- on hard/expert, a wrong report only says *how many* fields were right

`case_is_solvable()` is the oracle `make test` uses to prove every generated
case can be solved.

## Schema in one picture

```mermaid
erDiagram
  entities ||--o| domains : "is-a"
  entities ||--o| ip_addresses : "is-a"
  entities ||--o| certificates : "is-a"
  entities ||--o| whois_records : "is-a"
  entities ||--o| malware_samples : "is-a"
  entities ||--o| threat_actors : "is-a"
  entities ||--o| personas : "is-a"
  entities ||--o{ entity_relationships : "src"
  entities ||--o{ entity_relationships : "dst"
  sources ||--o{ entity_relationships : "reported by"
  cases ||--o{ entities : "case-scoped rows"
  cases ||--o{ case_entities : "hidden roles"
  cases ||--|| case_ground_truth : "answer"
  cases ||--o{ case_evidence : "player board"
  cases ||--o{ query_log : "every search"
  threat_actors ||--o{ actor_aliases : "named by vendors"
```

This is a supertype/subtype design (`entities` plus 23 subtype tables). It means
the single generalized `entity_relationships` table (research question 1) still
has **real foreign keys on both ends**, which a polymorphic `(type, id)` link
table can't have. That tradeoff belongs in the paper.

## Research hooks (question 2)

`query_log` records every search a player runs, how many results came back,
and which hidden roles those results contained (chain, red herring, false
flag…). The view `v_player_paths` orders it into a step-by-step trail per case.
From it you can measure how often players get misled by red herrings, how long
they take to reach the chain, how hints change their path, and how accuracy
differs across difficulties.

## Ethics / safety of the fake data

IPs come only from reserved ranges (198.18.0.0/15 per RFC 2544, 192.0.2.0/24
and 203.0.113.0/24 per RFC 5737). Every domain ends in `.example` or `.test`
(RFC 2606). Brands, vendors, malware, and actors are invented. Nothing in the
game points at a real server, company, or person.

## Adding a scenario

Create a `Scenario` subclass in `server/generator/scenarios/` that overrides `build()`,
using the shared builders in `base.py` (`site()`, `attribution()`, `unmask()`,
`email_msg()`, `persona()`, `image()`, `document()`, `audio()`, `phone()`, `payment()`,
`wallet()`, `money_trail` data, `complaints()`, ...). Declare its `report_fields`, register
it in `registry.py`, and it joins `make test` automatically. New `entity_kind` / `rel_type`
values go in a new migration (`alter type ... add value`).
