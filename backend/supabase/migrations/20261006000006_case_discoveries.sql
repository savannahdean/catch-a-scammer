-- =====================================================================
-- What each player has actually surfaced in a case.
--
-- Every record a tool shows the player is written here once (first tool,
-- first time). The Case Report only offers entities from this table, so a
-- player can name only what they found -- as in a real investigation.
-- It is also research data: which decoys players saw, and when.
-- =====================================================================
set search_path = public, extensions;

-- The desktop client uses integer ids. Each case and entity gets one when it is
-- created (an identity column, i.e. a surrogate key), so serving a record never
-- writes. The old lookup tables allocated ids on read, inside each request's
-- transaction, and two players browsing the same world rows could deadlock.
alter table cases    add column if not exists seq bigint generated always as identity;
alter table entities add column if not exists seq bigint generated always as identity;
create unique index if not exists cases_seq on cases(seq);
create unique index if not exists entities_seq on entities(seq);
drop table if exists compat_case_ids, compat_entity_ids;

create table if not exists case_discoveries (
  case_id    uuid not null references cases(id) on delete cascade,
  entity_id  uuid not null references entities(id) on delete cascade,
  tool       text not null,
  first_seen timestamptz not null default now(),
  primary key (case_id, entity_id)
);
create index if not exists case_discoveries_case on case_discoveries(case_id, first_seen);
alter table case_discoveries enable row level security;

-- research view: when did each player first see each piece of the answer,
-- and the red herrings, relative to opening the case?
create or replace view v_discovery_timeline with (security_invoker = true) as
select d.case_id, c.difficulty, c.scenario, d.tool, e.kind, coalesce(ce.role::text, 'world') as role,
       d.first_seen - c.created_at as after_open
from case_discoveries d
join cases c on c.id = d.case_id
join entities e on e.id = d.entity_id
left join case_entities ce on ce.case_id = d.case_id and ce.entity_id = d.entity_id;
