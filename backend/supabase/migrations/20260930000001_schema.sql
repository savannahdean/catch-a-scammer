-- =====================================================================
-- Catch-a-Scammer :: realistic OSINT schema (PostgreSQL 15+)
-- ---------------------------------------------------------------------
-- Design in one paragraph:
--   * Every investigable "thing" is a row in ENTITIES (supertype).
--     Kind-specific data lives in 1:1 subtype tables (domains, ip_addresses,
--     certificates, ...). This lets ENTITY_RELATIONSHIPS stay a single
--     generalized edge table (research question 1) while still having
--     REAL foreign keys on both ends, which a plain polymorphic
--     (type, id) link table cannot have.
--   * Edges carry a VALID-TIME range, a SOURCE (with Admiralty-code
--     reliability) and a CONFIDENCE. Real OSINT is time-bounded and
--     contradictory, so the player must reason about "when" and "who says".
--   * WORLD rows have case_id NULL and are shared by every case (big cloud
--     providers, CDNs, benign domains, known malware families, actors).
--     CASE rows are generated per case and carry case_id.
--   * Ground truth (case_entities.role, case_ground_truth) is never exposed
--     to the client. RLS is ON with no policies, so only the backend
--     (service role / direct connection) can read anything.
-- =====================================================================

create schema if not exists extensions;
create extension if not exists pg_trgm   with schema extensions;
create extension if not exists citext    with schema extensions;
create extension if not exists btree_gist with schema extensions;

set search_path = public, extensions;

-- ---------------------------------------------------------------------
-- Enumerations
-- ---------------------------------------------------------------------
create type entity_kind as enum (
  'domain','ip','asn','hosting_provider','registrar','nameserver',
  'whois_record','certificate','url','url_scan','tracking_id',
  'email_address','email_message','malware_family','malware_sample',
  'campaign','threat_actor','persona','person','organization',
  'crypto_wallet','phone','breach','web_article'
);

create type verdict as enum (
  'malicious','suspicious','benign','compromised','sinkholed','parked','unknown'
);

create type rel_type as enum (
  -- infrastructure
  'resolves_to',        -- domain -> ip           (passive DNS, time-bounded)
  'announced_by',       -- ip -> asn
  'operated_by',        -- asn -> hosting_provider
  'registered_via',     -- domain -> registrar
  'uses_nameserver',    -- domain -> nameserver
  'has_whois',          -- domain -> whois_record (historical snapshots)
  'registrant_email',   -- whois_record -> email_address
  'cert_covers',        -- certificate -> domain  (SAN list)
  'redirects_to',       -- url/domain -> url/domain
  'hosts_url',          -- domain -> url
  'scanned_as',         -- url -> url_scan
  'embeds_tracking_id', -- url_scan -> tracking_id
  -- email
  'sent_from_ip',       -- email_message -> ip (first external Received hop)
  'envelope_from',      -- email_message -> email_address (Return-Path)
  'reply_to',           -- email_message -> email_address
  'contains_link',      -- email_message -> url
  -- malware
  'serves_payload',     -- url -> malware_sample
  'sample_of',          -- malware_sample -> malware_family
  'c2_contact',         -- malware_sample -> ip/domain (from config/sandbox)
  'used_in',            -- malware_family/sample/domain -> campaign
  -- attribution
  'attributed_to',      -- campaign -> threat_actor
  'alias_of',           -- persona -> threat_actor
  'uses_email',         -- persona/person -> email_address
  'same_username',      -- persona <-> persona (handle reuse across platforms)
  'leaked_in',          -- email_address -> breach
  'identified_as',      -- persona -> person (OPSEC failure)
  'employed_by',        -- person -> organization
  'receives_funds',     -- persona/actor -> crypto_wallet
  'mentions'            -- web_article -> anything
);

create type case_role as enum (
  'initial_clue',   -- what the player is handed
  'chain',          -- on the true path
  'supporting',     -- true but not required
  'red_herring',    -- looks relevant, is not
  'false_flag',     -- deliberately planted to mislead attribution
  'noise'           -- background world data that surfaces in results
);

create type difficulty as enum ('easy','medium','hard','expert');
create type case_status as enum ('open','solved','failed','abandoned');

-- ---------------------------------------------------------------------
-- Sources: where a fact came from. Admiralty/NATO system:
--   reliability A (completely reliable) .. F (cannot be judged)
--   credibility 1 (confirmed) .. 6 (cannot be judged) -- stored per edge
-- ---------------------------------------------------------------------
create table sources (
  id           smallserial primary key,
  name         text not null unique,
  source_type  text not null check (source_type in
                 ('passive_dns','whois','ct_log','sandbox','url_scanner',
                  'vendor_report','news','blog','forum','paste','breach_corpus',
                  'internal','victim_report')),
  reliability  char(1) not null check (reliability in ('A','B','C','D','E','F')),
  description  text
);

-- ---------------------------------------------------------------------
-- Cases (declared early because entities reference them)
-- ---------------------------------------------------------------------
create table cases (
  id            uuid primary key default gen_random_uuid(),
  case_code     text not null unique,              -- e.g. CASE-2026-0412
  scenario      text not null,                      -- 'credential_phish', 'bec', ...
  difficulty    difficulty not null,
  rng_seed      bigint not null,                    -- reproducible generation
  incident_at   timestamptz not null,               -- when the victim clicked
  reported_at   timestamptz not null,
  victim_name   text not null,
  victim_org    text not null,
  victim_role   text not null,
  briefing      text not null,
  status        case_status not null default 'open',
  attempts      smallint not null default 0,
  hints_used    smallint not null default 0,
  score         integer,
  player_id     uuid,                               -- auth.users.id if you add login
  created_at    timestamptz not null default now(),
  closed_at     timestamptz
);

-- ---------------------------------------------------------------------
-- Supertype
-- ---------------------------------------------------------------------
create table entities (
  id          uuid primary key default gen_random_uuid(),
  kind        entity_kind not null,
  value       citext not null,          -- canonical searchable value
  label       text,                     -- pretty display
  verdict     verdict not null default 'unknown',
  case_id     uuid references cases(id) on delete cascade,  -- NULL = world
  tags        text[] not null default '{}',
  created_at  timestamptz not null default now()
);
-- same value may exist once in the world and once per case
create unique index entities_world_uq on entities(kind, value) where case_id is null;
create unique index entities_case_uq  on entities(case_id, kind, value) where case_id is not null;
create index entities_value_trgm on entities using gin (value gin_trgm_ops);
create index entities_case_idx   on entities(case_id);

-- ---------------------------------------------------------------------
-- Subtypes (1:1 with entities, PK = FK)
-- ---------------------------------------------------------------------
create table hosting_providers (
  entity_id     uuid primary key references entities(id) on delete cascade,
  name          text not null,
  country       char(2) not null,
  provider_type text not null check (provider_type in
                  ('hyperscale_cloud','cdn','vps','shared_hosting','bulletproof','residential_isp','university','enterprise')),
  abuse_email   text,
  abuse_responsiveness text not null default 'normal'
                  check (abuse_responsiveness in ('fast','normal','slow','ignores'))
);

create table asns (
  entity_id   uuid primary key references entities(id) on delete cascade,
  asn         integer not null,
  as_name     text not null,
  country     char(2) not null
);

create table ip_addresses (
  entity_id     uuid primary key references entities(id) on delete cascade,
  addr          inet not null,
  prefix        cidr not null,                    -- announced block
  country       char(2) not null,
  region        text,
  city          text,
  geo_accuracy_km integer not null default 50,    -- GeoIP is approximate!
  is_tor_exit   boolean not null default false,
  is_vpn        boolean not null default false,
  is_cdn        boolean not null default false,
  reverse_dns   text,
  open_ports    integer[] not null default '{}',
  banner        text
);
create index ip_addr_gist on ip_addresses using gist (addr inet_ops);

create table registrars (
  entity_id   uuid primary key references entities(id) on delete cascade,
  name        text not null,
  iana_id     integer,
  privacy_default boolean not null default false
);

create table nameservers (
  entity_id   uuid primary key references entities(id) on delete cascade,
  host        text not null
);

create table domains (
  entity_id       uuid primary key references entities(id) on delete cascade,
  fqdn            citext not null,
  registered_domain citext not null,             -- eTLD+1
  created_on      date,
  expires_on      date,
  is_typosquat_of text,                          -- brand it imitates, if any
  is_dga          boolean not null default false,
  popularity_rank integer                        -- Tranco-like rank; null = unranked
);

create table whois_records (
  entity_id         uuid primary key references entities(id) on delete cascade,
  domain_fqdn       citext not null,
  captured_at       timestamptz not null,        -- historical snapshots!
  registrar_name    text,
  created_on        date,
  updated_on        date,
  expires_on        date,
  registrant_name   text,
  registrant_org    text,
  registrant_email  text,
  registrant_phone  text,
  registrant_country char(2),
  privacy_service   text,                        -- non-null = redacted
  name_servers      text[] not null default '{}',
  status_codes      text[] not null default '{}',
  raw_text          text not null
);

create table certificates (
  entity_id     uuid primary key references entities(id) on delete cascade,
  sha256        char(64) not null,
  serial        text not null,
  issuer_cn     text not null,
  issuer_org    text,
  subject_cn    text not null,
  san           text[] not null,
  not_before    timestamptz not null,
  not_after     timestamptz not null,
  self_signed   boolean not null default false,
  ct_log        text,
  logged_at     timestamptz
);
create index cert_san_gin on certificates using gin (san);

create table urls (
  entity_id     uuid primary key references entities(id) on delete cascade,
  full_url      text not null,
  host          citext not null,
  path          text not null default '/'
);

create table url_scans (
  entity_id       uuid primary key references entities(id) on delete cascade,
  scanned_url     text not null,
  scanned_at      timestamptz not null,
  final_url       text,
  http_status     smallint,
  page_title      text,
  server_header   text,
  ip_seen         inet,
  favicon_mmh3    integer,                       -- Shodan-style favicon hash
  html_sha256     char(64),
  jarm            char(62),                      -- TLS server fingerprint
  tracking_ids    text[] not null default '{}',  -- analytics/pixel IDs: classic pivot
  kit_indicators  text[] not null default '{}',  -- phishing-kit artifacts
  screenshot_note text
);

create table tracking_ids (
  entity_id  uuid primary key references entities(id) on delete cascade,
  vendor     text not null,        -- 'analytics', 'pixel', 'tagmanager'
  tracking_code text not null
);

create table email_addresses (
  entity_id  uuid primary key references entities(id) on delete cascade,
  address    citext not null,
  provider   text,
  is_disposable boolean not null default false
);

create table email_messages (
  entity_id        uuid primary key references entities(id) on delete cascade,
  message_id       text not null,
  subject          text not null,
  header_from      text not null,               -- display From (spoofable)
  envelope_from    text not null,               -- Return-Path
  reply_to         text,
  to_addr          text not null,
  sent_at          timestamptz not null,
  x_mailer         text,
  spf_result       text not null,
  dkim_result      text not null,
  dmarc_result     text not null,
  received_chain   jsonb not null,              -- array of hops, newest first
  body_text        text not null,
  raw_headers      text not null
);

create table malware_families (
  entity_id       uuid primary key references entities(id) on delete cascade,
  family          text not null,
  malware_type    text not null,
  first_observed  date not null,
  is_commodity    boolean not null default false,  -- sold/leaked => weak attribution
  description     text
);

create table malware_samples (
  entity_id     uuid primary key references entities(id) on delete cascade,
  sha256        char(64) not null,
  sha1          char(40) not null,
  md5           char(32) not null,
  imphash       char(32),
  ssdeep        text,
  file_name     text,
  file_type     text,
  size_bytes    integer,
  first_submitted timestamptz not null,
  av_detections smallint not null,
  av_total      smallint not null,
  yara_hits     text[] not null default '{}',
  strings_of_interest text[] not null default '{}',   -- where false flags hide
  c2_config     jsonb,
  sandbox_verdict text
);

create table campaigns (
  entity_id   uuid primary key references entities(id) on delete cascade,
  name        text not null,
  started_on  date,
  ended_on    date,
  objective   text,
  targeting   text
);

create table threat_actors (
  entity_id     uuid primary key references entities(id) on delete cascade,
  primary_alias text not null,
  motivation    text not null,
  sophistication text not null,
  suspected_origin char(2),
  active_hours_utc int4range,             -- behavioural fingerprint
  notes         text
);

-- vendor naming chaos: same actor, different names from different reporters
create table actor_aliases (
  actor_id    uuid not null references entities(id) on delete cascade,
  alias       citext not null,
  named_by    smallint references sources(id),
  primary key (actor_id, alias)
);

create table personas (
  entity_id   uuid primary key references entities(id) on delete cascade,
  handle      citext not null,
  platform    text not null,              -- forum/market/social
  joined_on   date,
  post_count  integer not null default 0,
  bio         text,
  pgp_fingerprint text,
  language    text,
  utc_offset_guess smallint,              -- inferred from posting times
  last_active timestamptz
);

create table persons (
  entity_id   uuid primary key references entities(id) on delete cascade,
  full_name   text not null,
  city        text,
  country     char(2),
  birth_year  smallint,
  employer    text,
  job_title   text,
  source_row  integer                     -- row in the seed CSV, for traceability
);

create table organizations (
  entity_id   uuid primary key references entities(id) on delete cascade,
  name        text not null,
  sector      text,
  country     char(2)
);

create table crypto_wallets (
  entity_id   uuid primary key references entities(id) on delete cascade,
  chain       text not null,
  address     text not null,
  total_received numeric(20,8) not null default 0,
  tx_count    integer not null default 0
);

create table breaches (
  entity_id    uuid primary key references entities(id) on delete cascade,
  breach_name  text not null,
  breach_date  date not null,
  records      integer not null,
  data_classes text[] not null
);

-- per-identity record inside a breach corpus
create table breach_records (
  id             bigserial primary key,
  breach_id      uuid not null references entities(id) on delete cascade,
  email          citext,
  username       citext,
  display_name   text,
  password_hash  text,
  hash_type      text,
  signup_ip      inet,
  case_id        uuid references cases(id) on delete cascade
);
create index breach_records_email on breach_records(email);
create index breach_records_user  on breach_records(username);

create table web_articles (
  entity_id     uuid primary key references entities(id) on delete cascade,
  publisher     text not null,
  author        text,
  title         text not null,
  published_at  timestamptz not null,
  body          text not null,
  source_id     smallint references sources(id)
);
create index web_articles_fts on web_articles
  using gin (to_tsvector('english', title || ' ' || body));

-- ---------------------------------------------------------------------
-- THE generalized edge table (research question 1)
-- ---------------------------------------------------------------------
create table entity_relationships (
  id          bigserial primary key,
  src_id      uuid not null references entities(id) on delete cascade,
  dst_id      uuid not null references entities(id) on delete cascade,
  rel         rel_type not null,
  valid       tstzrange not null default tstzrange(null, null),  -- when it was true
  source_id   smallint references sources(id),
  confidence  smallint not null default 3 check (confidence between 1 and 6), -- Admiralty credibility
  case_id     uuid references cases(id) on delete cascade,     -- NULL = world fact
  note        text,
  check (src_id <> dst_id)
);
create index rel_src   on entity_relationships(src_id, rel);
create index rel_dst   on entity_relationships(dst_id, rel);
create index rel_case  on entity_relationships(case_id);
create index rel_valid on entity_relationships using gist (valid);

-- ---------------------------------------------------------------------
-- Hidden per-case answer data
-- ---------------------------------------------------------------------
create table case_entities (
  case_id    uuid not null references cases(id) on delete cascade,
  entity_id  uuid not null references entities(id) on delete cascade,
  role       case_role not null,
  hop        smallint,             -- position on the true chain
  explanation text,               -- shown after the case closes
  primary key (case_id, entity_id)
);

create table case_ground_truth (
  case_id            uuid primary key references cases(id) on delete cascade,
  actor_id           uuid not null references entities(id),
  campaign_id        uuid not null references entities(id),
  primary_domain_id  uuid not null references entities(id),
  origin_ip_id       uuid not null references entities(id),
  malware_family_id  uuid references entities(id),
  person_id          uuid references entities(id),   -- required on hard/expert
  resolution_text    text not null
);

create table case_hints (
  case_id   uuid not null references cases(id) on delete cascade,
  step      smallint not null,
  hint      text not null,
  cost      smallint not null default 50,
  primary key (case_id, step)
);

-- ---------------------------------------------------------------------
-- Player activity (also your research data for question 2)
-- ---------------------------------------------------------------------
create table case_evidence (
  case_id    uuid not null references cases(id) on delete cascade,
  entity_id  uuid not null references entities(id) on delete cascade,
  added_at   timestamptz not null default now(),
  note       text,
  primary key (case_id, entity_id)
);

create table query_log (
  id          bigserial primary key,
  case_id     uuid not null references cases(id) on delete cascade,
  tool        text not null,
  query       text not null,
  result_count integer not null,
  hit_roles   case_role[] not null default '{}',  -- what KIND of stuff they found
  at          timestamptz not null default now()
);

create table submissions (
  id          bigserial primary key,
  case_id     uuid not null references cases(id) on delete cascade,
  submitted_at timestamptz not null default now(),
  answer      jsonb not null,
  evidence    uuid[] not null,
  correct     boolean not null,
  score       integer not null,
  breakdown   jsonb not null
);

-- ---------------------------------------------------------------------
-- Tunable difficulty (data, not code)
-- ---------------------------------------------------------------------
create table difficulty_profiles (
  level                 difficulty primary key,
  sibling_domains       int  not null,  -- actor domains beyond the primary
  shared_hosting_noise  int  not null,  -- benign co-hosted domains per IP
  cdn_front_prob        real not null,  -- primary hidden behind a CDN
  whois_privacy_prob    real not null,
  stale_dns_traps       int  not null,  -- past/future resolutions outside the incident window
  compromised_redirector boolean not null,
  commodity_malware     boolean not null, -- family shared by several actors
  false_flag            boolean not null,
  decoy_actor_articles  int  not null,   -- low-reliability blog posts blaming someone else
  require_person        boolean not null,
  max_hints             int  not null,
  base_score            int  not null
);

insert into difficulty_profiles values
  ('easy',   1, 2,  0.0, 0.3, 0, false, false, false, 0, false, 5, 1000),
  ('medium', 2, 5,  0.2, 0.6, 1, true,  false, false, 1, false, 4, 1500),
  ('hard',   3, 10, 0.5, 0.8, 2, true,  true,  true,  2, true,  3, 2500),
  ('expert', 4, 18, 0.8, 1.0, 3, true,  true,  true,  3, true,  2, 4000);

-- ---------------------------------------------------------------------
-- Lock everything down: Supabase exposes public via PostgREST.
-- RLS on + no policies = anon/authenticated keys read nothing.
-- The FastAPI server connects with the DB connection string (bypasses RLS).
-- ---------------------------------------------------------------------
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;
