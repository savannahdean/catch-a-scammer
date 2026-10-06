# Catch-a-Scammer — realistic OSINT backend (PostgreSQL)

```
raylib C++ client  ──HTTP/JSON──▶  FastAPI (server/)  ──SQL──▶  PostgreSQL (Docker)
  client/src/net/ApiClient            case generator,            schema, search functions,
  (drop into your UI)                 tools, scoring             recursive chain validation
```

The client never sees the database password or the answer tables. Every table
also has row-level security on with no policies, so only the server's own
connection can read them.

## Quick start

```bash
docker compose up -d      # local Postgres 16 on :5432 (needs Docker Desktop running)
make setup                # venv, C++ headers, creates .env (already points at the Docker DB)
make db-migrate           # apply all migrations (tracked, idempotent)
make db-seed              # the persistent "world" (~1,500 entities)
make test                 # generates 12 cases, verifies each is solvable, grades answers
make server               # API on :8000   (leave running)
make smoke                # terminal game: ./build/api_smoke <difficulty> [scenario]
make client               # your raylib game
```

Without `make` (plain Windows PowerShell), from this `backend/` folder:

```powershell
docker compose up -d
copy .env.example .env
python -m venv .venv
.venv\Scripts\python -m pip install -r server\requirements.txt
$env:DATABASE_URL = "postgresql://cas:cas@localhost:5432/osint"
.venv\Scripts\python scripts\migrate.py
.venv\Scripts\python -m server.generator.world
.venv\Scripts\python -m uvicorn server.app:app --port 8000      # leave running
# in a second terminal (set DATABASE_URL there too):
$env:API_URL = "http://127.0.0.1:8000"; .venv\Scripts\python scripts\playtest.py 1
```

The `supabase/` folder name is historical; the migrations are plain PostgreSQL.

Put the Kaggle file at `data/osint_public_profiles_dataset.csv` before `make db-seed`
and the Directory is filled from it (names, usernames, companies only; its IPs and
domains are ignored on purpose because they could be real).

## Scam scenarios

The game ships **11 scam types**, picked at case creation (`scenario` in `POST /cases`,
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

At `hard`/`expert` every scenario also requires unmasking the **real person** behind the
operation (leaked email → breach corpus → forum persona → social handle → identity), with a
look-alike handle planted to punish jumping to conclusions.

Adding scam #12 is one class in `server/generator/scenarios/` plus a line in
`registry.py`; the tools, graph, scoring, and logging all work unchanged.

## The desktop client (`/api`, server/compat.py + server/cards.py)

The raylib game in the repo's top-level `client/` talks only to the `/api/...`
routes. It uses **integer** ids (the `seq` identity column every case and
entity gets on creation, next to its UUID) and is a thin renderer: it holds no game
data and no answer key. Run it against this server:

```
./catch-a-scammer --api http://127.0.0.1:8000
```

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
| (any) | `card/{n}` | one record, for links between tools |
| (all) | `GET/POST/DELETE cases/{n}/evidence` | the evidence board |

**You can only name what you found.** Every record a tool shows is written to
`case_discoveries`. The Case Report offers, for each field, only entities of that
kind the player has surfaced, and pinning requires discovery too. That table is
also research data (`v_discovery_timeline`: when each player first saw each part
of the answer and each decoy).

**Every scenario is proven solvable through the client.** `make test` includes a
bot that starts from the exhibits and may only follow what the client's screens
offer (card rows, record buttons, and names it reads in text). It must surface
every answer slot, pin the chain, and get a correct grade, for all 11 scenarios
at easy and hard (hard includes unmasking the real person).

Every search still writes to `query_log`, so the research data is the same
whichever client is used.

## The terminal smoke client (backend/client)

`backend/client/` holds a separate C++ `ApiClient` for the native, UUID API
(un-prefixed routes) and the terminal tool `make smoke` builds from it.

### Using ApiClient in another frontend

Copy your UI sources into `client/src/` next to `net/`. The Makefile compiles
every `.cpp` under `client/src`. If you keep your own Makefile instead, add:

- `-Iclient/src -Iclient/vendor` to the compile flags
- `client/src/net/ApiClient.cpp` to the sources
- `-pthread` (Linux/macOS) or `-lws2_32 -lcrypt32` (Windows) to the link flags

Include only `net/ApiClient.hpp` from UI code. It never includes `httplib.h`,
which on Windows drags in `<windows.h>` and collides with raylib's
`CloseWindow`, `DrawText`, and `Rectangle`.

| In-game app      | ApiClient call                                  |
|------------------|-------------------------------------------------|
| CaseDesk         | `newCase`, `caseInfo`, `email`                  |
| IntelSearch      | `search`, `entity`                              |
| DNS History      | `pdns`                                          |
| WHOIS History    | `whois`                                         |
| CertSearch       | `certSearch`                                    |
| URL Scanner      | `urlScan`, `pivot`                              |
| MalwareDB        | `malware`                                       |
| Breach Lookup    | `breach`                                        |
| WebSearch        | `webSearch`                                     |
| Directory        | `directory`                                     |
| Reverse Image    | `reverseImage` (romance, pig-butchering)        |
| Money Trail      | `moneyTrail` (BEC, romance, tech-support, crypto) |
| Social           | `social` (posts / DMs by text or handle)        |
| Phone Lookup     | `phone` (carrier, line type, spam reports)      |
| SMS              | `sms` (smishing messages)                       |
| Document Lab     | `document` + `entity` (metadata exposes forgers)|
| Audio Lab        | `audio` (voiceprint, synthetic score)           |
| Payment          | `payment` (mule accounts, gift cards, wallets)  |
| Complaints       | `complaints` (other victims' reports)           |
| Evidence Map     | `graph`, `evidence`, `addEvidence`              |
| Case Report      | `hint`, `submit`, `debrief`                      |
| (meta)           | `scenarios` (list scam types + report fields)   |

Use `api.async(...)` with `cas::Pending` and `poll()` once per frame so the
window shows "Querying…" instead of freezing (example at the bottom of
`ApiClient.hpp`).

## What makes it realistic (and hard)

Each item below is a real analyst skill the player has to use.

| Layer | What the data does | Skill it forces |
|---|---|---|
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
