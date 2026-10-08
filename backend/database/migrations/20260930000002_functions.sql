-- =====================================================================
-- Tool back-ends as SQL functions. Each in-game app maps to one of these.
-- Every function is "case scoped": it sees world rows (case_id IS NULL)
-- plus rows generated for the given case, never another player's case.
-- =====================================================================
set search_path = public, extensions;

-- What a case is allowed to see -----------------------------------------
create or replace function visible_entities(p_case uuid)
returns setof entities
language sql stable
set search_path = public, extensions
as $$
  select * from entities where case_id is null or case_id = p_case;
$$;

create or replace function visible_edges(p_case uuid)
returns setof entity_relationships
language sql stable
set search_path = public, extensions
as $$
  select * from entity_relationships where case_id is null or case_id = p_case;
$$;

-- IntelSearch: fuzzy lookup across every entity kind ---------------------
-- Exact hits first, then trigram similarity. Deliberately returns noise:
-- typing "secure-login" surfaces every lookalike, benign or not.
create or replace function intel_search(p_case uuid, p_query text, p_limit int default 25)
returns table (entity_id uuid, kind entity_kind, value text, label text,
               verdict verdict, score real)
language sql stable
set search_path = public, extensions
as $$
  select e.id, e.kind, e.value::text, e.label, e.verdict,
         case when e.value = p_query::citext then 2.0
              when e.value::text ilike '%' || p_query || '%' then 1.0 + similarity(e.value::text, p_query)
              else similarity(e.value::text, p_query) end::real as score
  from visible_entities(p_case) e
  where e.kind not in ('whois_record','url_scan','email_message')   -- those have their own tools
    and (e.value::text ilike '%' || p_query || '%' or similarity(e.value::text, p_query) > 0.3)
  order by score desc, e.kind
  limit p_limit;
$$;

-- Passive DNS: works in both directions, returns the time windows ------
create or replace function pdns(p_case uuid, p_value text)
returns table (domain text, ip text, first_seen timestamptz, last_seen timestamptz,
               source text, confidence smallint)
language sql stable
set search_path = public, extensions
as $$
  select d.value::text, i.value::text, lower(r.valid), upper(r.valid), s.name, r.confidence
  from visible_edges(p_case) r
  join entities d on d.id = r.src_id
  join entities i on i.id = r.dst_id
  left join sources s on s.id = r.source_id
  where r.rel = 'resolves_to'
    and (d.value = p_value::citext or i.value = p_value::citext)
    and (d.case_id is null or d.case_id = p_case)
    and (i.case_id is null or i.case_id = p_case)
  order by lower(r.valid) desc nulls last;
$$;

-- Certificate transparency search (by any SAN or CN, substring) ---------
create or replace function ct_search(p_case uuid, p_query text)
returns table (entity_id uuid, sha256 text, issuer text, subject_cn text,
               san text[], not_before timestamptz, not_after timestamptz, self_signed boolean)
language sql stable
set search_path = public, extensions
as $$
  select e.id, c.sha256::text, c.issuer_cn, c.subject_cn, c.san, c.not_before, c.not_after, c.self_signed
  from visible_entities(p_case) e
  join certificates c on c.entity_id = e.id
  where c.subject_cn ilike '%' || p_query || '%'
     or exists (select 1 from unnest(c.san) s where s ilike '%' || p_query || '%')
     or c.sha256 = lower(p_query)
  order by c.not_before desc;
$$;

-- Reverse pivots: "who else uses this tracking ID / favicon / nameserver"
create or replace function pivot(p_case uuid, p_field text, p_value text)
returns table (entity_id uuid, kind entity_kind, value text, detail text)
language plpgsql stable
set search_path = public, extensions
as $$
begin
  if p_field = 'tracking_id' then
    return query
      select e.id, e.kind, e.value::text, u.scanned_url || '  (' || coalesce(u.page_title,'') || ')'
      from visible_entities(p_case) e join url_scans u on u.entity_id = e.id
      where p_value = any(u.tracking_ids);
  elsif p_field = 'favicon' then
    return query
      select e.id, e.kind, e.value::text, u.scanned_url
      from visible_entities(p_case) e join url_scans u on u.entity_id = e.id
      where u.favicon_mmh3::text = p_value;
  elsif p_field = 'jarm' then
    return query
      select e.id, e.kind, e.value::text, coalesce(u.ip_seen::text,'')
      from visible_entities(p_case) e join url_scans u on u.entity_id = e.id
      where u.jarm = p_value;
  elsif p_field = 'nameserver' then
    return query
      select d.id, d.kind, d.value::text, 'uses ' || n.value
      from visible_edges(p_case) r
      join entities d on d.id = r.src_id
      join entities n on n.id = r.dst_id
      where r.rel = 'uses_nameserver' and n.value = p_value::citext;
  elsif p_field = 'registrant_email' then
    return query
      select e.id, e.kind, e.value::text, w.domain_fqdn || ' @ ' || w.captured_at::date
      from visible_entities(p_case) e join whois_records w on w.entity_id = e.id
      where w.registrant_email ilike p_value;
  elsif p_field = 'imphash' then
    return query
      select e.id, e.kind, e.value::text, coalesce(m.file_name,'')
      from visible_entities(p_case) e join malware_samples m on m.entity_id = e.id
      where m.imphash = lower(p_value);
  else
    raise exception 'unknown pivot field %', p_field;
  end if;
end $$;

-- Evidence Map: expand a node -------------------------------------------
create or replace function neighbors(p_case uuid, p_entity uuid)
returns table (edge_id bigint, direction text, rel rel_type, other_id uuid,
               other_kind entity_kind, other_value text, other_verdict verdict,
               valid_from timestamptz, valid_to timestamptz,
               source text, reliability char(1), confidence smallint)
language sql stable
set search_path = public, extensions
as $$
  select r.id, 'out', r.rel, o.id, o.kind, o.value::text, o.verdict,
         lower(r.valid), upper(r.valid), s.name, s.reliability, r.confidence
  from visible_edges(p_case) r
  join entities o on o.id = r.dst_id and (o.case_id is null or o.case_id = p_case)
  left join sources s on s.id = r.source_id
  where r.src_id = p_entity
  union all
  select r.id, 'in', r.rel, o.id, o.kind, o.value::text, o.verdict,
         lower(r.valid), upper(r.valid), s.name, s.reliability, r.confidence
  from visible_edges(p_case) r
  join entities o on o.id = r.src_id and (o.case_id is null or o.case_id = p_case)
  left join sources s on s.id = r.source_id
  where r.dst_id = p_entity
  order by 3, 6
  limit 200;   -- a CDN IP has hundreds of neighbours; cap like real tools do
$$;

-- ---------------------------------------------------------------------
-- Chain validation (recursive CTE).
-- Treat the player's evidence as a subgraph. Starting at the initial clue,
-- walk edges (either direction) whose BOTH endpoints are in the evidence
-- set. DNS edges only count if they were live around the incident.
-- Returns every evidence entity reachable from the clue.
-- ---------------------------------------------------------------------
create or replace function reachable_evidence(p_case uuid, p_evidence uuid[])
returns table (entity_id uuid, depth int)
language sql stable
set search_path = public, extensions
as $$
  with recursive
  c as (select incident_at from cases where id = p_case),
  ev as (select unnest(p_evidence) as id),
  e as (
    select r.src_id a, r.dst_id b
    from visible_edges(p_case) r, c
    where r.src_id in (select id from ev) and r.dst_id in (select id from ev)
      and (r.rel <> 'resolves_to'
           or r.valid && tstzrange(c.incident_at - interval '2 days', c.incident_at + interval '2 days'))
  ),
  und as (select a, b from e union select b, a from e),
  walk(id, depth, path) as (
    select ce.entity_id, 0, array[ce.entity_id]
    from case_entities ce
    where ce.case_id = p_case and ce.role = 'initial_clue'
    union all
    select u.b, w.depth + 1, w.path || u.b
    from walk w join und u on u.a = w.id
    where not u.b = any(w.path) and w.depth < 20
  )
  select id, min(depth) from walk group by id;
$$;

-- Oracle used by `make test`: can the true answer be reached using only
-- entities the generator marked chain/supporting? If not, the case is broken.
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
  select bool_and(t in (select entity_id from r))
  from case_ground_truth g,
       unnest(array[g.actor_id, g.campaign_id, g.primary_domain_id, g.origin_ip_id]
              || case when g.person_id is null then '{}'::uuid[] else array[g.person_id] end) t
  where g.case_id = p_case;
$$;

-- Research view: how did players move through a case? --------------------
create or replace view v_player_paths with (security_invoker = true) as
select q.case_id, c.difficulty, q.tool, q.query, q.result_count, q.hit_roles, q.at,
       row_number() over (partition by q.case_id order by q.at) as step
from query_log q join cases c on c.id = q.case_id;
