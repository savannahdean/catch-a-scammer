"""API for the React game client (frontend/), under /api.

The client speaks this dialect:
  * integer case and entity IDs (the `seq` identity columns)
  * /api/... routes
  * flat record shapes for the original tools (domain_name, ip_address, ...)
This module serves that dialect on top of the UUID/entity backend, and adds
the tools the 12 scam scenarios need. Those newer tools all return generic
"cards" (server/cards.py), so the client draws them with one renderer.
The client Messenger lives in server/messenger.py and the research study in
server/study.py; both are mounted next to this router in server/app.py.

Integer ids are the `seq` identity columns on cases and entities.

Search responses share one envelope:
    {"query": q, "found": bool, "message": "...", "cards": [...],
     ...legacy keys ("domains", "ips", "malware", "actors", "persons", "articles")}
A single record has a "kind" (legacy record) or "card" key.

Everything a tool shows is recorded in case_discoveries, and the Case Report
only offers what the player has discovered. Every query goes to query_log.
"""
from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from . import messenger, scoring
from .cards import (Ctx, card_for, case_int, ent_int, host_of, image_card, status_of, to_e164,
                    URL_RE, BUILDERS)
from .db import tx
from .guard import case_by_seq, rate_limit
from .generator.registry import SCENARIOS, generate_case

router = APIRouter(prefix="/api")

ALL_SCENARIOS = [k for k in SCENARIOS if k != "credential_phish"]
VICTIM_TZ = timezone(timedelta(hours=-5), "CDT")


# --------------------------------------------------------------------------- ids & helpers
def case_uuid(conn, n: int) -> UUID:
    """The case with this number, if the request carries its X-Case-Key (server/guard.py)."""
    return case_by_seq(conn, n)


def ent_uuid(conn, n: int) -> Optional[UUID]:
    row = conn.execute("select id from entities where seq=%s", (n,)).fetchone()
    return row["id"] if row else None


def need_ent(conn, n: int) -> UUID:
    eid = ent_uuid(conn, n)
    if not eid:
        raise HTTPException(404, "unknown entity")
    return eid


def iso(v) -> str:
    return v.date().isoformat() if isinstance(v, datetime) else (str(v) if v else "")


def case_visible(conn, cid: UUID, eid: UUID) -> dict:
    row = conn.execute("select * from entities where id=%s and (case_id is null or case_id=%s)", (eid, cid)).fetchone()
    if not row:
        raise HTTPException(404, "entity not found")
    return row


def qlog(conn, cid: UUID, tool: str, query: str, ids: list) -> None:
    """Research log: every search, how many results, and which hidden roles they hit."""
    ids = [i for i in dict.fromkeys(ids) if i]
    conn.execute("""insert into query_log(case_id, tool, query, result_count, hit_roles)
                    select %s, %s, %s, %s, coalesce(array_agg(distinct role), '{}')
                    from case_entities where case_id=%s and entity_id = any(%s::uuid[])""",
                 (cid, tool, query, len(ids), cid, ids))


def result(q: str, cards: list, empty: str, **legacy) -> dict:
    found = bool(cards) or any(legacy.values())
    return {"query": q, "found": found, "message": "" if found else empty, "cards": cards, **legacy}


# --------------------------------------------------------------------------- case lifecycle
class NewCase(BaseModel):
    model_config = {"extra": "allow"}
    difficulty: str = "medium"
    player: Optional[str] = None
    scenario: Optional[str] = None
    personality: Optional[str] = None       # client personality key, or "random" (dealt by difficulty)
    participant_id: Optional[UUID] = None   # study participant playing this case, if any


def clue_of(conn, cid: UUID) -> Optional[dict]:
    return conn.execute("""select e.* from case_entities ce join entities e on e.id=ce.entity_id
                           where ce.case_id=%s and ce.role='initial_clue' limit 1""", (cid,)).fetchone()


def clue_text(conn, clue: dict) -> str:
    k = clue["kind"]
    q = {"email_message": "select body_text t from email_messages where entity_id=%s",
         "sms_message": "select body t from sms_messages where entity_id=%s",
         "social_post": "select body t from social_posts where entity_id=%s",
         "audio_recording": "select transcript t from audio_recordings where entity_id=%s",
         "url_scan": "select scanned_url t from url_scans where entity_id=%s"}.get(k)
    return conn.execute(q, (clue["id"],)).fetchone()["t"] if q else ""


def brief_payload(conn, cid: UUID) -> dict:
    c = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
    if not c:
        raise HTTPException(404, "case not found")
    gt = conn.execute("select answer_slots, resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
    # The CaseDesk "open in IntelSearch" shortcut: only a domain the victim actually holds
    # (a link in the message they received). Never a domain they'd have to discover.
    entry = ""
    clue = clue_of(conn, cid)
    if clue:
        link = conn.execute("""select e.value::text v from entity_relationships r join entities e on e.id=r.dst_id
                               where r.src_id=%s and r.rel='contains_link' limit 1""", (clue["id"],)).fetchone()
        found = URL_RE.findall(clue_text(conn, clue) or "")
        entry = host_of(link["v"]) if link else (host_of(found[0]) if found else "")
    loc = lambda d: d.astimezone(VICTIM_TZ).strftime("%a %b %d %Y, %I:%M %p CDT")
    briefing = (f"REPORTED BY: {c['victim_name']}, {c['victim_role']}, {c['victim_org']}\n"
                f"INCIDENT:    {loc(c['incident_at'])}\nREPORTED:    {loc(c['reported_at'])}\n\n{c['briefing']}")
    fields = [{"key": k, "label": v["label"], "kind": v["kind"]} for k, v in (ordered_slots(conn, cid).items() if gt else [])]
    client = conn.execute("""select cc.personality, p.label from case_client cc join client_profiles p on p.key=cc.personality
                             where cc.case_id=%s""", (cid,)).fetchone()
    return {
        "case_id": case_int(conn, cid),
        "case_code": c["case_code"],
        "difficulty": c["difficulty"],
        "scenario": c["scenario"],
        "briefing": briefing,
        "entry_domain": entry,
        "incident_at": c["incident_at"].isoformat(),
        "report_fields": fields,
        "attempts": c["attempts"],
        "hints_used": c["hints_used"],
        "status": c["status"],
        "score": c["score"] or 0,
        "resolution_text": (gt["resolution_text"] if (gt and c["status"] in ("solved", "failed")) else ""),
        "victim_name": c["victim_name"],
        "client": {"name": c["victim_name"], "personality": client["personality"], "label": client["label"]}
                  if client else None,
    }


@router.post("/cases", dependencies=[Depends(rate_limit("new_case", "20/3600"))])
def new_case(body: NewCase):
    scenario = body.scenario or "random"
    if scenario == "random":
        scenario = random.choice(ALL_SCENARIOS)
    with tx() as conn:
        from psycopg.rows import dict_row, tuple_row
        conn.row_factory = tuple_row          # the generator uses tuple rows
        try:
            cid = generate_case(conn, body.difficulty, None, scenario)
        except ValueError as e:
            raise HTTPException(400, str(e))
        finally:
            conn.row_factory = dict_row
        if body.participant_id and conn.execute("select 1 from study_participants where id=%s",
                                                (body.participant_id,)).fetchone():
            conn.execute("update cases set participant_id=%s where id=%s", (body.participant_id, cid))
        messenger.init_client(conn, cid, messenger.pick_personality(conn, body.difficulty, body.personality))
        key = conn.execute("select access_key::text k from cases where id=%s", (cid,)).fetchone()["k"]
        # the only time the key is sent: the client keeps it and sends it back as X-Case-Key
        return {**brief_payload(conn, cid), "case_key": key}


@router.get("/cases/{n}")
def get_case(n: int):
    with tx() as conn:
        return brief_payload(conn, case_uuid(conn, n))


@router.get("/cases/{n}/exhibits")
def exhibits(n: int):
    """What the reporting party handed over: the message they received, the
    profile and photos they saw, and the payment details they were given."""
    with tx() as conn:
        cid = case_uuid(conn, n)
        ctx = Ctx(conn, cid, "casedesk")
        clue = clue_of(conn, cid)
        items: list[UUID] = []
        if clue:
            items.append(clue["id"])
            if clue["kind"] == "social_post":
                # the thread the victim saw: replies to their post (angler phishing's fake "support")
                items += [r["id"] for r in conn.execute(
                    """select r.src_id id from entity_relationships r join social_posts sp on sp.entity_id=r.src_id
                       where r.dst_id=%s and r.rel='replied_to' order by sp.posted_at""", (clue["id"],)).fetchall()]
                for a in conn.execute("""select r.src_id id from entity_relationships r
                                         where r.dst_id=%s and r.rel='posted'""", (clue["id"],)).fetchall():
                    items.append(a["id"])
                    items += [r["id"] for r in conn.execute(
                        """select e.id from entity_relationships r join entities e on e.id=r.dst_id
                           join social_posts sp on sp.entity_id=e.id
                           where r.src_id=%s and r.rel='posted' and e.case_id=%s and sp.is_direct_message
                           order by sp.posted_at""", (a["id"], cid)).fetchall()]
                    items += [r["id"] for r in conn.execute(
                        "select dst_id id from entity_relationships where src_id=%s and rel='uses_image'", (a["id"],)).fetchall()]
            elif clue["kind"] == "email_message":
                items += [r["id"] for r in conn.execute(
                    "select dst_id id from entity_relationships where src_id=%s and rel='attached'", (clue["id"],)).fetchall()]
            elif clue["kind"] == "sms_message":
                items += [r["id"] for r in conn.execute(
                    """select e.id from sms_messages s join entities e on e.id=s.entity_id
                       where e.case_id=%s and s.from_number=(select from_number from sms_messages where entity_id=%s)
                       order by s.sent_at""", (cid, clue["id"])).fetchall()]
        # follow-up messages that carried payment details (whaling's second email)
        items += [r["id"] for r in conn.execute(
            """select distinct e.id from entity_relationships r join sources s on s.id=r.source_id
               join entities e on e.id=r.src_id
               where r.case_id=%s and s.name='Victim Report' and r.rel='pays_to'
                 and e.kind in ('email_message','sms_message','social_post')""", (cid,)).fetchall()]
        # payment details the victim was given (account numbers, deposit addresses)
        items += [r["id"] for r in conn.execute(
            """select distinct e.id from entity_relationships r join sources s on s.id=r.source_id
               join entities e on e.id=r.dst_id
               where r.case_id=%s and s.name='Victim Report' and e.kind in ('payment_account','crypto_wallet')""",
            (cid,)).fetchall()]
        # records the client is still holding back (they hand them over in the Messenger)
        held = messenger.withheld(conn, cid)
        items = [i for i in items if i not in held]
        c = conn.execute("select victim_name, victim_role, victim_org from cases where id=%s", (cid,)).fetchone()
        email = c["victim_name"].lower().replace(" ", ".") + "@midstate.example"
        cards, letters = [{
            "card": "victim", "kind_label": "REPORTING PARTY", "title": c["victim_name"],
            "subtitle": f"{c['victim_role']}, {c['victim_org']}", "status": "",
            "fields": [["Name", c["victim_name"]], ["Role", c["victim_role"]], ["Organization", c["victim_org"]],
                       ["Work email", email]],
            "blocks": [{"type": "rows", "label": "THE VICTIM'S OWN EXPOSURE",
                        "note": "Targeted scams are built from what the victim posts publicly. Check what an "
                                "attacker could have seen.",
                        "rows": [{"text": f"Search social media for {c['victim_name']}", "right": "SOCIAL >", "tone": "",
                                  "open": {"app": "social", "query": c["victim_name"]}},
                                 {"text": f"Check {email} in breach data", "right": "BREACH LOOKUP >", "tone": "",
                                  "open": {"app": "breach", "query": email}}]}],
            "pin": None}], "ABCDEFGHIJKLMNOP"
        for eid in dict.fromkeys(items):
            cd = card_for(ctx, eid)
            if cd:
                cd["kind_label"] = f"EXHIBIT {letters[len(cards) - 1]}  ·  {cd['kind_label']}"
                cards.append(cd)
        qlog(conn, cid, "casedesk.exhibits", "open", list(dict.fromkeys(items)))
        return {"cards": cards}


# --------------------------------------------------------------------------- legacy records
# Turn an entity into the flat shapes the original renderers (rec::Domain, ...) read.

def domain_record(ctx: Ctx, eid: UUID) -> dict:
    conn, cid = ctx.conn, ctx.cid
    e = conn.execute("select * from entities where id=%s", (eid,)).fetchone()
    d = conn.execute("select * from domains where entity_id=%s", (eid,)).fetchone()
    res = conn.execute("""select i.id, i.value::text ip, lower(r.valid) fs, upper(r.valid) ls
                          from entity_relationships r join entities i on i.id=r.dst_id
                          where r.src_id=%s and r.rel='resolves_to' and (r.case_id is null or r.case_id=%s)
                          order by lower(r.valid) desc nulls last""", (eid, cid)).fetchall()
    assoc, first_seen, last_seen = [], None, None
    for row in res:
        assoc.append({"ip_id": ent_int(conn, row["id"]), "ip_address": row["ip"],
                      "first_seen": iso(row["fs"]), "last_seen": iso(row["ls"]) if row["ls"] else "present"})
        if row["fs"] and (first_seen is None or row["fs"] < first_seen):
            first_seen = row["fs"]
        if row["ls"] and (last_seen is None or row["ls"] > last_seen):
            last_seen = row["ls"]
    mw = conn.execute("""select distinct mf.entity_id, mf.family from entities d
                         join entity_relationships hu on hu.src_id=d.id and hu.rel='hosts_url'
                         join entity_relationships sp on sp.src_id=hu.dst_id and sp.rel='serves_payload'
                         join entity_relationships so on so.src_id=sp.dst_id and so.rel='sample_of'
                         join malware_families mf on mf.entity_id=so.dst_id
                         where d.id=%s""", (eid,)).fetchall()
    reg = conn.execute("""select rg.name from entity_relationships r join registrars rg on rg.entity_id=r.dst_id
                          where r.src_id=%s and r.rel='registered_via' limit 1""", (eid,)).fetchone()
    ctx.seen(eid, *[m["entity_id"] for m in mw])
    return {
        "kind": "domain",
        "domain_id": ent_int(conn, eid),
        "domain_name": e["value"],
        "status": status_of(e["verdict"]),
        "first_seen": iso(first_seen), "last_seen": iso(last_seen) if last_seen else "",
        "registered": iso(d["created_on"]) if d and d["created_on"] else "",
        "registrar": reg["name"] if reg else "",
        "lookalike_of": (d["is_typosquat_of"] or "") if d else "",
        "associated_ips": assoc,
        "delivers_malware": [{"malware_id": ent_int(conn, m["entity_id"]), "family_name": m["family"]} for m in mw],
    }


def ip_record(ctx: Ctx, eid: UUID) -> dict:
    conn, cid = ctx.conn, ctx.cid
    e = conn.execute("select * from entities where id=%s", (eid,)).fetchone()
    ip = conn.execute("select * from ip_addresses where entity_id=%s", (eid,)).fetchone()
    net = conn.execute("""select a.value::text asn, hp.name provider, hp.provider_type, hp.abuse_email
                          from entity_relationships r join entities a on a.id=r.dst_id
                          join entity_relationships r2 on r2.src_id=a.id and r2.rel='operated_by'
                          join hosting_providers hp on hp.entity_id=r2.dst_id
                          where r.src_id=%s and r.rel='announced_by' limit 1""", (eid,)).fetchone()
    rep = "bulletproof" if (net and net["provider_type"] == "bulletproof") else \
          "clean" if e["verdict"] == "benign" else "mixed"
    doms = conn.execute("""select d.id, d.value::text, d.verdict, lower(r.valid) fs from entity_relationships r
                           join entities d on d.id=r.src_id
                           where r.dst_id=%s and r.rel='resolves_to' and (r.case_id is null or r.case_id=%s)
                             and (d.case_id is null or d.case_id=%s) and d.kind='domain'
                           order by lower(r.valid) desc nulls last limit 25""", (eid, cid, cid)).fetchall()
    mw = conn.execute("""select distinct mf.entity_id, mf.family from entity_relationships c2
                         join entity_relationships so on so.src_id=c2.src_id and so.rel='sample_of'
                         join malware_families mf on mf.entity_id=so.dst_id
                         where c2.dst_id=%s and c2.rel='c2_contact' and (c2.case_id is null or c2.case_id=%s)""",
                      (eid, cid)).fetchall()
    ctx.seen(eid, *[d["id"] for d in doms], *[m["entity_id"] for m in mw])
    tags = [t for t in (e["tags"] or []) if t in ("tor-exit", "vpn", "cdn", "sinkhole")]
    return {
        "kind": "ip",
        "ip_id": ent_int(conn, eid),
        "ip_address": e["value"],
        "status": status_of(e["verdict"]),
        "asn": net["asn"] if net else "",
        "provider_name": net["provider"] if net else "",
        "provider_reputation": rep,
        "abuse_email": net["abuse_email"] if net else "",
        "tags": ", ".join(tags) + (" (CDN edge: shared by many sites)" if ip and ip["is_cdn"] else ""),
        "reverse_dns": (ip["reverse_dns"] or "") if ip else "",
        "country": (ip["country"] or "") if ip else "", "region": (ip["region"] or "") if ip else "",
        "city": (ip["city"] or "") if ip else "",
        "related_domains": [{"domain_id": ent_int(conn, d["id"]), "domain_name": d["value"],
                             "status": status_of(d["verdict"]), "first_seen": iso(d["fs"])} for d in doms],
        "related_malware": [{"malware_id": ent_int(conn, m["entity_id"]), "family_name": m["family"]} for m in mw],
    }


def malware_record(ctx: Ctx, eid: UUID) -> dict:
    conn, cid = ctx.conn, ctx.cid
    f = conn.execute("select * from malware_families where entity_id=%s", (eid,)).fetchone()
    camps = conn.execute("""select c.entity_id, c.name from entity_relationships r
                            join campaigns c on c.entity_id=r.dst_id join entities ce on ce.id=c.entity_id
                            where r.src_id=%s and r.rel='used_in' and (ce.case_id is null or ce.case_id=%s)""",
                         (eid, cid)).fetchall()
    infra = conn.execute("""select distinct i.value::text ip from entity_relationships so
                            join entity_relationships c2 on c2.src_id=so.src_id and c2.rel='c2_contact'
                            join entities i on i.id=c2.dst_id
                            where so.dst_id=%s and so.rel='sample_of' and i.kind='ip'
                              and (i.case_id is null or i.case_id=%s) limit 10""", (eid, cid)).fetchall()
    ctx.seen(eid)
    return {
        "kind": "malware",
        "malware_id": ent_int(conn, eid),
        "family_name": f["family"], "name": f["family"],
        "malware_type": f["malware_type"],
        "first_observed": iso(f["first_observed"]),
        "source": "SampleBazaar (commodity: sold to many crews)" if f["is_commodity"] else "Sandboxr",
        "campaigns": [{"campaign_id": ent_int(conn, c["entity_id"]), "name": c["name"]} for c in camps],
        "infrastructure": [{"ip_address": r["ip"]} for r in infra],
    }


def campaign_record(ctx: Ctx, eid: UUID) -> dict:
    conn = ctx.conn
    c = conn.execute("select * from campaigns where entity_id=%s", (eid,)).fetchone()
    actors = conn.execute("""select t.primary_alias, s.name src, s.reliability from entity_relationships r
                             join threat_actors t on t.entity_id=r.dst_id left join sources s on s.id=r.source_id
                             where r.src_id=%s and r.rel='attributed_to' and (r.case_id is null or r.case_id=%s)""",
                          (eid, ctx.cid)).fetchall()
    ctx.seen(eid)
    return {
        "kind": "campaign",
        "campaign_id": ent_int(conn, eid),
        "name": c["name"],
        "description": f"Objective: {c['objective'] or 'unknown'}. Targeting: {c['targeting'] or 'unknown'}.",
        "active_since": iso(c["started_on"]),
        "actors": [{"alias": f"{a['primary_alias']}"} for a in actors],
        "attribution_sources": [f"{a['primary_alias']} per {a['src']} (reliability {a['reliability']})" for a in actors],
    }


def actor_record(ctx: Ctx, eid: UUID) -> dict:
    conn, cid = ctx.conn, ctx.cid
    t = conn.execute("select * from threat_actors where entity_id=%s", (eid,)).fetchone()
    camps = conn.execute("""select c.name from entity_relationships r join campaigns c on c.entity_id=r.src_id
                            join entities ce on ce.id=c.entity_id
                            where r.dst_id=%s and r.rel='attributed_to' and (ce.case_id is null or ce.case_id=%s)""",
                         (eid, cid)).fetchall()
    # infrastructure tied to this actor's own campaigns (not to whatever case is open)
    doms = conn.execute("""select distinct d.value::text, d.verdict from entity_relationships a
                           join entity_relationships u on u.dst_id=a.src_id and u.rel='used_in'
                           join entities d on d.id=u.src_id
                           where a.dst_id=%s and a.rel='attributed_to' and d.kind='domain'
                             and (d.case_id is null or d.case_id=%s) and (a.case_id is null or a.case_id=%s)
                             and coalesce(a.confidence, 3) <= 3
                           limit 8""", (eid, cid, cid)).fetchall()
    aliases = conn.execute("""select a.alias::text, s.name src from actor_aliases a left join sources s on s.id=a.named_by
                              where a.actor_id=%s order by s.name""", (eid,)).fetchall()
    ctx.seen(eid)
    alias_txt = "; ".join(f"{a['alias']} ({a['src']})" for a in aliases)
    return {
        "kind": "actor",
        "actor_id": ent_int(conn, eid),
        "alias": t["primary_alias"],
        "motivation": t["motivation"],
        "origin_region": t["suspected_origin"] or "",
        "first_attributed": "",
        "notes": ((t["notes"] or "") + ("\n\nAlso tracked as: " + alias_txt if alias_txt else "")).strip(),
        "campaigns": [{"name": c["name"]} for c in camps],
        "known_domains": [{"domain_name": d["value"], "status": status_of(d["verdict"])} for d in doms],
    }


def person_record(ctx: Ctx, eid: UUID) -> dict:
    conn = ctx.conn
    p = conn.execute("select * from persons where entity_id=%s", (eid,)).fetchone()
    accts = conn.execute("""select pe.handle::text, pe.platform from entity_relationships r
                            join personas pe on pe.entity_id=r.src_id
                            where r.dst_id=%s and r.rel='identified_as' and (r.case_id is null or r.case_id=%s)""",
                         (eid, ctx.cid)).fetchall()
    ctx.seen(eid)
    return {
        "kind": "person",
        "person_id": ent_int(conn, eid),
        "full_name": p["full_name"],
        "username": "", "email": "",
        "city": p["city"] or "", "country": p["country"] or "",
        "employer": p["employer"] or "", "job_title": p["job_title"] or "",
        "phone": "", "last_ip": "", "mac_address": "",
        "breach_count": 0, "breach_sources": "",
        "socials": {a["platform"]: "@" + a["handle"] for a in accts},
    }


def article_record(ctx: Ctx, eid: UUID) -> dict:
    a = ctx.conn.execute("""select a.*, s.reliability from web_articles a left join sources s on s.id=a.source_id
                            where a.entity_id=%s""", (eid,)).fetchone()
    ctx.seen(eid)
    rel = a["reliability"] or "?"
    return {
        "kind": "article",
        "title": a["title"], "outlet": f"{a['publisher']}  (source reliability {rel})",
        "published": iso(a["published_at"]), "body": a["body"],
        "reveals_alias": rel in ("A", "B", "C"),
    }


RECORD = {"domain": domain_record, "ip": ip_record, "malware_family": malware_record,
          "campaign": campaign_record, "threat_actor": actor_record, "person": person_record,
          "web_article": article_record}
ENVELOPE_KEY = {"domain": "domains", "ip": "ips", "malware_family": "malware",
                "campaign": "campaigns", "threat_actor": "actors", "person": "persons",
                "web_article": "articles"}


def envelope(ctx: Ctx, q: str, hits: list[tuple[str, UUID]], empty: str) -> dict:
    """Group (kind, uuid) hits into legacy record lists; anything else becomes a card."""
    out: dict[str, list] = {}
    cards, seen = [], set()
    for kind, eid in hits:
        if eid in seen:
            continue
        seen.add(eid)
        if kind in ENVELOPE_KEY:
            out.setdefault(ENVELOPE_KEY[kind], []).append(RECORD[kind](ctx, eid))
        elif kind in BUILDERS:
            cards.append(card_for(ctx, eid))
    return result(q, cards, empty, **out)


# --------------------------------------------------------------------------- original tools
@router.get("/intel")
def intel(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = host_of(q) if ("/" in q or q.lower().startswith("http")) else q.strip()
        rows = conn.execute("select * from intel_search(%s,%s,30)", (cid, term)).fetchall()
        keep = ("domain", "ip", "malware_family", "url")
        hits = [(r["kind"], r["entity_id"]) for r in rows if r["kind"] in keep]
        qlog(conn, cid, "intelsearch", q, [h[1] for h in hits])
        return envelope(Ctx(conn, cid, "intelsearch"), q, hits,
                        f"Nothing indexed for \"{q}\". Paste a domain, URL or IP exactly as you found it.")


@router.get("/intel/domain/{n}")
def intel_domain(n: int, case_id: int):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        eid = need_ent(conn, n)
        case_visible(conn, cid, eid)
        qlog(conn, cid, "intel.domain", str(n), [eid])
        return domain_record(Ctx(conn, cid, "intelsearch"), eid)


@router.get("/intel/ip/{n}")
def intel_ip(n: int, case_id: int):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        eid = need_ent(conn, n)
        case_visible(conn, cid, eid)
        qlog(conn, cid, "intel.ip", str(n), [eid])
        return ip_record(Ctx(conn, cid, "intelsearch"), eid)


@router.get("/malware")
def malware(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        rows = conn.execute("""select e.id from entities e join malware_families f on f.entity_id=e.id
                               where f.family ilike %s""", (f"%{q.strip()}%",)).fetchall()
        term = q.strip().lower()
        samples = conn.execute("""select e.id from malware_samples m join entities e on e.id=m.entity_id
                                  where (e.case_id is null or e.case_id=%s)
                                    and (m.sha256=%s or m.sha1=%s or m.md5=%s or m.file_name ilike %s)""",
                               (cid, term, term, term, f"%{term}%")).fetchall()
        hits = [("malware_family", r["id"]) for r in rows] + [("malware_sample", r["id"]) for r in samples]
        qlog(conn, cid, "malware", q, [h[1] for h in hits])
        return envelope(Ctx(conn, cid, "malwaredb"), q, hits, f"No malware family, hash or file name matches \"{q}\".")


@router.get("/directory")
def directory(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = f"%{q.strip()}%"
        actors = conn.execute("""select distinct t.entity_id from threat_actors t
                                 left join actor_aliases a on a.actor_id=t.entity_id
                                 where t.primary_alias ilike %s or a.alias::text ilike %s""", (term, term)).fetchall()
        people = conn.execute("""select e.id from entities e join persons p on p.entity_id=e.id
                                 where (e.case_id is null or e.case_id=%s)
                                   and (p.full_name ilike %s or p.employer ilike %s) limit 25""",
                              (cid, term, term)).fetchall()
        hits = [("threat_actor", r["entity_id"]) for r in actors] + [("person", r["id"]) for r in people]
        qlog(conn, cid, "directory", q, [h[1] for h in hits])
        return envelope(Ctx(conn, cid, "directory"), q, hits,
                        f"No actor alias or person matches \"{q}\". Vendors use different names for the same group.")


@router.get("/websearch")
def websearch(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        rows = conn.execute("""select e.id from web_articles a join entities e on e.id=a.entity_id
                               where (e.case_id is null or e.case_id=%s)
                               and (a.title ilike %s or a.body ilike %s
                                    or to_tsvector('english', a.title||' '||a.body) @@ websearch_to_tsquery('english', %s))
                               order by a.published_at desc limit 20""",
                           (cid, f"%{q}%", f"%{q}%", q)).fetchall()
        arts = [r["id"] for r in rows]
        # a campaign an article names gets its own result, like a knowledge panel
        camps = conn.execute("""select distinct c.entity_id from entity_relationships r
                                join campaigns c on c.entity_id=r.dst_id join entities ce on ce.id=c.entity_id
                                join web_articles a on a.entity_id=r.src_id
                                where r.src_id = any(%s::uuid[]) and r.rel='mentions'
                                  and (ce.case_id is null or ce.case_id=%s)
                                  and position(lower(c.name) in lower(a.body)) > 0""", (arts, cid)).fetchall()
        hits = [("campaign", r["entity_id"]) for r in camps] + [("web_article", a) for a in arts]
        qlog(conn, cid, "websearch", q, [h[1] for h in hits])
        return envelope(Ctx(conn, cid, "websearch"), q, hits, f"No published reporting matches \"{q}\".")


# --------------------------------------------------------------------------- card tools
@router.get("/card/{n}")
def one_card(n: int, case_id: int):
    """Any single record, for links between tools."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        eid = need_ent(conn, n)
        e = case_visible(conn, cid, eid)
        ctx = Ctx(conn, cid, f"card.{e['kind']}")
        qlog(conn, cid, f"card.{e['kind']}", str(e["value"]), [eid])
        if e["kind"] in RECORD:
            return RECORD[e["kind"]](ctx, eid)
        c = card_for(ctx, eid)
        if not c:
            raise HTTPException(404, "no viewer for this record")
        return c


def run_cards(conn, cid: UUID, tool: str, q: str, ids: list[UUID], empty: str, **extra) -> dict:
    ctx = Ctx(conn, cid, tool)
    ids = list(dict.fromkeys(ids))
    qlog(conn, cid, tool, q, ids)
    return result(q, [c for c in (card_for(ctx, i) for i in ids) if c], empty, **extra)


@router.get("/social")
def social(case_id: int, q: str = Query(min_length=1)):
    """Social-media search: profiles by handle, name or bio, and posts/DMs by text.
    A post that matches also returns the profile that wrote it."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip().lstrip("@")
        like = f"%{term}%"
        posts = [r["id"] for r in conn.execute(
            """select e.id from social_posts p join entities e on e.id=p.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (p.body ilike %s or p.author_handle::text ilike %s
                      or to_tsvector('simple', p.body) @@ plainto_tsquery('simple', %s))
               order by p.posted_at limit 25""", (cid, like, like, term)).fetchall()]
        personas = [r["id"] for r in conn.execute(
            """select e.id from personas p join entities e on e.id=p.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (p.handle::text ilike %s or p.display_name ilike %s or p.bio ilike %s
                      or exists (select 1 from entity_relationships r where r.src_id=e.id and r.rel='posted'
                                 and r.dst_id = any(%s::uuid[])))
               order by (p.handle::text ilike %s) desc, p.handle limit 15""",
            (cid, like, like, like, posts, term)).fetchall()]
        return run_cards(conn, cid, "social", q, personas + posts,
                         f"No profile, post or message matches \"{q}\". Try the exact handle, a name, or a phrase "
                         f"from a message.")


@router.get("/reverseimage")
def reverseimage(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip()
        rows = conn.execute("""select e.id from images i join entities e on e.id=i.entity_id
                               where (e.case_id is null or e.case_id=%s)
                                 and (e.value = %s::citext or i.phash = lower(%s) or e.id::text = %s)""",
                            (cid, term, term, term)).fetchall()
        ctx = Ctx(conn, cid, "reverseimage")
        cards = [image_card(ctx, r["id"], sightings=True) for r in rows]
        qlog(conn, cid, "reverseimage", q, [r["id"] for r in rows])
        return result(q, cards, "That image isn't in the index. Use the Image ID (img:...) from a profile or exhibit, "
                                "or its perceptual hash.")


@router.get("/phone")
def phone(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        digits = re.sub(r"\D", "", q)
        if len(digits) < 4:
            return result(q, [], "Enter at least four digits of the number.")
        ids = [r["id"] for r in conn.execute(
            """select e.id from phone_numbers p join entities e on e.id=p.entity_id
               where (e.case_id is null or e.case_id=%s) and regexp_replace(p.e164, '\\D', '', 'g') like %s
               order by p.spam_reports desc limit 15""", (cid, f"%{digits}%")).fetchall()]
        return run_cards(conn, cid, "phone", q, ids, f"No carrier record for {q}.")


@router.get("/sms")
def sms(case_id: int, q: str = Query(min_length=1)):
    """Carrier spam-report database (what people forward to 7726)."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        digits = re.sub(r"\D", "", q)
        ids = [r["id"] for r in conn.execute(
            """select e.id from sms_messages s join entities e on e.id=s.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (s.body ilike %s or (length(%s) >= 4 and regexp_replace(s.from_number, '\\D', '', 'g') like %s))
               order by s.sent_at limit 25""", (cid, f"%{q.strip()}%", digits, f"%{digits}%")).fetchall()]
        return run_cards(conn, cid, "sms", q, ids, f"No reported text messages match \"{q}\".")


@router.get("/documents")
def documents(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        like = f"%{q.strip()}%"
        ids = [r["id"] for r in conn.execute(
            """select e.id from documents d join entities e on e.id=d.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (d.file_name ilike %s or d.text_excerpt ilike %s or d.sha256=lower(%s) or d.meta_author ilike %s
                      or d.meta_last_modified_by ilike %s or d.meta_company ilike %s)""",
            (cid, like, like, q.strip(), like, like, like)).fetchall()]
        return run_cards(conn, cid, "doclab", q, ids, f"No document matches \"{q}\".")


@router.get("/audio")
def audio(case_id: int, q: str = Query(min_length=1)):
    """Audio lab: search transcripts, speakers, caller IDs, or match a voiceprint."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        like = f"%{q.strip()}%"
        ids = [r["id"] for r in conn.execute(
            """select e.id from audio_recordings a join entities e on e.id=a.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (a.transcript ilike %s or a.speaker_claimed ilike %s or a.caller_id ilike %s
                      or a.voiceprint_hash = lower(%s) or a.source_url ilike %s)
               order by a.recorded_at""", (cid, like, like, like, q.strip(), like)).fetchall()]
        return run_cards(conn, cid, "audiolab", q, ids, f"No recording matches \"{q}\".")


@router.get("/payments")
def payments(case_id: int, q: str = Query(min_length=1)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        like = f"%{q.strip()}%"
        ids = [r["id"] for r in conn.execute(
            """select e.id from payment_accounts p join entities e on e.id=p.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (p.identifier ilike %s or p.provider ilike %s or p.holder_name ilike %s or e.value ilike %s)
               limit 20""", (cid, like, like, like, like)).fetchall()]
        ids += [r["id"] for r in conn.execute(
            """select e.id from crypto_wallets w join entities e on e.id=w.entity_id
               where (e.case_id is null or e.case_id=%s) and w.address like %s limit 20""",
            (cid, q.strip() + "%")).fetchall()]
        return run_cards(conn, cid, "payments", q, ids, f"No account matches \"{q}\".")


@router.get("/moneytrail")
def moneytrail(case_id: int, q: str = Query(min_length=1)):
    """Follow money forward from an account or wallet, hop by hop (recursive CTE in SQL)."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip()
        starts = conn.execute(
            """select e.id, e.value::text v from entities e
               left join crypto_wallets w on w.entity_id=e.id left join payment_accounts p on p.entity_id=e.id
               where (e.case_id is null or e.case_id=%s) and e.kind in ('crypto_wallet','payment_account')
                 and (w.address = %s or p.identifier = %s or e.value = %s::citext)""",
            (cid, term, term, term)).fetchall()
        if not starts:
            starts = conn.execute(
                """select e.id, e.value::text v from entities e
                   left join crypto_wallets w on w.entity_id=e.id left join payment_accounts p on p.entity_id=e.id
                   where (e.case_id is null or e.case_id=%s) and e.kind in ('crypto_wallet','payment_account')
                     and (w.address like %s or p.identifier ilike %s) limit 12""",
                (cid, term + "%", f"%{term}%")).fetchall()
        ctx = Ctx(conn, cid, "moneytrail")
        if len(starts) != 1:
            qlog(conn, cid, "moneytrail", q, [s["id"] for s in starts])
            cards = [card_for(ctx, s["id"]) for s in starts]
            return result(q, cards, f"No account or wallet starts with \"{q}\". Paste the full address or account "
                                    f"identifier.") | ({"message": f"{len(cards)} accounts match. Pick one and trace "
                                                                   f"it."} if cards else {})
        start = starts[0]["id"]
        hops = conn.execute("select * from money_trail(%s, %s, 6)", (cid, start)).fetchall()
        rows = []
        for h in hops:
            rows.append({"text": f"hop {h['depth']}   {short(option_label(conn, h['from_id']))}  ->  "
                                 f"{short(option_label(conn, h['to_id']))}",
                         "right": iso(h["moved_at"]) or "date unknown", "tone": "",
                         "fetch": {"app": "moneytrail", "path": f"/api/card/{ent_int(conn, h['to_id'])}", "params": {}}})
        ledger = {"card": "ledger", "kind_label": "MONEY TRAIL", "title": option_label(conn, start),
                  "subtitle": f"{len(hops)} outgoing transfer(s) followed", "status": "", "fields": [],
                  "blocks": [{"type": "rows", "label": "TRANSFERS, IN ORDER",
                              "note": "Each hop is a real transfer on the ledger. Funds usually stop at an exchange "
                                      "deposit address, where the criminal turns them into cash.", "rows": rows}]
                  if rows else [{"type": "text", "label": "TRANSFERS",
                                 "text": "No outgoing transfers recorded from this account."}],
                  "pin": None}
        ids = [start] + [h["to_id"] for h in hops]
        qlog(conn, cid, "moneytrail", q, ids)
        cards = [ledger] + [c for c in (card_for(ctx, i) for i in dict.fromkeys(ids)) if c]
        return result(q, cards, "")


def short(v: str, n: int = 22) -> str:
    return v if len(v) <= n else v[: n - 3] + "..."


@router.get("/complaints")
def complaints(case_id: int, q: str = Query(min_length=1)):
    """ScamWatch Portal: other victims' reports. Corroboration, and noise."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip().lstrip("@$")
        digits = re.sub(r"\D", "", term)
        ids = [r["id"] for r in conn.execute(
            """select e.id from complaints c join entities e on e.id=c.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (c.narrative ilike %s
                      or exists (select 1 from unnest(c.indicators) i
                                 where i ilike %s or (length(%s) >= 7 and regexp_replace(i, '\\D', '', 'g') = %s))
                      or to_tsvector('english', c.narrative) @@ websearch_to_tsquery('english', %s))
               order by c.filed_at desc limit 30""", (cid, f"%{term}%", f"%{term}%", digits, digits, term)).fetchall()]
        return run_cards(conn, cid, "complaints", q, ids, f"No fraud reports match \"{q}\".")


@router.get("/dns")
def dns(case_id: int, q: str = Query(min_length=1)):
    """Passive DNS: every resolution ever observed, both directions, with time windows."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = host_of(q)
        rows = conn.execute("select * from pdns(%s, %s)", (cid, term)).fetchall()
        ids = [r["id"] for r in conn.execute(
            "select id from entities where value = any(%s) and (case_id is null or case_id=%s)",
            ([r["domain"] for r in rows] + [r["ip"] for r in rows], cid)).fetchall()]
        qlog(conn, cid, "dns", q, ids)
        Ctx(conn, cid, "dns").seen(*ids)
        if not rows:
            return result(q, [], f"No DNS observations for \"{term}\".")
        is_ip = all(r["ip"] == term for r in rows)
        out = []
        for r in rows:
            other = r["domain"] if is_ip else r["ip"]
            span = f"{iso(r['first_seen']) or '?'}  to  {iso(r['last_seen']) if r['last_seen'] else 'present'}"
            out.append({"text": f"{r['domain']}  ->  {r['ip']}", "right": span, "tone": "",
                        "open": {"app": "intelsearch", "query": other}})
        c = {"card": "pdns", "kind_label": "PASSIVE DNS", "title": term,
             "subtitle": f"{len(rows)} observation(s), newest first", "status": "", "fields": [],
             "blocks": [{"type": "rows", "label": "RESOLUTIONS (first seen to last seen)",
                         "note": "Where did it point when the victim clicked? Today's answer is often a sinkhole "
                                 "or a CDN, not the attacker.", "rows": out}], "pin": None}
        return result(q, [c], "")


@router.get("/whois")
def whois(case_id: int, q: str = Query(min_length=1)):
    """WHOIS history for a domain, or every snapshot that lists a registrant email."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip() if "@" in q else host_of(q)
        ids = [r["id"] for r in conn.execute(
            """select e.id from whois_records w join entities e on e.id=w.entity_id
               where (e.case_id is null or e.case_id=%s) and (w.domain_fqdn = %s or w.registrant_email ilike %s)
               order by w.captured_at""", (cid, term, term)).fetchall()]
        return run_cards(conn, cid, "whois", q, ids,
                         f"No WHOIS history for \"{term}\". Search the bare domain (example.test), not a URL.")


@router.get("/certs")
def certs(case_id: int, q: str = Query(min_length=3)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        ids = [r["entity_id"] for r in conn.execute("select * from ct_search(%s, %s)", (cid, host_of(q))).fetchall()]
        return run_cards(conn, cid, "certs", q, ids[:30], f"No certificates in the CT logs mention \"{q}\".")


@router.get("/urlscan")
def urlscan(case_id: int, q: str = Query(min_length=3)):
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip()
        ids = [r["id"] for r in conn.execute(
            """select e.id from url_scans s join entities e on e.id=s.entity_id
               where (e.case_id is null or e.case_id=%s)
                 and (s.scanned_url ilike %s or s.final_url ilike %s or host(s.ip_seen)=%s)
               order by s.scanned_at desc limit 25""", (cid, f"%{term}%", f"%{term}%", term)).fetchall()]
        # URLs on file that were never scanned themselves (payload downloads, redirectors)
        ids += [r["id"] for r in conn.execute(
            """select e.id from urls u join entities e on e.id=u.entity_id
               where (e.case_id is null or e.case_id=%s) and u.full_url ilike %s
                 and not exists (select 1 from entity_relationships r where r.src_id=e.id and r.rel='scanned_as')
               limit 10""", (cid, f"%{term}%")).fetchall()]
        return run_cards(conn, cid, "urlscan", q, ids, f"No scans of \"{q}\" on file.")


PIVOT_FIELDS = {"tracking_id", "favicon", "jarm", "nameserver", "registrant_email", "imphash"}


@router.get("/pivot")
def pivot(case_id: int, field: str, value: str):
    if field not in PIVOT_FIELDS:
        raise HTTPException(400, "unknown pivot")
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        rows = conn.execute("select * from pivot(%s, %s, %s)", (cid, field, value)).fetchall()
        ctx = Ctx(conn, cid, f"pivot.{field}")
        ids = [r["entity_id"] for r in rows][:40]
        qlog(conn, cid, f"pivot.{field}", value, ids)
        cards, legacy = [], {}
        for eid in ids:
            kind = conn.execute("select kind::text k from entities where id=%s", (eid,)).fetchone()["k"]
            if kind == "domain":
                legacy.setdefault("domains", []).append(domain_record(ctx, eid))
            else:
                c = card_for(ctx, eid)
                if c:
                    cards.append(c)
        return result(f"{field} = {value}", cards, f"Nothing else shares {field} {value}.", **legacy)


@router.get("/breach")
def breach(case_id: int, q: str = Query(min_length=3)):
    """Breach lookup by exact email or username, like a leaked-credential search."""
    with tx() as conn:
        cid = case_uuid(conn, case_id)
        term = q.strip().lstrip("@")
        recs = conn.execute("""select b.entity_id bid, b.breach_name, b.breach_date, b.records, b.data_classes,
                                      r.email::text email, r.username::text username, r.display_name, r.hash_type,
                                      left(r.password_hash, 14) h, host(r.signup_ip) ip
                               from breach_records r join breaches b on b.entity_id=r.breach_id
                               where (r.case_id is null or r.case_id=%s) and (r.email = %s or r.username = %s)
                               order by b.breach_date""", (cid, term, term)).fetchall()
        ctx = Ctx(conn, cid, "breach")
        cards = []
        addr = conn.execute("""select id from entities where kind='email_address' and value=%s::citext
                               and (case_id is null or case_id=%s) limit 1""", (term, cid)).fetchone()
        if addr:
            cards.append(card_for(ctx, addr["id"]))
        for r in recs:
            ctx.seen(r["bid"])
            pivots = []
            if r["email"] and r["email"].lower() != term.lower():
                pivots.append({"text": f"Email {r['email']}", "right": "BREACH LOOKUP >", "tone": "",
                               "open": {"app": "breach", "query": r["email"]}})
            if r["username"]:
                pivots.append({"text": f"Username {r['username']}  ·  search every platform", "right": "SOCIAL >",
                               "tone": "", "open": {"app": "social", "query": r["username"]}})
                if r["username"].lower() != term.lower():
                    pivots.append({"text": f"Username {r['username']}  ·  other breaches", "right": "BREACH LOOKUP >",
                                   "tone": "", "open": {"app": "breach", "query": r["username"]}})
            cards.append({"card": "breach_record", "kind_label": "BREACH RECORD", "title": r["breach_name"],
                          "subtitle": f"breached {iso(r['breach_date'])}  ·  {r['records']:,} accounts", "status": "",
                          "fields": [[k, v] for k, v in [("Email", r["email"]), ("Username", r["username"]),
                                                         ("Display name", r["display_name"]),
                                                         ("Password hash", f"{r['hash_type']}  {r['h']}..." if r["h"] else None),
                                                         ("Sign-up IP", r["ip"]),
                                                         ("Data exposed", ", ".join(r["data_classes"]))] if v],
                          "blocks": [{"type": "rows", "label": "PIVOTS",
                                      "note": "People reuse usernames and emails for years. That reuse is how "
                                              "anonymous accounts get tied to real people.", "rows": pivots}],
                          "pin": {"entity_kind": "breach", "entity_id": ent_int(conn, r["bid"]),
                                  "label": f"Breach: {r['breach_name']}"}})
        qlog(conn, cid, "breach", q, ([addr["id"]] if addr else []) + [r["bid"] for r in recs])
        return result(q, cards, f"\"{term}\" does not appear in any indexed breach. Breach search needs an exact "
                                f"email address or username.")


# --------------------------------------------------------------------------- evidence
def _ev(conn, cid: UUID) -> dict:
    rows = conn.execute("""select e.id, e.kind::text kind, coalesce(e.label, e.value::text) label
                           from case_evidence ev join entities e on e.id=ev.entity_id
                           where ev.case_id=%s order by ev.added_at""", (cid,)).fetchall()
    return {"items": [{"evidence_id": ent_int(conn, r["id"]), "entity_kind": r["kind"],
                       "entity_id": ent_int(conn, r["id"]), "label": r["label"]} for r in rows]}


@router.get("/cases/{n}/evidence")
def list_evidence(n: int):
    with tx() as conn:
        return _ev(conn, case_uuid(conn, n))


class PinIn(BaseModel):
    model_config = {"extra": "allow"}
    entity_kind: str = ""
    entity_id: int


@router.post("/cases/{n}/evidence")
def pin(n: int, body: PinIn):
    with tx() as conn:
        cid = case_uuid(conn, n)
        if conn.execute("select status from cases where id=%s", (cid,)).fetchone()["status"] != "open":
            raise HTTPException(409, "case is closed")
        eid = ent_uuid(conn, body.entity_id)
        if not eid or not conn.execute("select 1 from case_discoveries where case_id=%s and entity_id=%s",
                                       (cid, eid)).fetchone():
            raise HTTPException(409, "not discovered")
        case_visible(conn, cid, eid)
        conn.execute("insert into case_evidence(case_id, entity_id) values (%s,%s) on conflict do nothing", (cid, eid))
        messenger.on_pin(conn, cid, eid)
        return _ev(conn, cid)


@router.delete("/cases/{n}/evidence/{eid}")
def unpin(n: int, eid: int):
    with tx() as conn:
        cid = case_uuid(conn, n)
        euuid = ent_uuid(conn, eid)
        if euuid:
            conn.execute("delete from case_evidence where case_id=%s and entity_id=%s", (cid, euuid))
        return _ev(conn, cid)


# --------------------------------------------------------------------------- hint
@router.post("/cases/{n}/hint")
def hint(n: int):
    with tx() as conn:
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


# --------------------------------------------------------------------------- report
def option_label(conn, eid: UUID) -> str:
    e = conn.execute("select kind::text k, value::text v, coalesce(label, value::text) l from entities where id=%s",
                     (eid,)).fetchone()
    k = e["k"]
    if k == "persona":
        p = conn.execute("select handle::text h, platform from personas where entity_id=%s", (eid,)).fetchone()
        return f"@{p['h']} ({p['platform'].split(' (')[0]})"
    if k == "threat_actor":
        return conn.execute("select primary_alias a from threat_actors where entity_id=%s", (eid,)).fetchone()["a"]
    if k == "phone":
        from .cards import phone_pretty
        return phone_pretty(e["v"])
    if k == "audio_recording":
        a = conn.execute("select recording_type t, speaker_claimed s, recorded_at d from audio_recordings "
                         "where entity_id=%s", (eid,)).fetchone()
        return f"{a['t'].replace('_', ' ')}: {a['s']} ({iso(a['d'])})"
    if k in ("domain", "ip", "email_address", "crypto_wallet", "campaign"):
        return e["v"]
    return e["l"]


def ordered_slots(conn, cid: UUID) -> dict:
    """Answer slots in the order the scenario's report form declares them."""
    row = conn.execute("""select g.answer_slots, s.report_fields from case_ground_truth g
                          join cases c on c.id=g.case_id left join scenarios s on s.key=c.scenario
                          where g.case_id=%s""", (cid,)).fetchone()
    order = [f["key"] for f in (row["report_fields"] or [])] + ["campaign", "actor", "person"]
    rank = {k: i for i, k in enumerate(order)}
    return dict(sorted(row["answer_slots"].items(), key=lambda kv: rank.get(kv[0], len(rank))))


@router.get("/cases/{n}/report-options")
def report_options(n: int):
    """One field per answer slot the scenario declares. Each offers only entities of
    that kind the player has actually surfaced, so nothing can be guessed from a list."""
    with tx() as conn:
        cid = case_uuid(conn, n)
        slots = ordered_slots(conn, cid)
        fields = []
        for key, spec in slots.items():
            found = conn.execute("""select d.entity_id from case_discoveries d join entities e on e.id=d.entity_id
                                    where d.case_id=%s and e.kind=%s order by d.first_seen""",
                                 (cid, spec["kind"])).fetchall()
            fields.append({"key": key, "label": spec["label"], "kind": spec["kind"],
                           "options": [{"entity_id": ent_int(conn, r["entity_id"]),
                                        "label": option_label(conn, r["entity_id"])} for r in found]})
        return {"fields": fields}


class SubmitIn(BaseModel):
    model_config = {"extra": "allow"}
    answers: dict[str, int] = {}
    # legacy four-field form
    actor_id: Optional[int] = None
    campaign_id: Optional[int] = None
    domain_id: Optional[int] = None
    malware_id: Optional[int] = None


LEGACY_FIELD_TO_SLOTS = {"actor_id": ["actor"], "campaign_id": ["campaign"],
                         "domain_id": ["primary_domain", "lookalike_domain", "popup_domain", "fake_platform"],
                         "malware_id": ["malware_family"]}


@router.post("/cases/{n}/submit")
def submit(n: int, body: SubmitIn):
    with tx() as conn:
        cid = case_uuid(conn, n)
        c = conn.execute("select * from cases where id=%s", (cid,)).fetchone()
        if c["status"] != "open":
            raise HTTPException(409, "case is closed")
        slots = ordered_slots(conn, cid)

        picked: dict[str, int] = dict(body.answers)
        for field, keys in LEGACY_FIELD_TO_SLOTS.items():
            val = getattr(body, field)
            slot = next((k for k in keys if k in slots), None)
            if val is not None and slot and slot not in picked:
                picked[slot] = val
        answer = {k: str(ent_uuid(conn, v)) for k, v in picked.items() if k in slots and ent_uuid(conn, v)}

        ev = [r["entity_id"] for r in conn.execute("select entity_id from case_evidence where case_id=%s", (cid,)).fetchall()]
        res = scoring.grade(conn, c, answer, ev)
        conn.execute("""insert into submissions(case_id, answer, evidence, correct, score, breakdown)
                        values (%s,%s,%s,%s,%s,%s)""",
                     (cid, json.dumps(answer), ev, res["correct"], res["score"], json.dumps(res)))
        if res["correct"]:
            conn.execute("update cases set status='solved', score=%s, closed_at=now() where id=%s", (res["score"], cid))
        else:
            conn.execute("update cases set attempts=attempts+1 where id=%s", (cid,))
        messenger.on_report(conn, cid, res["correct"])
        attempt_no = conn.execute("select attempts from cases where id=%s", (cid,)).fetchone()["attempts"]

        hard = c["difficulty"] in ("hard", "expert")
        verdicts = []
        for key, spec in slots.items():
            sub = option_label(conn, UUID(answer[key])) if key in answer else "(none)"
            v = {"field": spec["label"], "submitted": sub}
            if res["correct"] or not hard:
                v["correct"] = bool(res["fields"].get(key))
            verdicts.append(v)
        n_right = sum(bool(x) for x in res["fields"].values())

        notes = []
        if res["correct"]:
            gt = conn.execute("select resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
            narrative = gt["resolution_text"]
            for e in res["misleading_evidence"]:
                why = conn.execute("""select coalesce(e.label, e.value::text) l, ce.explanation x from case_entities ce
                                      join entities e on e.id=ce.entity_id where ce.case_id=%s and ce.entity_id=%s""",
                                   (cid, UUID(e))).fetchone()
                notes.append(f"Misleading evidence on your board: {why['l']}. {why['x'] or ''}".strip())
            for k in res["unsupported_conclusions"]:
                notes.append(f"Right answer, but your pinned evidence doesn't connect to it: {slots[k]['label']}. "
                             f"Pin the records that link the clue to it.")
            if res["disconnected_evidence"]:
                notes.append(f"{len(res['disconnected_evidence'])} pinned record(s) don't connect to the chain.")
            if res["hint_penalty"]:
                notes.append(f"Hints cost {res['hint_penalty']} points.")
            for f in conn.execute("""select body from case_client_facts where case_id=%s and secret
                                     and revealed_at is null""", (cid,)).fetchall():
                notes.append("The client never told you: " + f["body"].lstrip(". "))
        elif hard:
            narrative = (f"{n_right} of {len(slots)} conclusions are correct. On this difficulty the desk won't say "
                         f"which. Re-check the weakest link in your chain.")
        else:
            narrative = "Not every conclusion holds up. The fields marked XX need another look."
        if not res["correct"] and res["misleading_evidence"]:
            notes.append(f"{len(res['misleading_evidence'])} item(s) on your evidence board are red herrings "
                         f"or planted false flags.")
        return {"is_correct": res["correct"], "score": res["score"], "attempt_no": attempt_no,
                "verdicts": verdicts, "narrative": narrative, "notes": notes,
                "correct_count": n_right, "total": len(slots)}


# --------------------------------------------------------------------------- graph
@router.get("/cases/{n}/graph")
def graph(n: int):
    """Evidence Map: pinned entities plus their immediate neighbours."""
    with tx() as conn:
        cid = case_uuid(conn, n)
        pinned = [r["entity_id"] for r in conn.execute(
            "select entity_id from case_evidence where case_id=%s", (cid,)).fetchall()]
        if not pinned:
            return {"nodes": [], "edges": []}
        node_ids = set(pinned)
        edges = []
        rows = conn.execute("""select r.src_id, r.dst_id, r.rel::text rel, r.confidence
                               from entity_relationships r
                               join entities a on a.id=r.src_id join entities b on b.id=r.dst_id
                               where (r.src_id = any(%s::uuid[]) or r.dst_id = any(%s::uuid[]))
                                 and (r.case_id is null or r.case_id=%s)
                                 and (a.case_id is null or a.case_id=%s) and (b.case_id is null or b.case_id=%s)
                               limit 400""", (pinned, pinned, cid, cid, cid)).fetchall()
        for r in rows:
            node_ids.add(r["src_id"])
            node_ids.add(r["dst_id"])
            edges.append({"src": str(r["src_id"]), "dst": str(r["dst_id"]), "label": r["rel"].replace("_", " "),
                          "confidence": round((7 - (r["confidence"] or 3)) / 6, 2)})
        ctx = Ctx(conn, cid, "evidencemap")
        ctx.seen(*node_ids)
        nodes = []
        for nid in node_ids:
            e = conn.execute("select kind::text, value::text v, verdict::text from entities where id=%s", (nid,)).fetchone()
            nodes.append({"node_id": str(nid), "entity_id": ent_int(conn, nid), "kind": e["kind"],
                          "label": option_label(conn, nid)[:36], "query": e["v"],
                          "sublabel": e["kind"].replace("_", " "), "status": status_of(e["verdict"]),
                          "in_evidence": nid in pinned})
        qlog(conn, cid, "graph", "", list(node_ids))
        return {"nodes": nodes, "edges": edges}
