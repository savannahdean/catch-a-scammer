"""Catch-a-Scammer API.  Run: make server   (uvicorn on :8000)

The C++/raylib client only ever talks to this API. The database connection
string and the ground-truth tables never leave the server.

App (in-game window)   -> endpoint
  CaseDesk             -> POST /cases, GET /cases/{id}, GET /cases/{id}/email
  IntelSearch          -> GET /cases/{id}/search, /entity/{eid}
  DNS History          -> GET /cases/{id}/pdns
  WHOIS History        -> GET /cases/{id}/whois
  CertSearch (CT)      -> GET /cases/{id}/ct
  URL Scanner          -> GET /cases/{id}/urlscan, /pivot
  MalwareDB            -> GET /cases/{id}/malware
  Breach Lookup        -> GET /cases/{id}/breach
  WebSearch            -> GET /cases/{id}/web
  Directory            -> GET /cases/{id}/directory
  Evidence Map         -> GET /cases/{id}/graph/{eid}, /evidence
  Case Report          -> POST /cases/{id}/submit, GET /cases/{id}/debrief
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import FastAPI, HTTPException, Query
from psycopg.rows import dict_row, tuple_row
from pydantic import BaseModel

from . import compat, scoring
from .db import tx
from .generator.registry import generate_case, sync_catalog, SCENARIOS

app = FastAPI(title="Catch-a-Scammer API", version="1.0")
app.include_router(compat.router)


@app.on_event("startup")
def _startup():
    try:
        with tx() as conn:
            sync_catalog(conn)
    except Exception:
        pass   # catalog is best-effort; /scenarios still reads whatever is there

SUBTYPE = {
    "domain": "domains", "ip": "ip_addresses", "asn": "asns", "hosting_provider": "hosting_providers",
    "registrar": "registrars", "nameserver": "nameservers", "whois_record": "whois_records",
    "certificate": "certificates", "url": "urls", "url_scan": "url_scans", "tracking_id": "tracking_ids",
    "email_address": "email_addresses", "email_message": "email_messages", "malware_family": "malware_families",
    "malware_sample": "malware_samples", "campaign": "campaigns", "threat_actor": "threat_actors",
    "persona": "personas", "person": "persons", "organization": "organizations",
    "crypto_wallet": "crypto_wallets", "breach": "breaches", "web_article": "web_articles",
    "image": "images", "social_post": "social_posts", "document": "documents",
    "audio_recording": "audio_recordings", "sms_message": "sms_messages", "phone": "phone_numbers",
    "payment_account": "payment_accounts", "lure_template": "lure_templates", "complaint": "complaints",
}


# ------------------------------------------------------------------ helpers
def jsonable(row: dict) -> dict:
    out = {}
    for k, v in row.items():
        if isinstance(v, (datetime,)):
            out[k] = v.isoformat()
        elif hasattr(v, "lower") and hasattr(v, "upper") and hasattr(v, "isempty"):   # Range
            out[k] = {"from": v.lower.isoformat() if v.lower else None, "to": v.upper.isoformat() if v.upper else None}
        elif isinstance(v, (list, tuple)):
            out[k] = [str(x) if not isinstance(x, (int, float, str, dict, type(None))) else x for x in v]
        elif isinstance(v, (int, float, str, dict, bool, type(None))):
            out[k] = v
        else:
            out[k] = str(v)
    return out


def get_case(conn, cid: UUID) -> dict:
    case = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
    if not case:
        raise HTTPException(404, "case not found")
    return case


def require_open(case: dict) -> None:
    if case["status"] != "open":
        raise HTTPException(409, f"case is {case['status']}")


def log(conn, cid: UUID, tool: str, query: str, ids: list) -> None:
    ids = [i for i in ids if i]
    roles = [r["role"] for r in conn.execute(
        "select distinct role::text as role from case_entities where case_id=%s and entity_id = any(%s::uuid[])",
        (cid, ids)).fetchall()] if ids else []
    conn.execute("insert into query_log(case_id, tool, query, result_count, hit_roles) values (%s,%s,%s,%s,%s::case_role[])",
                 (cid, tool, query, len(ids), roles))


def visible(conn, cid: UUID, eid: UUID) -> dict:
    row = conn.execute("select * from entities where id=%s and (case_id is null or case_id=%s)", (eid, cid)).fetchone()
    if not row:
        raise HTTPException(404, "entity not found")
    return row


# ------------------------------------------------------------------ CaseDesk
class NewCase(BaseModel):
    difficulty: str = "medium"
    seed: Optional[int] = None
    scenario: str = "random"


@app.get("/scenarios")
def scenarios():
    with tx() as conn:
        rows = conn.execute("select key, title, category, real_world_basis, player_skill, report_fields, min_difficulty from scenarios where enabled order by category, title").fetchall()
    return [jsonable(r) for r in rows]


@app.get("/health")
def health():
    with tx() as conn:
        n = conn.execute("select count(*) n from entities where case_id is null").fetchone()["n"]
    return {"ok": True, "world_entities": n}


@app.post("/cases")
def new_case(body: NewCase):
    with tx() as conn:
        conn.row_factory = tuple_row          # generator uses tuple rows
        try:
            cid = generate_case(conn, body.difficulty, body.seed, body.scenario)
        except ValueError as e:
            raise HTTPException(400, str(e))
        finally:
            conn.row_factory = dict_row
        case = get_case(conn, cid)
        mh = conn.execute("select max_hints from difficulty_profiles where level=%s", (case["difficulty"],)).fetchone()
        slots = conn.execute("select answer_slots from case_ground_truth where case_id=%s", (cid,)).fetchone()
        fields = [{"key": k, "label": v["label"], "kind": v["kind"]} for k, v in (slots["answer_slots"].items() if slots else [])]
    return {"case_id": str(cid), "case_code": case["case_code"], "scenario": case["scenario"],
            "difficulty": case["difficulty"], "briefing": case["briefing"], "reported_at": case["reported_at"].isoformat(),
            "victim": {"name": case["victim_name"], "role": case["victim_role"], "org": case["victim_org"]},
            "report_fields": fields, "max_hints": mh["max_hints"]}


@app.get("/cases")
def list_cases(limit: int = 20):
    with tx() as conn:
        rows = conn.execute("""select id, case_code, difficulty, status, score, created_at from cases
                               order by created_at desc limit %s""", (limit,)).fetchall()
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}")
def case_info(cid: UUID):
    with tx() as conn:
        c = get_case(conn, cid)
    keep = ["id", "case_code", "scenario", "difficulty", "reported_at", "victim_name", "victim_org",
            "victim_role", "briefing", "status", "attempts", "hints_used", "score"]
    return jsonable({k: c[k] for k in keep})


@app.get("/cases/{cid}/email")
def case_email(cid: UUID):
    with tx() as conn:
        get_case(conn, cid)
        row = conn.execute("""select e.id as entity_id, m.* from case_entities ce
                              join entities e on e.id = ce.entity_id
                              join email_messages m on m.entity_id = e.id
                              where ce.case_id=%s and ce.role='initial_clue'""", (cid,)).fetchone()
        log(conn, cid, "casedesk.email", "open", [row["entity_id"]])
    return jsonable(row)


# ------------------------------------------------------------------ IntelSearch
@app.get("/cases/{cid}/search")
def search(cid: UUID, q: str = Query(min_length=2), limit: int = 25):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("select * from intel_search(%s, %s, %s)", (cid, q, limit)).fetchall()
        log(conn, cid, "intelsearch", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/entity/{eid}")
def entity(cid: UUID, eid: UUID):
    with tx() as conn:
        e = visible(conn, cid, eid)
        detail = {}
        table = SUBTYPE.get(e["kind"])
        if table:
            d = conn.execute(f"select * from {table} where entity_id=%s", (eid,)).fetchone()
            detail = jsonable(d) if d else {}
        if e["kind"] == "threat_actor":
            detail["aliases"] = [jsonable(a) for a in conn.execute(
                """select a.alias::text, s.name as named_by, s.reliability from actor_aliases a
                   left join sources s on s.id=a.named_by where a.actor_id=%s""", (eid,)).fetchall()]
        if e["kind"] == "ip":
            asn = conn.execute("""select a.value::text asn, hp.name provider, hp.provider_type, hp.abuse_responsiveness
                                  from entity_relationships r join entities a on a.id=r.dst_id
                                  join entity_relationships r2 on r2.src_id=a.id and r2.rel='operated_by'
                                  join hosting_providers hp on hp.entity_id=r2.dst_id
                                  where r.src_id=%s and r.rel='announced_by' limit 1""", (eid,)).fetchone()
            detail["network"] = jsonable(asn) if asn else None
        detail.pop("entity_id", None)
        log(conn, cid, f"entity.{e['kind']}", str(e["value"]), [eid])
    return {"entity": jsonable(e), "detail": detail}


# ------------------------------------------------------------------ infrastructure tools
@app.get("/cases/{cid}/pdns")
def pdns(cid: UUID, q: str):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("select * from pdns(%s, %s)", (cid, q)).fetchall()
        ids = [r["id"] for r in conn.execute(
            "select id from entities where value = any(%s) and (case_id is null or case_id=%s)",
            ([r["domain"] for r in rows] + [r["ip"] for r in rows], cid)).fetchall()]
        log(conn, cid, "pdns", q, ids)
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/whois")
def whois(cid: UUID, domain: str):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, w.* from whois_records w join entities e on e.id=w.entity_id
                               where w.domain_fqdn=%s and (e.case_id is null or e.case_id=%s)
                               order by w.captured_at""", (domain, cid)).fetchall()
        log(conn, cid, "whois", domain, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/ct")
def ct(cid: UUID, q: str = Query(min_length=3)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("select * from ct_search(%s, %s)", (cid, q)).fetchall()
        log(conn, cid, "ct", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/urlscan")
def urlscan(cid: UUID, q: str = Query(min_length=3)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, s.* from url_scans s join entities e on e.id=s.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (s.scanned_url ilike %s or s.final_url ilike %s or host(s.ip_seen)=%s)
                               order by s.scanned_at desc limit 50""", (cid, f"%{q}%", f"%{q}%", q)).fetchall()
        log(conn, cid, "urlscan", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/pivot")
def pivot(cid: UUID, field: str, value: str):
    with tx() as conn:
        get_case(conn, cid)
        try:
            rows = conn.execute("select * from pivot(%s, %s, %s)", (cid, field, value)).fetchall()
        except Exception as e:
            raise HTTPException(400, str(e).splitlines()[0])
        log(conn, cid, f"pivot.{field}", value, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


# ------------------------------------------------------------------ malware / breach / web / directory
@app.get("/cases/{cid}/malware")
def malware(cid: UUID, q: str = Query(min_length=3)):
    with tx() as conn:
        get_case(conn, cid)
        fams = conn.execute("""select e.id as entity_id, f.* from malware_families f join entities e on e.id=f.entity_id
                               where f.family ilike %s""", (f"%{q}%",)).fetchall()
        samples = conn.execute("""select e.id as entity_id, m.* from malware_samples m join entities e on e.id=m.entity_id
                                  where (e.case_id is null or e.case_id=%s)
                                    and (m.sha256=lower(%s) or m.md5=lower(%s) or m.sha1=lower(%s)
                                         or m.imphash=lower(%s) or m.file_name ilike %s)""",
                               (cid, q, q, q, q, f"%{q}%")).fetchall()
        # a family page lists recent samples in this case's scope, like a sample-sharing site
        for f in fams:
            f["recent_samples"] = [r["sha256"] for r in conn.execute(
                """select m.sha256 from malware_samples m join entities e on e.id=m.entity_id
                   join entity_relationships r on r.src_id=e.id and r.rel='sample_of' and r.dst_id=%s
                   where e.case_id is null or e.case_id=%s""", (f["entity_id"], cid)).fetchall()]
        log(conn, cid, "malware", q, [r["entity_id"] for r in fams + samples])
    return {"families": [jsonable(r) for r in fams], "samples": [jsonable(r) for r in samples]}


@app.get("/cases/{cid}/breach")
def breach(cid: UUID, q: str = Query(min_length=3)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select b.breach_name, b.breach_date, r.email::text, r.username::text, r.display_name,
                                      r.hash_type, left(r.password_hash, 12) || '…' as password_hash_prefix,
                                      host(r.signup_ip) as signup_ip, r.breach_id
                               from breach_records r join breaches b on b.entity_id=r.breach_id
                               where (r.case_id is null or r.case_id=%s)
                                 and (r.email = %s or r.username = %s)
                               order by b.breach_date""", (cid, q, q)).fetchall()
        log(conn, cid, "breach", q, [r["breach_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/web")
def web(cid: UUID, q: str = Query(min_length=2)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, a.publisher, a.author, a.title, a.published_at, a.body,
                                      s.reliability
                               from web_articles a join entities e on e.id=a.entity_id
                               left join sources s on s.id=a.source_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (to_tsvector('english', a.title || ' ' || a.body) @@ websearch_to_tsquery('english', %s)
                                      or a.body ilike %s or a.title ilike %s)
                               order by a.published_at desc limit 20""", (cid, q, f"%{q}%", f"%{q}%")).fetchall()
        log(conn, cid, "web", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/directory")
def directory(cid: UUID, q: str = Query(min_length=2)):
    with tx() as conn:
        get_case(conn, cid)
        actors = conn.execute("""select distinct e.id as entity_id, t.primary_alias, t.motivation, t.sophistication,
                                        t.suspected_origin, t.notes
                                 from threat_actors t join entities e on e.id=t.entity_id
                                 left join actor_aliases a on a.actor_id=t.entity_id
                                 where t.primary_alias ilike %s or a.alias::text ilike %s""", (f"%{q}%", f"%{q}%")).fetchall()
        # match the handle, the profile text, or anything the persona posted, so a
        # snippet from a romance DM or a bio line finds the account behind it
        personas = conn.execute("""select e.id as entity_id, p.handle::text, p.platform, p.display_name, p.joined_on,
                                          p.post_count, p.bio, p.claimed_occupation, p.claimed_location,
                                          p.language, p.utc_offset_guess
                                   from personas p join entities e on e.id=p.entity_id
                                   where (e.case_id is null or e.case_id=%s)
                                     and (p.handle::text ilike %s or p.display_name ilike %s or p.bio ilike %s
                                          or exists (select 1 from entity_relationships r
                                                     join social_posts sp on sp.entity_id=r.dst_id
                                                     where r.src_id=e.id and r.rel='posted' and sp.body ilike %s))
                                   limit 25""", (cid, f"%{q}%", f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        people = conn.execute("""select e.id as entity_id, p.full_name, p.city, p.country, p.birth_year, p.employer, p.job_title
                                 from persons p join entities e on e.id=p.entity_id
                                 where (e.case_id is null or e.case_id=%s) and p.full_name ilike %s
                                 limit 25""", (cid, f"%{q}%")).fetchall()
        orgs = conn.execute("""select e.id as entity_id, o.* from organizations o join entities e on e.id=o.entity_id
                               where o.name ilike %s""", (f"%{q}%",)).fetchall()
        ids = [r["entity_id"] for r in actors + personas + people + orgs]
        log(conn, cid, "directory", q, ids)
    return {"actors": [jsonable(r) for r in actors], "personas": [jsonable(r) for r in personas],
            "people": [jsonable(r) for r in people], "organizations": [jsonable(r) for r in orgs]}


# ------------------------------------------------------------------ new-scam tools
@app.get("/cases/{cid}/reverse_image")
def reverse_image(cid: UUID, q: str):
    """Reverse image search: every place a photo (or near-duplicate) appears, oldest first."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("select * from reverse_image(%s, %s)", (cid, q)).fetchall()
        log(conn, cid, "reverse_image", q, [r["seen_on_id"] for r in rows] + [r["image_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/money_trail")
def money_trail(cid: UUID, start: UUID, max_depth: int = 6):
    """Follow payments/transfers forward from an account or wallet."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("select * from money_trail(%s, %s, %s)", (cid, start, max_depth)).fetchall()
        log(conn, cid, "money_trail", str(start), [r["to_id"] for r in rows] + [start])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/social")
def social(cid: UUID, q: str = Query(min_length=2)):
    """Search social posts/DMs by text or author handle."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, p.* from social_posts p join entities e on e.id=p.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (p.body ilike %s or p.author_handle::text ilike %s
                                      or to_tsvector('simple', p.body) @@ plainto_tsquery('simple', %s))
                               order by p.posted_at limit 40""", (cid, f"%{q}%", f"%{q}%", q)).fetchall()
        log(conn, cid, "social", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/phone")
def phone_lookup(cid: UUID, number: str = Query(min_length=3)):
    """Carrier / line-type / spam-report lookup for a phone number."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, p.* from phone_numbers p join entities e on e.id=p.entity_id
                               where (e.case_id is null or e.case_id=%s) and (p.e164 ilike %s or e.value::text ilike %s)""",
                            (cid, f"%{number}%", f"%{number}%")).fetchall()
        log(conn, cid, "phone", number, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/sms")
def sms_lookup(cid: UUID, q: str = Query(min_length=2)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, s.* from sms_messages s join entities e on e.id=s.entity_id
                               where (e.case_id is null or e.case_id=%s) and (s.body ilike %s or s.from_number ilike %s)
                               order by s.sent_at""", (cid, f"%{q}%", f"%{q}%")).fetchall()
        log(conn, cid, "sms", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/document")
def document_lookup(cid: UUID, q: str = Query(min_length=3)):
    """Document search; the detail view (via /entity) exposes the metadata that exposes forgers."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, d.file_name, d.file_type, d.sha256, d.meta_author,
                                      d.meta_last_modified_by, d.meta_creator_tool, d.meta_created, d.text_excerpt
                               from documents d join entities e on e.id=d.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (d.file_name ilike %s or d.text_excerpt ilike %s or d.sha256=lower(%s)
                                      or d.meta_author ilike %s)""",
                            (cid, f"%{q}%", f"%{q}%", q, f"%{q}%")).fetchall()
        log(conn, cid, "document", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/audio")
def audio_lookup(cid: UUID, q: str = Query(min_length=2)):
    """Audio analysis: transcript search; detail shows voiceprint + synthetic score."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, a.recording_type, a.speaker_claimed, a.recorded_at,
                                      a.caller_id, a.stir_shaken, a.synthetic_score, a.voiceprint_hash,
                                      a.duration_s, a.transcript, a.source_url, a.analysis_note
                               from audio_recordings a join entities e on e.id=a.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (a.transcript ilike %s or a.speaker_claimed ilike %s or a.caller_id ilike %s)
                               order by a.recorded_at""", (cid, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        log(conn, cid, "audio", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/payment")
def payment_lookup(cid: UUID, q: str = Query(min_length=2)):
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, p.* from payment_accounts p join entities e on e.id=p.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (p.identifier ilike %s or p.provider ilike %s or p.holder_name ilike %s)""",
                            (cid, f"%{q}%", f"%{q}%", f"%{q}%")).fetchall()
        log(conn, cid, "payment", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


@app.get("/cases/{cid}/complaints")
def complaints_lookup(cid: UUID, q: str = Query(min_length=2)):
    """Fraud-complaint portal: other victims' reports (corroboration and noise)."""
    with tx() as conn:
        get_case(conn, cid)
        rows = conn.execute("""select e.id as entity_id, c.portal, c.filed_at, c.reporter_region, c.loss_amount,
                                      c.narrative, c.indicators
                               from complaints c join entities e on e.id=c.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (c.narrative ilike %s or %s = any(c.indicators)
                                      or to_tsvector('english', c.narrative) @@ websearch_to_tsquery('english', %s))
                               order by c.filed_at desc limit 30""", (cid, f"%{q}%", q, q)).fetchall()
        log(conn, cid, "complaints", q, [r["entity_id"] for r in rows])
    return [jsonable(r) for r in rows]


# ------------------------------------------------------------------ Evidence Map
@app.get("/cases/{cid}/graph/{eid}")
def graph(cid: UUID, eid: UUID):
    with tx() as conn:
        get_case(conn, cid)
        center = visible(conn, cid, eid)
        rows = conn.execute("select * from neighbors(%s, %s)", (cid, eid)).fetchall()
        log(conn, cid, "graph.expand", str(center["value"]), [eid] + [r["other_id"] for r in rows])
    return {"center": jsonable(center), "edges": [jsonable(r) for r in rows]}


class EvidenceIn(BaseModel):
    entity_id: UUID
    note: Optional[str] = None


@app.get("/cases/{cid}/evidence")
def evidence_list(cid: UUID):
    with tx() as conn:
        rows = conn.execute("""select e.id as entity_id, e.kind, e.value::text, e.label, ev.note, ev.added_at
                               from case_evidence ev join entities e on e.id=ev.entity_id
                               where ev.case_id=%s order by ev.added_at""", (cid,)).fetchall()
    return [jsonable(r) for r in rows]


@app.post("/cases/{cid}/evidence")
def evidence_add(cid: UUID, body: EvidenceIn):
    with tx() as conn:
        require_open(get_case(conn, cid))
        visible(conn, cid, body.entity_id)
        conn.execute("""insert into case_evidence(case_id, entity_id, note) values (%s,%s,%s)
                        on conflict (case_id, entity_id) do update set note=excluded.note""",
                     (cid, body.entity_id, body.note))
    return {"ok": True}


@app.delete("/cases/{cid}/evidence/{eid}")
def evidence_remove(cid: UUID, eid: UUID):
    with tx() as conn:
        conn.execute("delete from case_evidence where case_id=%s and entity_id=%s", (cid, eid))
    return {"ok": True}


# ------------------------------------------------------------------ Hints / Report
@app.post("/cases/{cid}/hint")
def hint(cid: UUID):
    with tx() as conn:
        c = get_case(conn, cid)
        require_open(c)
        mx = conn.execute("select max_hints from difficulty_profiles where level=%s", (c["difficulty"],)).fetchone()["max_hints"]
        if c["hints_used"] >= mx:
            raise HTTPException(409, "no hints left for this difficulty")
        h = conn.execute("select step, hint, cost from case_hints where case_id=%s and step=%s",
                         (cid, c["hints_used"] + 1)).fetchone()
        if not h:
            raise HTTPException(409, "no more hints")
        conn.execute("update cases set hints_used = hints_used + 1 where id=%s", (cid,))
    return {"step": h["step"], "hint": h["hint"], "cost": h["cost"], "remaining": mx - h["step"]}


class Submission(BaseModel):
    # Answer slots vary by scenario (actor, campaign, mule_account, scam_persona,
    # stolen_image, callback_number, ...), so accept any string slot the Case
    # Report form declares, plus the evidence list. Unknown keys are kept.
    model_config = {"extra": "allow"}
    evidence: Optional[list[UUID]] = None      # defaults to everything on the evidence board


@app.post("/cases/{cid}/submit")
def submit(cid: UUID, body: Submission):
    with tx() as conn:
        c = get_case(conn, cid)
        require_open(c)
        ev = body.evidence or [r["entity_id"] for r in conn.execute(
            "select entity_id from case_evidence where case_id=%s", (cid,)).fetchall()]
        answer = {k: v for k, v in body.model_dump(exclude={"evidence"}).items() if v is not None}
        result = scoring.grade(conn, c, answer, ev)
        conn.execute("""insert into submissions(case_id, answer, evidence, correct, score, breakdown)
                        values (%s,%s,%s,%s,%s,%s)""",
                     (cid, json.dumps(body.model_dump(exclude={"evidence"})), ev,
                      result["correct"], result["score"], json.dumps(result)))
        if result["correct"]:
            conn.execute("update cases set status='solved', score=%s, closed_at=now() where id=%s", (result["score"], cid))
        else:
            conn.execute("update cases set attempts = attempts + 1 where id=%s", (cid,))
    if not result["correct"] and c["difficulty"] in ("hard", "expert"):
        # harder cases only say HOW MANY conclusions are right, not which
        result["fields"] = {"correct_count": sum(result["fields"].values()), "total": len(result["fields"])}
    return result


@app.post("/cases/{cid}/abandon")
def abandon(cid: UUID):
    with tx() as conn:
        conn.execute("update cases set status='abandoned', closed_at=now() where id=%s and status='open'", (cid,))
    return {"ok": True}


@app.get("/cases/{cid}/debrief")
def debrief(cid: UUID):
    """Only after the case is closed: the full story, and what each clue really was."""
    with tx() as conn:
        c = get_case(conn, cid)
        if c["status"] == "open":
            raise HTTPException(409, "debrief unlocks after the case is solved or abandoned")
        truth = conn.execute("select resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
        roles = conn.execute("""select e.kind, e.value::text, ce.role, ce.hop, ce.explanation
                                from case_entities ce join entities e on e.id=ce.entity_id
                                where ce.case_id=%s and ce.role <> 'noise'
                                order by ce.role, ce.hop nulls last""", (cid,)).fetchall()
    return {"resolution": truth["resolution_text"], "entities": [jsonable(r) for r in roles]}
