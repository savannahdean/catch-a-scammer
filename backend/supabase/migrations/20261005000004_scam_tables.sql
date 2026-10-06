-- =====================================================================
-- Multi-scenario expansion, part 2: artifact tables, scenario catalog,
-- generic answer slots, and the new tool functions.
-- =====================================================================
set search_path = public, extensions;

-- new kinds of sources (reverse image engines, carrier lookups, complaint portals, chains)
alter table sources drop constraint if exists sources_source_type_check;
alter table sources add constraint sources_source_type_check check (source_type in
  ('passive_dns','whois','ct_log','sandbox','url_scanner','vendor_report','news','blog','forum',
   'paste','breach_corpus','internal','victim_report','reverse_image','carrier_lookup',
   'complaint_portal','social_platform','blockchain','audio_lab','document_lab'));

-- richer social accounts (impostor support accounts, dating profiles, recruiters)
alter table personas
  add column if not exists display_name       text,
  add column if not exists verified           boolean not null default false,
  add column if not exists previous_handles   text[]  not null default '{}',
  add column if not exists follower_count     integer not null default 0,
  add column if not exists claimed_location   text,
  add column if not exists claimed_occupation text,
  add column if not exists account_created    timestamptz;

-- visual fingerprints for clone detection
alter table url_scans
  add column if not exists phash        char(16),   -- perceptual hash of the screenshot
  add column if not exists visual_match text;       -- "97% match to parcelpost.example/track"

create table if not exists images (
  entity_id      uuid primary key references entities(id) on delete cascade,
  phash          char(16) not null,           -- perceptual hash: survives resizing/recompression
  width          integer,
  height         integer,
  exif_camera    text,                        -- usually stripped by platforms; sometimes not
  exif_taken_at  timestamptz,
  exif_location  text,
  synthetic_score real,                       -- 0..1 likelihood the face is AI-generated
  description    text not null
);
create index if not exists images_phash on images(phash);

create table if not exists social_posts (
  entity_id       uuid primary key references entities(id) on delete cascade,
  platform        text not null,
  author_handle   citext not null,
  posted_at       timestamptz not null,
  body            text not null,
  language        text not null default 'en',
  reply_to_handle citext,
  is_direct_message boolean not null default false,
  likes           integer not null default 0
);
create index if not exists social_posts_fts on social_posts using gin (to_tsvector('simple', body));

create table if not exists documents (
  entity_id          uuid primary key references entities(id) on delete cascade,
  file_name          text not null,
  file_type          text not null,
  sha256             char(64) not null,
  size_bytes         integer,
  meta_author        text,                    -- classic OSINT pivot: forgers forget metadata
  meta_last_modified_by text,
  meta_company       text,
  meta_creator_tool  text,
  meta_created       timestamptz,
  meta_modified      timestamptz,
  page_count         smallint,
  text_excerpt       text not null,
  published_url      text                     -- set when the document is public (minutes, reports)
);

create table if not exists audio_recordings (
  entity_id        uuid primary key references entities(id) on delete cascade,
  recording_type   text not null check (recording_type in ('voicemail','public_talk','call_recording')),
  duration_s       integer not null,
  recorded_at      timestamptz not null,
  caller_id        text,                      -- what the victim's phone displayed (spoofable)
  stir_shaken      char(1),                   -- A full, B partial, C gateway attestation
  speaker_claimed  text,
  synthetic_score  real,                      -- deepfake detector output, 0..1
  voiceprint_hash  char(32),                  -- speaker-embedding fingerprint
  transcript       text not null,
  source_url       text,
  analysis_note    text
);

create table if not exists sms_messages (
  entity_id    uuid primary key references entities(id) on delete cascade,
  from_number  text not null,
  to_number    text not null,
  sent_at      timestamptz not null,
  body         text not null,
  language     text not null,
  style_notes  text,                          -- dialect / register the lure imitates
  channel      text not null default 'SMS'    -- SMS, iMessage, RCS, WhatsApp
);

create table if not exists phone_numbers (
  entity_id     uuid primary key references entities(id) on delete cascade,
  e164          text not null,
  country       char(2) not null,
  line_type     text not null check (line_type in ('mobile','landline','voip','toll_free','short_code')),
  carrier       text,
  cnam          text,                         -- caller-ID name on file
  spam_reports  integer not null default 0,
  first_reported date
);

create table if not exists payment_accounts (
  entity_id    uuid primary key references entities(id) on delete cascade,
  method       text not null check (method in ('bank_wire','gift_card','p2p_app','money_transfer','crypto_exchange')),
  provider     text not null,
  identifier   text not null,                 -- masked/fictional: 'GRB ****4417', '$handle', 'card ****2209'
  holder_name  text,
  opened_on    date,
  is_mule      boolean not null default false, -- money mules are usually victims too
  notes        text
);

create table if not exists lure_templates (
  entity_id     uuid primary key references entities(id) on delete cascade,
  template_hash char(32) not null,            -- fuzzy hash of the message skeleton
  theme         text not null,
  locale        text not null,                -- en-US, pt-BR, es-MX ...
  language      text not null,
  cultural_hook text,                         -- holiday, tax season, local payment system ...
  kit_name      text,
  sample_text   text not null
);

create table if not exists complaints (
  entity_id      uuid primary key references entities(id) on delete cascade,
  portal         text not null,
  filed_at       timestamptz not null,
  reporter_region text not null,
  loss_amount    numeric(12,2) not null default 0,
  narrative      text not null,
  indicators     text[] not null default '{}'  -- numbers, wallets, domains the victim listed
);
create index if not exists complaints_ind on complaints using gin (indicators);
create index if not exists complaints_fts on complaints using gin (to_tsvector('english', narrative));

-- generic answers: each scenario declares its own Case Report fields
alter table case_ground_truth
  alter column campaign_id drop not null,
  alter column primary_domain_id drop not null,
  alter column origin_ip_id drop not null,
  add column if not exists answer_slots jsonb not null default '{}';
  -- { "slot_key": {"entity_id": "...", "kind": "domain", "label": "...", "weight": 0.2}, ... }

create table if not exists scenarios (
  key             text primary key,
  title           text not null,
  category        text not null,
  real_world_basis text not null,   -- what real technique this models (cite it in the paper)
  player_skill    text not null,    -- what the case teaches
  report_fields   jsonb not null,   -- [{key,label,kind}] the Case Report form is built from this
  min_difficulty  difficulty not null default 'easy',
  enabled         boolean not null default true
);

-- tables created after the RLS loop in migration 001 need it too
do $$
declare t text;
begin
  for t in select tablename from pg_tables where schemaname = 'public' loop
    execute format('alter table public.%I enable row level security', t);
  end loop;
end $$;

-- ---------------------------------------------------------------------
-- Solvability oracle, generalized to any scenario's answer slots
-- ---------------------------------------------------------------------
create or replace function case_is_solvable(p_case uuid)
returns boolean
language sql stable
set search_path = public, extensions
as $$
  with r as (
    select entity_id from reachable_evidence(
      p_case,
      (select array_agg(entity_id) from case_entities
        where case_id = p_case and role in ('initial_clue','chain','supporting')))
  )
  select coalesce(bool_and((s.value->>'entity_id')::uuid in (select entity_id from r)), false)
  from case_ground_truth g, jsonb_each(g.answer_slots) s
  where g.case_id = p_case;
$$;

-- Reverse image search: every place a picture (or a near-duplicate) appears,
-- oldest first. The oldest sighting is usually the real owner.
create or replace function reverse_image(p_case uuid, p_query text)
returns table (image_id uuid, phash text, description text, seen_on_id uuid, seen_on_kind entity_kind,
               seen_on text, first_seen timestamptz, how text)
language sql stable
set search_path = public, extensions
as $$
  with target as (
    select e.id, i.phash from visible_entities(p_case) e join images i on i.entity_id = e.id
    where e.id::text = p_query or i.phash = lower(p_query) or e.value = p_query::citext
  ),
  near_dups as (   -- near-duplicates: same first 12 hex chars of the perceptual hash
    select e.id, i.phash, i.description from visible_entities(p_case) e join images i on i.entity_id = e.id
    where left(i.phash, 12) in (select left(phash, 12) from target)
  )
  select s.id, s.phash::text, s.description, o.id, o.kind, o.value::text, lower(r.valid),
         case when r.rel = 'uses_image' then 'used as profile/post image' else 'indexed on page' end
  from near_dups s
  join visible_edges(p_case) r on (r.rel = 'uses_image' and r.dst_id = s.id) or (r.rel = 'image_seen_at' and r.src_id = s.id)
  join entities o on o.id = case when r.rel = 'uses_image' then r.src_id else r.dst_id end
  order by lower(r.valid) nulls last;
$$;

-- Money trail: follow pays_to / transfers_to forward from any account (recursive CTE)
create or replace function money_trail(p_case uuid, p_start uuid, p_max_depth int default 6)
returns table (depth int, from_id uuid, from_value text, to_id uuid, to_value text, to_kind entity_kind,
               moved_at timestamptz, note text)
language sql stable
set search_path = public, extensions
as $$
  with recursive t(depth, src, dst, at, note, path) as (
    select 1, r.src_id, r.dst_id, lower(r.valid), r.note, array[r.src_id, r.dst_id]
    from visible_edges(p_case) r
    where r.src_id = p_start and r.rel in ('pays_to','transfers_to')
    union all
    select t.depth + 1, r.src_id, r.dst_id, lower(r.valid), r.note, t.path || r.dst_id
    from t join visible_edges(p_case) r on r.src_id = t.dst and r.rel = 'transfers_to'
    where t.depth < p_max_depth and not r.dst_id = any(t.path)
  )
  select t.depth, t.src, a.value::text, t.dst, b.value::text, b.kind, t.at, t.note
  from t join entities a on a.id = t.src join entities b on b.id = t.dst
  order by t.depth, t.at;
$$;
