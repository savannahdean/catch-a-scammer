"""Compatibility API for the raylib desktop client.

The client (client/src) was written against an earlier, phishing-only API with:
  * integer case IDs           (long long caseId)
  * /api/... route prefix      (/api/cases, /api/intel, /api/malware, ...)
  * a flat, denormalised record shape  (domain_name, ip_address, associated_ips…)
  * a fixed Case Report form   (actor / campaign / domain / malware)

The current backend uses UUIDs, un-prefixed routes, and an entity/relationship
model that drives 11 scam scenarios. Rather than rewrite the client, this module
exposes the OLD dialect and translates every call to the new generator, DB and
scoring. The client compiles and runs unchanged.

Mounted by server/app.py. Only the seven original apps are wired here, so this
plays the phishing scenarios end to end (bulk/spear/whaling/clone/angler/
smishing/vishing map cleanly onto domain→IP→malware→campaign→actor). The
non-phishing scams (romance, advance-fee, …) need the new apps and are reached
through the native /cases API, not this shim.

Integer <-> UUID: we keep a per-process table mapping a small int to each case
UUID and each entity UUID, so the client can use `long long` throughout. The
maps live in the DB (compat_ids) so they survive across worker requests.
"""
from __future__ import annotations

import json
import random
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel

from .db import tx
from .generator.registry import generate_case
from . import scoring

router = APIRouter(prefix="/api")

# phishing scenarios play through the 7-app client; "random" among these by default
PHISH_SCENARIOS = ["bulk_phish", "spear_phish", "whaling", "clone_phish",
                   "angler_phish", "smishing", "vishing"]


# --------------------------------------------------------------------------- id maps
def ensure_tables(conn) -> None:
    conn.execute("""create table if not exists compat_case_ids (
                      seq bigint generated always as identity primary key,
                      case_id uuid not null unique)""")
    conn.execute("""create table if not exists compat_entity_ids (
                      seq bigint generated always as identity primary key,
                      entity_id uuid not null unique)""")
    conn.execute("alter table compat_case_ids enable row level security")
    conn.execute("alter table compat_entity_ids enable row level security")


def case_int(conn, case_uuid: UUID) -> int:
    row = conn.execute("""insert into compat_case_ids(case_id) values (%s)
                          on conflict (case_id) do update set case_id=excluded.case_id
                          returning seq""", (case_uuid,)).fetchone()
    return row["seq"]


def case_uuid(conn, n: int) -> UUID:
    row = conn.execute("select case_id from compat_case_ids where seq=%s", (n,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown case")
    return row["case_id"]


def ent_int(conn, entity_uuid: UUID) -> int:
    row = conn.execute("""insert into compat_entity_ids(entity_id) values (%s)
                          on conflict (entity_id) do update set entity_id=excluded.entity_id
                          returning seq""", (entity_uuid,)).fetchone()
    return row["seq"]


def ent_uuid(conn, n: int) -> Optional[UUID]:
    row = conn.execute("select entity_id from compat_entity_ids where seq=%s", (n,)).fetchone()
    return row["entity_id"] if row else None


def iso(dt) -> str:
    return dt.date().isoformat() if isinstance(dt, datetime) else (str(dt) if dt else "")


# --------------------------------------------------------------------------- helpers
def status_of(verdict: str) -> str:
    # client shows MALICIOUS/SUSPICIOUS/CLEAN/UNKNOWN badges
    return {"malicious": "malicious", "compromised": "malicious", "suspicious": "suspicious",
            "benign": "clean", "parked": "clean", "sinkholed": "unknown",
            "unknown": "unknown"}.get(verdict, "unknown")


def case_visible(conn, cid: UUID, eid: UUID) -> dict:
    row = conn.execute("select * from entities where id=%s and (case_id is null or case_id=%s)", (eid, cid)).fetchone()
    if not row:
        raise HTTPException(404, "entity not found")
    return row


def incident_window(conn, cid: UUID):
    r = conn.execute("select incident_at from cases where id=%s", (cid,)).fetchone()
    return r["incident_at"]


# --------------------------------------------------------------------------- case lifecycle
class NewCase(BaseModel):
    model_config = {"extra": "allow"}
    difficulty: str = "medium"
    player: Optional[str] = None


def brief_payload(conn, cid: UUID) -> dict:
    c = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
    if not c:
        raise HTTPException(404, "case not found")
    # entry domain the client can hand to IntelSearch: the primary/look-alike domain
    gt = conn.execute("select answer_slots, resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
    entry = ""
    for key in ("primary_domain", "lookalike_domain", "popup_domain", "fake_platform"):
        slot = (gt["answer_slots"] if gt else {}).get(key)
        if slot:
            entry = conn.execute("select value::text v from entities where id=%s", (UUID(slot["entity_id"]),)).fetchone()["v"]
            break
    if not entry:
        # fall back to the initial clue's first linked domain, else any case domain
        row = conn.execute("""select e.value::text v from entities e where e.case_id=%s and e.kind='domain'
                              order by e.created_at limit 1""", (cid,)).fetchone()
        entry = row["v"] if row else ""
    solved = c["status"] == "solved"
    return {
        "case_id": case_int(conn, cid),
        "case_code": c["case_code"],
        "difficulty": c["difficulty"],
        "scenario": c["scenario"],
        "briefing": c["briefing"],
        "entry_domain": entry,
        "attempts": c["attempts"],
        "hints_used": c["hints_used"],
        "status": c["status"],
        "score": c["score"] or 0,
        "resolution_text": (gt["resolution_text"] if (gt and solved) else ""),
    }


@router.post("/cases")
def new_case(body: NewCase, request: Request):
    with tx() as conn:
        ensure_tables(conn)
        scenario = getattr(body, "scenario", None) or random.choice(PHISH_SCENARIOS)
        if scenario == "random":
            scenario = random.choice(PHISH_SCENARIOS)
        from psycopg.rows import tuple_row, dict_row
        conn.row_factory = tuple_row
        try:
            cid = generate_case(conn, body.difficulty, None, scenario)
        except ValueError as e:
            raise HTTPException(400, str(e))
        finally:
            conn.row_factory = dict_row
        return brief_payload(conn, cid)


@router.get("/cases/{n}")
def get_case(n: int):
    with tx() as conn:
        ensure_tables(conn)
        return brief_payload(conn, case_uuid(conn, n))


# --------------------------------------------------------------------------- record builders
# Each turns an entity (+ its case-scoped relationships) into the flat shape the
# client's rec:: renderers read. All IDs are the integer compat IDs.

def domain_record(conn, cid: UUID, eid: UUID) -> dict:
    e = conn.execute("select * from entities where id=%s", (eid,)).fetchone()
    d = conn.execute("select * from domains where entity_id=%s", (eid,)).fetchone()
    # resolutions live within the incident window -> the "current" IP
    inc = incident_window(conn, cid)
    # order so the resolution LIVE at the time of the incident comes first (that's the
    # one that matters); historical and post-takedown (sinkhole) resolutions follow.
    res = conn.execute("""select i.id, i.value::text ip, lower(r.valid) fs, upper(r.valid) ls,
                                 (r.valid @> %s::timestamptz) live_at_incident
                          from entity_relationships r join entities i on i.id=r.dst_id
                          where r.src_id=%s and r.rel='resolves_to' and (r.case_id is null or r.case_id=%s)
                          order by live_at_incident desc, lower(r.valid) desc nulls last""",
                       (inc, eid, cid)).fetchall()
    assoc, first_seen, last_seen = [], None, None
    for row in res:
        assoc.append({"ip_id": ent_int(conn, row["id"]), "ip_address": row["ip"]})
        if row["fs"] and (first_seen is None or row["fs"] < first_seen):
            first_seen = row["fs"]
        if row["ls"] and (last_seen is None or (row["ls"] and row["ls"] > last_seen)):
            last_seen = row["ls"]
    # malware staged on this domain's URLs
    mw = conn.execute("""select distinct mf.entity_id, mf.family from entities d
                         join entity_relationships hu on hu.src_id=d.id and hu.rel='hosts_url'
                         join entity_relationships sp on sp.src_id=hu.dst_id and sp.rel='serves_payload'
                         join entity_relationships so on so.src_id=sp.dst_id and so.rel='sample_of'
                         join malware_families mf on mf.entity_id=so.dst_id
                         where d.id=%s""", (eid,)).fetchall()
    reg = conn.execute("""select rg.name from entity_relationships r join registrars rg on rg.entity_id=r.dst_id
                          where r.src_id=%s and r.rel='registered_via' limit 1""", (eid,)).fetchone()
    return {
        "domain_id": ent_int(conn, eid),
        "domain_name": e["value"],
        "status": status_of(e["verdict"]),
        "first_seen": iso(first_seen), "last_seen": iso(last_seen) if last_seen else "",
        "registrar": reg["name"] if reg else "",
        "associated_ips": assoc,
        "delivers_malware": [{"malware_id": ent_int(conn, m["entity_id"]), "family_name": m["family"]} for m in mw],
    }


def ip_record(conn, cid: UUID, eid: UUID) -> dict:
    e = conn.execute("select * from entities where id=%s", (eid,)).fetchone()
    ip = conn.execute("select * from ip_addresses where entity_id=%s", (eid,)).fetchone()
    net = conn.execute("""select a.value::text asn, hp.name provider, hp.provider_type, hp.abuse_email
                          from entity_relationships r join entities a on a.id=r.dst_id
                          join entity_relationships r2 on r2.src_id=a.id and r2.rel='operated_by'
                          join hosting_providers hp on hp.entity_id=r2.dst_id
                          where r.src_id=%s and r.rel='announced_by' limit 1""", (eid,)).fetchone()
    rep = "bulletproof" if (net and net["provider_type"] == "bulletproof") else \
          "clean" if e["verdict"] == "benign" else "mixed"
    # domains that resolved here (within window-ish) and malware whose C2 is here
    doms = conn.execute("""select d.id, d.value::text, d.verdict from entity_relationships r
                           join entities d on d.id=r.src_id
                           where r.dst_id=%s and r.rel='resolves_to' and (r.case_id is null or r.case_id=%s)
                           and d.kind='domain' limit 25""", (eid, cid)).fetchall()
    return {
        "ip_id": ent_int(conn, eid),
        "ip_address": e["value"],
        "status": status_of(e["verdict"]),
        "asn": (ip["prefix"] and net["asn"]) if net else "",
        "provider_name": net["provider"] if net else "",
        "provider_reputation": rep,
        "abuse_email": net["abuse_email"] if net else "",
        "country": ip["country"] or "", "region": ip["region"] or "", "city": ip["city"] or "",
        "latitude": 0.0, "longitude": 0.0,
        "related_domains": [{"domain_id": ent_int(conn, d["id"]), "domain_name": d["value"],
                             "status": status_of(d["verdict"])} for d in doms],
        "related_malware": [],
    }


def malware_record(conn, cid: UUID, eid: UUID) -> dict:
    e = conn.execute("select * from entities where id=%s", (eid,)).fetchone()
    f = conn.execute("select * from malware_families where entity_id=%s", (eid,)).fetchone()
    camps = conn.execute("""select c.entity_id, c.name from entity_relationships r
                            join campaigns c on c.entity_id=r.dst_id
                            where r.src_id=%s and r.rel='used_in'""", (eid,)).fetchall()
    infra = conn.execute("""select distinct i.value::text ip from entities s
                            join entity_relationships so on so.dst_id=%s and so.rel='sample_of'
                            join entity_relationships c2 on c2.src_id=so.src_id and c2.rel='c2_contact'
                            join entities i on i.id=c2.dst_id where i.kind='ip' limit 10""", (eid,)).fetchall()
    return {
        "malware_id": ent_int(conn, eid),
        "family_name": f["family"], "name": f["family"],
        "malware_type": f["malware_type"],
        "first_observed": iso(f["first_observed"]),
        "source": "SampleBazaar" if f["is_commodity"] else "Sandboxr",
        "campaigns": [{"campaign_id": ent_int(conn, c["entity_id"]), "name": c["name"]} for c in camps],
        "infrastructure": [{"ip_address": r["ip"]} for r in infra],
    }


def campaign_record(conn, cid: UUID, eid: UUID) -> dict:
    c = conn.execute("select * from campaigns where entity_id=%s", (eid,)).fetchone()
    actors = conn.execute("""select t.primary_alias from entity_relationships r
                             join threat_actors t on t.entity_id=r.dst_id
                             where r.src_id=%s and r.rel='attributed_to'""", (eid,)).fetchall()
    return {
        "campaign_id": ent_int(conn, eid),
        "name": c["name"],
        "description": c["objective"] or "",
        "active_since": iso(c["started_on"]),
        "actors": [{"alias": a["primary_alias"]} for a in actors],
    }


def actor_record(conn, cid: UUID, eid: UUID) -> dict:
    t = conn.execute("select * from threat_actors where entity_id=%s", (eid,)).fetchone()
    camps = conn.execute("""select c.name from entity_relationships r join campaigns c on c.entity_id=r.src_id
                            where r.dst_id=%s and r.rel='attributed_to'""", (eid,)).fetchall()
    doms = conn.execute("""select distinct d.value::text, d.verdict from case_entities ce
                           join entities d on d.id=ce.entity_id
                           where ce.case_id=%s and d.kind='domain' and ce.role in ('chain','supporting') limit 8""", (cid,)).fetchall()
    return {
        "actor_id": ent_int(conn, eid),
        "alias": t["primary_alias"],
        "motivation": t["motivation"],
        "origin_region": t["suspected_origin"] or "",
        "first_attributed": "",
        "notes": t["notes"] or "",
        "campaigns": [{"name": c["name"]} for c in camps],
        "known_domains": [{"domain_name": d["value"], "status": status_of(d["verdict"])} for d in doms],
    }


def person_record(conn, cid: UUID, eid: UUID) -> dict:
    p = conn.execute("select * from persons where entity_id=%s", (eid,)).fetchone()
    br = conn.execute("""select b.breach_name from entity_relationships r
                         join breaches b on b.entity_id=r.dst_id
                         where r.src_id in (select src_id from entity_relationships where dst_id=%s)
                         and r.rel='leaked_in' limit 5""", (eid,)).fetchall()
    return {
        "person_id": ent_int(conn, eid),
        "full_name": p["full_name"],
        "username": "", "email": "",
        "city": p["city"] or "", "country": p["country"] or "",
        "employer": p["employer"] or "", "job_title": p["job_title"] or "",
        "phone": "", "last_ip": "", "mac_address": "",
        "breach_count": len(br),
        "breach_sources": ", ".join(b["breach_name"] for b in br),
        "socials": {},
    }


def article_record(conn, cid: UUID, eid: UUID) -> dict:
    a = conn.execute("""select a.*, s.reliability from web_articles a left join sources s on s.id=a.source_id
                        where a.entity_id=%s""", (eid,)).fetchone()
    reveals = (a["reliability"] in ("A", "B", "C")) if a["reliability"] else False
    return {
        "title": a["title"], "outlet": a["publisher"],
        "published": iso(a["published_at"]), "body": a["body"],
        "reveals_alias": reveals,
    }


RECORD = {"domain": domain_record, "ip": ip_record, "malware_family": malware_record,
          "campaign": campaign_record, "threat_actor": actor_record, "person": person_record,
          "web_article": article_record}
ENVELOPE_KEY = {"domain": "domains", "ip": "ips", "malware_family": "malware",
                "campaign": "campaigns", "threat_actor": "actors", "person": "persons",
                "web_article": "articles"}


# --------------------------------------------------------------------------- search tools
def envelope(conn, cid: UUID, hits: list[tuple[str, UUID]]) -> dict:
    """Group (kind, uuid) hits into the client's envelope shape, deduped, capped."""
    out: dict[str, list] = {}
    seen = set()
    for kind, eid in hits:
        if eid in seen:
            continue
        seen.add(eid)
        key = ENVELOPE_KEY.get(kind)
        if not key:
            continue
        out.setdefault(key, []).append(RECORD[kind](conn, cid, eid))
    return out


@router.get("/intel")
def intel(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        rows = conn.execute("select * from intel_search(%s,%s,30)", (cid, q)).fetchall()
        hits = [(r["kind"], r["entity_id"]) for r in rows if r["kind"] in ("domain", "ip", "malware_family")]
        # log for research data, same as the native API
        conn.execute("""insert into query_log(case_id, tool, query, result_count, hit_roles)
                        select %s,'intelsearch',%s,%s, coalesce(array_agg(distinct role),'{}')
                        from case_entities where case_id=%s and entity_id = any(%s::uuid[])""",
                     (cid, q, len(hits), cid, [h[1] for h in hits]))
        return envelope(conn, cid, hits)


@router.get("/intel/domain/{n}")
def intel_domain(n: int, case_id: int):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        eid = ent_uuid(conn, n)
        if not eid:
            raise HTTPException(404, "unknown entity")
        case_visible(conn, cid, eid)
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'intel.domain','',1,'{}')", (cid,))
        return {"domains": [domain_record(conn, cid, eid)]}


@router.get("/intel/ip/{n}")
def intel_ip(n: int, case_id: int):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        eid = ent_uuid(conn, n)
        if not eid:
            raise HTTPException(404, "unknown entity")
        case_visible(conn, cid, eid)
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'intel.ip','',1,'{}')", (cid,))
        return {"ips": [ip_record(conn, cid, eid)]}


@router.get("/malware")
def malware(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        rows = conn.execute("""select e.id from entities e join malware_families f on f.entity_id=e.id
                               where f.family ilike %s""", (f"%{q}%",)).fetchall()
        hits = [("malware_family", r["id"]) for r in rows]
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'malware',%s,%s,'{}')",
                     (cid, q, len(hits)))
        return envelope(conn, cid, hits)


@router.get("/directory")
def directory(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        actors = conn.execute("""select distinct t.entity_id from threat_actors t
                                 left join actor_aliases a on a.actor_id=t.entity_id
                                 where t.primary_alias ilike %s or a.alias::text ilike %s""",
                              (f"%{q}%", f"%{q}%")).fetchall()
        people = conn.execute("""select e.id from entities e join persons p on p.entity_id=e.id
                                 where (e.case_id is null or e.case_id=%s) and p.full_name ilike %s limit 25""",
                              (cid, f"%{q}%")).fetchall()
        hits = [("threat_actor", r["entity_id"]) for r in actors] + [("person", r["id"]) for r in people]
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'directory',%s,%s,'{}')",
                     (cid, q, len(hits)))
        return envelope(conn, cid, hits)


@router.get("/websearch")
def websearch(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, case_id)
        rows = conn.execute("""select e.id from web_articles a join entities e on e.id=a.entity_id
                               where (e.case_id is null or e.case_id=%s)
                               and (a.title ilike %s or a.body ilike %s
                                    or to_tsvector('english', a.title||' '||a.body) @@ websearch_to_tsquery('english', %s))
                               order by a.published_at desc limit 20""",
                           (cid, f"%{q}%", f"%{q}%", q)).fetchall()
        hits = [("web_article", r["id"]) for r in rows]
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'websearch',%s,%s,'{}')",
                     (cid, q, len(hits)))
        return envelope(conn, cid, hits)


# --------------------------------------------------------------------------- evidence
@router.get("/cases/{n}/evidence")
def list_evidence(n: int):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        rows = conn.execute("""select e.id, e.kind, e.value::text v, coalesce(e.label,e.value::text) label
                               from case_evidence ev join entities e on e.id=ev.entity_id
                               where ev.case_id=%s order by ev.added_at""", (cid,)).fetchall()
        items = [{"evidence_id": ent_int(conn, r["id"]), "entity_kind": r["kind"],
                  "entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in rows]
        return {"items": items}


class PinIn(BaseModel):
    model_config = {"extra": "allow"}
    entity_kind: str
    entity_id: int


@router.post("/cases/{n}/evidence")
def pin(n: int, body: PinIn):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        if conn.execute("select status from cases where id=%s", (cid,)).fetchone()["status"] != "open":
            raise HTTPException(409, "case is closed")
        eid = ent_uuid(conn, body.entity_id)
        if not eid:
            raise HTTPException(409, "not discovered")
        case_visible(conn, cid, eid)
        conn.execute("""insert into case_evidence(case_id, entity_id) values (%s,%s)
                        on conflict do nothing""", (cid, eid))
        return list_evidence.__wrapped__(n) if hasattr(list_evidence, "__wrapped__") else _ev(conn, cid)


def _ev(conn, cid):
    rows = conn.execute("""select e.id, e.kind, coalesce(e.label,e.value::text) label
                           from case_evidence ev join entities e on e.id=ev.entity_id
                           where ev.case_id=%s order by ev.added_at""", (cid,)).fetchall()
    return {"items": [{"evidence_id": ent_int(conn, r["id"]), "entity_kind": r["kind"],
                       "entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in rows]}


@router.delete("/cases/{n}/evidence/{eid}")
def unpin(n: int, eid: int):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        euuid = ent_uuid(conn, eid)
        if euuid:
            conn.execute("delete from case_evidence where case_id=%s and entity_id=%s", (cid, euuid))
        return _ev(conn, cid)


# --------------------------------------------------------------------------- hint
@router.post("/cases/{n}/hint")
def hint(n: int):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        c = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
        mx = conn.execute("select max_hints from difficulty_profiles where level=%s", (c["difficulty"],)).fetchone()["max_hints"]
        if c["status"] != "open" or c["hints_used"] >= mx:
            raise HTTPException(409, "no hints available")
        h = conn.execute("select hint, cost from case_hints where case_id=%s and step=%s",
                         (cid, c["hints_used"] + 1)).fetchone()
        if not h:
            raise HTTPException(409, "no more hints")
        conn.execute("update cases set hints_used=hints_used+1 where id=%s", (cid,))
        return {"body": h["hint"], "penalty_applied": h["cost"]}


# --------------------------------------------------------------------------- report options
@router.get("/cases/{n}/report-options")
def report_options(n: int):
    """The client's Case Report has four dropdowns: actors, campaigns, domains, malware.
    Offer plausible choices (correct answer + decoys) drawn from what's in the case."""
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)

        # case choices (include the true answer) + world decoys so each dropdown is a real
        # decision rather than a single forced pick.
        def opts(subtype_join, label_expr):
            case_rows = conn.execute(f"""select e.id, {label_expr} label from entities e {subtype_join}
                                         where e.case_id=%s order by random() limit 8""", (cid,)).fetchall()
            out = [{"entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in case_rows]
            if len(out) < 4:
                world = conn.execute(f"""select e.id, {label_expr} label from entities e {subtype_join}
                                         where e.case_id is null order by random() limit %s""",
                                     (6 - len(out),)).fetchall()
                out += [{"entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in world]
            random.shuffle(out)
            return out

        actors = conn.execute("""select t.entity_id id, t.primary_alias label from threat_actors t
                                 order by (t.entity_id = (select actor_id from case_ground_truth where case_id=%s)) desc,
                                          random() limit 8""", (cid,)).fetchall()
        actor_opts = [{"entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in actors]
        random.shuffle(actor_opts)
        return {
            "actors": actor_opts,
            "campaigns": opts("join campaigns c on c.entity_id=e.id", "c.name"),
            "domains": opts("join domains d on d.entity_id=e.id", "d.fqdn::text"),
            "malware": opts("join malware_families f on f.entity_id=e.id", "f.family"),
        }


# --------------------------------------------------------------------------- submit
class SubmitIn(BaseModel):
    model_config = {"extra": "allow"}
    actor_id: Optional[int] = None
    campaign_id: Optional[int] = None
    domain_id: Optional[int] = None
    malware_id: Optional[int] = None


# map the client's four fixed fields onto whichever answer slots a scenario uses
CLIENT_FIELD_TO_SLOTS = {
    "actor_id": ["actor"],
    "campaign_id": ["campaign"],
    "domain_id": ["primary_domain", "lookalike_domain", "popup_domain", "fake_platform"],
    "malware_id": ["malware_family"],   # only some scenarios score malware
}


@router.post("/cases/{n}/submit")
def submit(n: int, body: SubmitIn):
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        c = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
        if c["status"] != "open":
            raise HTTPException(409, "case is closed")
        slots = conn.execute("select answer_slots from case_ground_truth where case_id=%s", (cid,)).fetchone()["answer_slots"]

        # translate the client's four int fields to {slot_key: uuid-string} for scoring
        answer: dict[str, str] = {}
        submitted_labels: dict[str, str] = {}
        client = {"actor_id": body.actor_id, "campaign_id": body.campaign_id,
                  "domain_id": body.domain_id, "malware_id": body.malware_id}
        for field, val in client.items():
            if val is None:
                continue
            euuid = ent_uuid(conn, val)
            if not euuid:
                continue
            lab = conn.execute("select coalesce(label,value::text) l from entities where id=%s", (euuid,)).fetchone()
            submitted_labels[field] = lab["l"] if lab else ""
            for slot in CLIENT_FIELD_TO_SLOTS[field]:
                if slot in slots:
                    answer[slot] = str(euuid)
                    break

        # evidence = whatever the player pinned
        ev = [r["entity_id"] for r in conn.execute("select entity_id from case_evidence where case_id=%s", (cid,)).fetchall()]
        result = scoring.grade(conn, c, answer, ev)

        # the client only scores the slots it can submit; recompute "correct" over those
        scored_slots = [s for field in client if client[field] is not None
                        for s in CLIENT_FIELD_TO_SLOTS[field] if s in slots]
        scored_slots = list(dict.fromkeys(scored_slots))
        all_required = [s for s in slots if s not in ("person",)]  # person needs the new apps
        verdicts = []
        FIELD_LABEL = {"actor_id": "Threat actor", "campaign_id": "Campaign",
                       "domain_id": "Primary domain", "malware_id": "Malware family"}
        correct_fields = result["fields"]
        for field in ("actor_id", "campaign_id", "domain_id", "malware_id"):
            slot = next((s for s in CLIENT_FIELD_TO_SLOTS[field] if s in slots), None)
            if slot is None:
                continue
            good = bool(correct_fields.get(slot))
            verdicts.append({"field": FIELD_LABEL[field], "correct": good,
                             "submitted": submitted_labels.get(field, "(none)")})

        # "solved" for the 7-app client = every slot it is ABLE to answer is right
        answerable = [s for s in all_required if any(s in CLIENT_FIELD_TO_SLOTS[f] for f in client)]
        is_correct = bool(answerable) and all(correct_fields.get(s) for s in answerable)

        conn.execute("""insert into submissions(case_id, answer, evidence, correct, score, breakdown)
                        values (%s,%s,%s,%s,%s,%s)""",
                     (cid, json.dumps(answer), ev, is_correct, result["score"], json.dumps(result)))
        if is_correct:
            conn.execute("update cases set status='solved', score=%s, closed_at=now() where id=%s",
                         (result["score"], cid))
        else:
            conn.execute("update cases set attempts=attempts+1 where id=%s", (cid,))
        attempt_no = conn.execute("select attempts from cases where id=%s", (cid,)).fetchone()["attempts"]
        gt = conn.execute("select resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
        return {
            "is_correct": is_correct, "score": result["score"], "attempt_no": attempt_no,
            "verdicts": verdicts,
            "narrative": gt["resolution_text"] if is_correct else
                         "Not all conclusions are supported. Re-examine the infrastructure and attribution.",
        }


# --------------------------------------------------------------------------- graph
@router.get("/cases/{n}/graph")
def graph(n: int):
    """The Evidence Map. Show the player's pinned entities plus their immediate
    neighbours, as nodes + edges in the client's shape (string node_id)."""
    with tx() as conn:
        ensure_tables(conn)
        cid = case_uuid(conn, n)
        pinned = [r["entity_id"] for r in conn.execute(
            "select entity_id from case_evidence where case_id=%s", (cid,)).fetchall()]
        if not pinned:
            return {"nodes": [], "edges": []}
        # neighbours of pinned nodes (one hop), so the web grows as they investigate
        node_ids = set(pinned)
        edges = []
        rows = conn.execute("""select r.src_id, r.dst_id, r.rel::text, r.case_id,
                                      coalesce((select role::text from case_entities where case_id=%s and entity_id=r.src_id),'noise') srole
                               from entity_relationships r
                               where (r.src_id = any(%s::uuid[]) or r.dst_id = any(%s::uuid[]))
                                 and (r.case_id is null or r.case_id=%s)""",
                           (cid, pinned, pinned, cid)).fetchall()
        for r in rows:
            node_ids.add(r["src_id"]); node_ids.add(r["dst_id"])
            edges.append({"src": str(r["src_id"]), "dst": str(r["dst_id"]),
                          "label": r["rel"].replace("_", " ")})
        nodes = []
        for nid in node_ids:
            e = conn.execute("select kind::text, value::text v, coalesce(label,value::text) l, verdict::text from entities where id=%s", (nid,)).fetchone()
            role = conn.execute("select role::text from case_entities where case_id=%s and entity_id=%s", (cid, nid)).fetchone()
            nodes.append({"node_id": str(nid), "entity_id": ent_int(conn, nid),
                          "kind": e["kind"], "label": e["l"][:36], "sublabel": e["kind"].replace("_", " "),
                          "status": status_of(e["verdict"])})
        conn.execute("insert into query_log(case_id,tool,query,result_count,hit_roles) values (%s,'graph','',%s,'{}')",
                     (cid, len(nodes)))
        return {"nodes": nodes, "edges": edges}
