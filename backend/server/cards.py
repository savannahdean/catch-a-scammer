"""Record "cards" for the desktop client's investigation tools.

The C++ client draws one generic card shape, so every tool (social search,
reverse image, phone lookup, document lab, money trail, ...) is described
here, server-side. That keeps the client a thin renderer with no game logic,
and it means a new tool is a route plus a builder in this file.

A card:
    {"card": kind, "kind_label": "SOCIAL PROFILE", "title": ..., "subtitle": ...,
     "status": "malicious|suspicious|clean|unknown" (only where a real tool rates things),
     "fields": [[key, value, tone?], ...],
     "blocks": [{"type": "text"|"mono", "label", "text"},
                {"type": "meter", "label", "value", "low", "high", "note"},
                {"type": "rows", "label", "note", "rows": [row, ...]}],
     "pin": {"entity_kind", "entity_id", "label"}}
A row: {"text", "right", "tone", plus one action:
        "open": {"app", "query"}                 open another tool with a query, or
        "fetch": {"app", "path", "params"}}      load a record into a tool window.

Cards only show what the real tool would show. Analyst conclusions stored on
edges (notes like "voiceprint matches...") are never printed; the player has
to draw them. Every entity a card shows is recorded in case_discoveries.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

# --------------------------------------------------------------------------- int <-> uuid
# The client uses `long long` ids everywhere: the `seq` identity column every
# case and entity gets when it is created (migration 006). Read-only lookups.


def case_int(conn, case_uuid: UUID) -> int:
    return conn.execute("select seq from cases where id=%s", (case_uuid,)).fetchone()["seq"]


def ent_int(conn, entity_uuid: UUID) -> int:
    return conn.execute("select seq from entities where id=%s", (entity_uuid,)).fetchone()["seq"]


# --------------------------------------------------------------------------- context
@dataclass
class Ctx:
    """One request: the connection, the case, and which tool is asking."""
    conn: Any
    cid: UUID
    tool: str

    def seen(self, *eids: Optional[UUID]) -> None:
        ids = [e for e in eids if e]
        if ids:
            self.conn.execute("""insert into case_discoveries(case_id, entity_id, tool)
                                 select %s, x, %s from unnest(%s::uuid[]) x
                                 on conflict do nothing""", (self.cid, self.tool, ids))

    def incident(self) -> datetime:
        if not hasattr(self, "_incident"):
            self._incident = self.conn.execute("select incident_at from cases where id=%s", (self.cid,)).fetchone()["incident_at"]
        return self._incident


# --------------------------------------------------------------------------- formatting
def dt(v) -> str:
    return v.strftime("%Y-%m-%d %H:%M UTC") if isinstance(v, datetime) else (str(v) if v else "")


def day(v) -> str:
    return v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else (str(v) if v else "")


def before_incident(ctx: Ctx, v) -> str:
    """'41 days before the incident' -- account/registration age is a classic red flag."""
    if not v:
        return ""
    if not isinstance(v, datetime):
        v = datetime(v.year, v.month, v.day, tzinfo=ctx.incident().tzinfo)
    days = (ctx.incident() - v).days
    if days < 0:
        return f"{day(v)}  ({-days} days after the incident)"
    if days < 2:
        return f"{day(v)}  (days before the incident)"
    if days < 60:
        return f"{day(v)}  ({days} days before the incident)"
    return f"{day(v)}  ({days // 365} yr {days % 365 // 30} mo before the incident)" if days >= 365 else \
           f"{day(v)}  ({days // 30} months before the incident)"


def phone_pretty(e164: str) -> str:
    return f"({e164[2:5]}) {e164[5:8]}-{e164[8:]}" if e164 and e164.startswith("+1") and len(e164) == 12 else (e164 or "")


def money(v) -> str:
    return f"${float(v):,.2f}" if v is not None else ""


def short_platform(p: str) -> str:
    return p.split(" (")[0] if p else ""


URL_RE = re.compile(r"(https?://[^\s\"'<>)]+|\b[a-z0-9][a-z0-9-]*(?:\.[a-z0-9-]+)*\.(?:example|test)(?:/[^\s\"'<>)]*)?)", re.I)
PHONE_RE = re.compile(r"\(\d{3}\) \d{3}-\d{4}|\+1\d{10}")


def host_of(s: str) -> str:
    s = s.strip()
    s = re.sub(r"^[a-z]+://", "", s, flags=re.I)
    return s.split("/")[0].split("?")[0].split(":")[0].strip(".").lower()


def to_e164(s: str) -> str:
    d = re.sub(r"\D", "", s)
    return f"+1{d}" if len(d) == 10 else (f"+{d}" if d else "")


# --------------------------------------------------------------------------- actions
def open_(app: str, query: str) -> dict:
    return {"open": {"app": app, "query": query}}


def fetch_card(ctx: Ctx, eid: UUID, app: Optional[str] = None) -> dict:
    kind = ctx.conn.execute("select kind::text k from entities where id=%s", (eid,)).fetchone()["k"]
    return {"fetch": {"app": app or APP_FOR_KIND.get(kind, "intelsearch"),
                      "path": f"/api/card/{ent_int(ctx.conn, eid)}", "params": {}}}


def fetch_path(app: str, path: str, **params) -> dict:
    return {"fetch": {"app": app, "path": path, "params": {k: str(v) for k, v in params.items()}}}


def row(text: str, right: str = "", tone: str = "", **action) -> dict:
    r = {"text": text, "right": right, "tone": tone}
    r.update(action.get("act", {}))
    return r


def rows(label: str, items: list, note: str = "") -> Optional[dict]:
    return {"type": "rows", "label": label, "note": note, "rows": items} if items else None


def text(label: str, body: Optional[str], mono: bool = False) -> Optional[dict]:
    return {"type": "mono" if mono else "text", "label": label, "text": body} if body else None


def meter(label: str, value, low: str, high: str, note: str = "") -> Optional[dict]:
    if value is None:
        return None
    return {"type": "meter", "label": label, "value": round(float(value), 3), "low": low, "high": high, "note": note}


def card(ctx: Ctx, eid: UUID, kind: str, kind_label: str, title: str, *, subtitle: str = "",
         status: str = "", fields=(), blocks=(), pin_label: Optional[str] = None) -> dict:
    ctx.seen(eid)
    return {"card": kind, "kind_label": kind_label, "title": title, "subtitle": subtitle, "status": status,
            "fields": [list(f) for f in fields if f and f[1] not in (None, "")],
            "blocks": [b for b in blocks if b],
            "pin": {"entity_kind": kind, "entity_id": ent_int(ctx.conn, eid), "label": pin_label or title}}


def status_of(verdict: str) -> str:
    return {"malicious": "malicious", "compromised": "malicious", "suspicious": "suspicious",
            "benign": "clean", "parked": "clean", "sinkholed": "unknown"}.get(verdict, "unknown")


def edges(ctx: Ctx, eid: UUID, rel: str, direction: str = "out") -> list[dict]:
    """Visible edges of one type from/to an entity, with the other end's basics."""
    me, other = ("src_id", "dst_id") if direction == "out" else ("dst_id", "src_id")
    return ctx.conn.execute(f"""
        select o.id, o.kind::text kind, o.value::text v, coalesce(o.label, o.value::text) label, o.verdict::text verdict,
               lower(r.valid) at, s.name src
        from entity_relationships r join entities o on o.id = r.{other}
        left join sources s on s.id = r.source_id
        where r.{me}=%s and r.rel=%s and (r.case_id is null or r.case_id=%s)
          and (o.case_id is null or o.case_id=%s)
        order by lower(r.valid) nulls last""", (eid, rel, ctx.cid, ctx.cid)).fetchall()


def pivot_rows(*items: tuple[str, str, str]) -> Optional[dict]:
    """(text, app, query) -> a PIVOTS block of open-actions."""
    return rows("PIVOTS", [row(t, "OPEN >", "", act=open_(a, q)) for t, a, q in items if q])


def indicator_row(ind: str) -> dict:
    """Send an indicator a victim listed to the tool that understands it."""
    i = ind.strip()
    if PHONE_RE.fullmatch(i) or re.fullmatch(r"\+?\d{10,12}", i):
        return row(i, "PHONE LOOKUP >", act=open_("phone", i))
    if re.fullmatch(r"T[1-9A-HJ-NP-Za-km-z]{33}|bc1q\w+", i):
        return row(i, "MONEY TRAIL >", act=open_("moneytrail", i))
    if "@" in i and "." in i.split("@")[-1]:
        return row(i, "BREACH LOOKUP >", act=open_("breach", i))
    if re.search(r"\.(example|test)\b", i):
        return row(i, "INTELSEARCH >", act=open_("intelsearch", host_of(i)))
    return row(i, "SOCIAL SEARCH >", act=open_("social", i.lstrip("@$")))


# --------------------------------------------------------------------------- builders
def persona_card(ctx: Ctx, eid: UUID) -> dict:
    c = ctx.conn
    p = c.execute("select * from personas where entity_id=%s", (eid,)).fetchone()
    created = p["account_created"] or p["joined_on"]
    photos = [row(f"Profile photo  ·  {im['label']}", "REVERSE IMAGE SEARCH >", act=open_("reverseimage", im["v"]))
              for im in edges(ctx, eid, "uses_image")]
    posts = []
    for po in c.execute("""select e.id, sp.body, sp.posted_at, sp.is_direct_message from entity_relationships r
                           join entities e on e.id=r.dst_id join social_posts sp on sp.entity_id=e.id
                           where r.src_id=%s and r.rel='posted' and (r.case_id is null or r.case_id=%s)
                           order by sp.posted_at desc limit 8""", (eid, ctx.cid)).fetchall():
        tag = "DM" if po["is_direct_message"] else "post"
        snippet = po["body"] if len(po["body"]) < 70 else po["body"][:67] + "..."
        posts.append(row(f"{day(po['posted_at'])}  {tag}: {snippet}", "OPEN >", act=fetch_card(ctx, po["id"], "social")))
    links = [row(f"Link in bio: personal page of {pe['name']}", "DIRECTORY >", act=open_("directory", pe["name"]))
             for pe in c.execute("""select p.full_name name from entity_relationships r join persons p on p.entity_id=r.dst_id
                                    where r.src_id=%s and r.rel='identified_as' and (r.case_id is null or r.case_id=%s)""",
                                 (eid, ctx.cid)).fetchall()]
    h = p["handle"]
    return card(ctx, eid, "persona", "SOCIAL PROFILE", f"@{h}", subtitle=p["platform"],
                fields=[("Display name", p["display_name"]),
                        ("Platform", p["platform"]),
                        ("Verified", "yes (platform-verified)" if p["verified"] else "no", "ok" if p["verified"] else ""),
                        ("Account created", before_incident(ctx, created)),
                        ("Followers", f"{p['follower_count']:,}" if p["follower_count"] else None),
                        ("Posts", f"{p['post_count']:,}" if p["post_count"] else None),
                        ("Says they are", p["claimed_occupation"]),
                        ("Says they're in", p["claimed_location"]),
                        ("Language", p["language"]),
                        ("Active hours suggest", f"UTC{p['utc_offset_guess']:+d}" if p["utc_offset_guess"] is not None else None),
                        ("PGP key", p["pgp_fingerprint"]),
                        ("Previous handles", ", ".join(p["previous_handles"]) if p["previous_handles"] else None),
                        ("Last active", day(p["last_active"]) if p["last_active"] else None)],
                blocks=[text("BIO", p["bio"]),
                        rows("PROFILE PHOTOS", photos, "Scammers rarely use their own face. Check where else a photo appears."),
                        rows("POSTS & MESSAGES", posts),
                        rows("LINKS", links),
                        pivot_rows((f"Search the username '{h}' on every platform", "social", h),
                                   (f"Look up '{h}' in breach data", "breach", h),
                                   (f"Search fraud reports for '{h}'", "complaints", h),
                                   (f"Search the web for '{h}'", "websearch", h))],
                pin_label=f"@{h} ({short_platform(p['platform'])})")


def post_card(ctx: Ctx, eid: UUID) -> dict:
    sp = ctx.conn.execute("select * from social_posts where entity_id=%s", (eid,)).fetchone()
    author = edges(ctx, eid, "posted", "in")
    links = [row(l["v"], "URL SCANNER >", act=open_("urlscan", l["v"])) for l in edges(ctx, eid, "contains_link")]
    for m in URL_RE.findall(sp["body"]):
        if not any(m in l["text"] for l in links):
            links.append(row(m, "INTELSEARCH >", act=open_("intelsearch", host_of(m))))
    replied = [row(f"In reply to: {r['label'][:70]}", "OPEN >", act=fetch_card(ctx, r["id"], "social"))
               for r in edges(ctx, eid, "replied_to")]
    replied += [row(f"Reply: {r['label'][:70]}", "OPEN >", act=fetch_card(ctx, r["id"], "social"))
                for r in edges(ctx, eid, "replied_to", "in")]
    dm = sp["is_direct_message"]
    return card(ctx, eid, "social_post", "DIRECT MESSAGE" if dm else "PUBLIC POST",
                f"@{sp['author_handle']}", subtitle=f"{sp['platform']}  ·  {dt(sp['posted_at'])}",
                fields=[("From", f"@{sp['author_handle']}"),
                        ("Platform", sp["platform"]),
                        ("Sent" if dm else "Posted", dt(sp["posted_at"])),
                        ("Visibility", "private message to the victim" if dm else "public"),
                        ("Replying to", f"@{sp['reply_to_handle']}" if sp["reply_to_handle"] else None),
                        ("Likes", str(sp["likes"]) if (sp["likes"] and not dm) else None),
                        ("Language", sp["language"])],
                blocks=[text("MESSAGE" if dm else "POST", sp["body"]),
                        rows("AUTHOR", [row(f"@{sp['author_handle']} ({a['label']})", "VIEW PROFILE >",
                                            act=fetch_card(ctx, a["id"], "social")) for a in author]),
                        rows("LINKS IN MESSAGE", links),
                        rows("THREAD", replied)],
                pin_label=f"{'DM' if dm else 'Post'} from @{sp['author_handle']}: {sp['body'][:40]}")


def image_card(ctx: Ctx, eid: UUID, sightings: bool = False) -> dict:
    c = ctx.conn
    im = c.execute("select * from images where entity_id=%s", (eid,)).fetchone()
    value = c.execute("select value::text v from entities where id=%s", (eid,)).fetchone()["v"]
    exif = [x for x in (im["exif_camera"], im["exif_taken_at"] and dt(im["exif_taken_at"]), im["exif_location"]) if x]
    blocks = [meter("AI-GENERATED FACE DETECTOR", im["synthetic_score"], "camera photo", "synthetic face",
                    "Above ~0.6 the face was probably generated, so there is no real person to find.")]
    if sightings:
        hits = c.execute("select * from reverse_image(%s, %s)", (ctx.cid, value)).fetchall()
        seen_rows, near = [], []
        for h in hits:
            who = c.execute("""select coalesce(p.handle::text, e.value::text) h, p.platform, e.kind::text k
                               from entities e left join personas p on p.entity_id=e.id where e.id=%s""",
                            (h["seen_on_id"],)).fetchone()
            where = f"@{who['h']} on {short_platform(who['platform'])}" if who["platform"] else who["h"]
            dup = "" if h["image_id"] == eid else "  (near-duplicate)"
            seen_rows.append(row(f"{day(h['first_seen']) or 'date unknown'}   {where}{dup}", "OPEN >",
                                 act=fetch_card(ctx, h["seen_on_id"], "social")))
            ctx.seen(h["seen_on_id"], h["image_id"])
        for n in c.execute("""select e.id, i.description from images i join entities e on e.id=i.entity_id
                              where (e.case_id is null or e.case_id=%s) and left(i.phash,12)=left(%s,12) and e.id<>%s
                                and not exists (select 1 from entity_relationships r where r.src_id=e.id or r.dst_id=e.id)""",
                           (ctx.cid, im["phash"], eid)).fetchall():
            near.append(row(f"Visually similar: {n['description']}", "", "warn"))
            ctx.seen(n["id"])
        blocks += [rows("MATCHES, OLDEST FIRST", seen_rows,
                        "The earliest appearance is usually the real owner. A brand-new account using an old photo is a red flag."),
                   rows("VISUALLY SIMILAR IMAGES", near)]
        if not seen_rows and not near:
            blocks.append(text("MATCHES", "No other copies of this image are indexed."))
    else:
        blocks.append(pivot_rows(("Run a reverse image search on this picture", "reverseimage", value)))
    return card(ctx, eid, "image", "IMAGE", im["description"], subtitle=f"{im['width']} x {im['height']} px",
                fields=[("Image ID", value),
                        ("Perceptual hash", im["phash"]),
                        ("EXIF", "  ·  ".join(exif) if exif else "none (stripped by the platform)")],
                blocks=blocks)


LINE_TYPE = {"voip": ("VoIP (internet number, cheap and disposable)", "warn"),
             "toll_free": ("Toll-free (anyone can rent one in minutes)", "warn"),
             "mobile": ("Mobile", ""), "landline": ("Landline", ""), "short_code": ("SMS short code", "")}


def phone_card(ctx: Ctx, eid: UUID) -> dict:
    p = ctx.conn.execute("select * from phone_numbers where entity_id=%s", (eid,)).fetchone()
    lt, tone = LINE_TYPE.get(p["line_type"], (p["line_type"], ""))
    n = p["spam_reports"]
    pretty = phone_pretty(p["e164"])
    return card(ctx, eid, "phone", "PHONE NUMBER", pretty, subtitle=f"{p['carrier'] or 'unknown carrier'}",
                status="suspicious" if n >= 5 else "",
                fields=[("E.164", p["e164"]), ("Country", p["country"]), ("Line type", lt, tone),
                        ("Carrier", p["carrier"]), ("Caller-ID name (CNAM)", p["cnam"] or "none on file"),
                        ("Community spam reports", str(n), "danger" if n >= 10 else "warn" if n else ""),
                        ("First reported", day(p["first_reported"]) if p["first_reported"] else None)],
                blocks=[pivot_rows(("Search fraud reports that list this number", "complaints", p["e164"]),
                                   ("Search reported texts from this number", "sms", p["e164"]),
                                   ("Find voicemails that mention this number", "audiolab", pretty),
                                   ("Search social media and forums for this number", "social", pretty),
                                   ("Search the web for this number", "websearch", p["e164"]))],
                pin_label=pretty)


def sms_card(ctx: Ctx, eid: UUID) -> dict:
    s = ctx.conn.execute("select * from sms_messages where entity_id=%s", (eid,)).fetchone()
    links = [row(m, "URL SCANNER >", act=open_("urlscan", m)) for m in dict.fromkeys(URL_RE.findall(s["body"]))]
    return card(ctx, eid, "sms_message", "TEXT MESSAGE", f"From {phone_pretty(s['from_number'])}",
                subtitle=f"{s['channel']}  ·  {dt(s['sent_at'])}",
                fields=[("From", phone_pretty(s["from_number"])), ("To", phone_pretty(s["to_number"])),
                        ("Received", dt(s["sent_at"])), ("Channel", s["channel"]), ("Language", s["language"]),
                        ("Writing style", s["style_notes"])],
                blocks=[text("MESSAGE", s["body"]),
                        rows("LINKS IN MESSAGE", links, "Never open these on a work device. Scan them instead."),
                        pivot_rows(("Look up the sending number", "phone", s["from_number"]),
                                   ("Other reported texts from this number", "sms", s["from_number"]))],
                pin_label=f"SMS from {phone_pretty(s['from_number'])}")


def document_card(ctx: Ctx, eid: UUID) -> dict:
    d = ctx.conn.execute("select * from documents where entity_id=%s", (eid,)).fetchone()
    meta = "\n".join(f"{k:<22}: {v}" for k, v in [
        ("File Name", d["file_name"]), ("File Type", d["file_type"]), ("Page Count", d["page_count"]),
        ("Author", d["meta_author"] or ""), ("Last Modified By", d["meta_last_modified_by"] or ""),
        ("Company", d["meta_company"] or ""), ("Creator Tool", d["meta_creator_tool"] or ""),
        ("Create Date", dt(d["meta_created"])), ("Modify Date", dt(d["meta_modified"]))])
    piv = []
    if d["meta_author"]:
        piv.append((f"Look up the author '{d['meta_author']}' in the Directory", "directory", d["meta_author"]))
        piv.append((f"Find other documents by '{d['meta_author']}'", "doclab", d["meta_author"]))
    piv.append(("Search the web for this file's hash", "websearch", d["sha256"]))
    if d["meta_last_modified_by"] and d["meta_last_modified_by"] != d["meta_author"]:
        piv.append((f"Look up '{d['meta_last_modified_by']}' in the Directory", "directory", d["meta_last_modified_by"]))
    return card(ctx, eid, "document", "DOCUMENT", d["file_name"],
                subtitle=f"{d['file_type']}  ·  {(d['size_bytes'] or 0) // 1024} KB",
                fields=[("SHA-256", d["sha256"]), ("Published at", d["published_url"])],
                blocks=[text("EMBEDDED METADATA (exiftool)", meta, mono=True),
                        text("TEXT EXCERPT", d["text_excerpt"]),
                        pivot_rows(*piv)],
                pin_label=d["file_name"])


STIR = {"A": ("A - full attestation: carrier verified the caller owns this number", "ok"),
        "B": ("B - partial: carrier knows the customer, not that they own this number", "warn"),
        "C": ("C - gateway: call entered from outside, caller ID unverified (easily spoofed)", "danger")}


def audio_card(ctx: Ctx, eid: UUID) -> dict:
    a = ctx.conn.execute("select * from audio_recordings where entity_id=%s", (eid,)).fetchone()
    verdict = ctx.conn.execute("select verdict::text v from entities where id=%s", (eid,)).fetchone()["v"]
    kind = {"voicemail": "Voicemail", "public_talk": "Public recording", "call_recording": "Call recording"}[a["recording_type"]]
    stir, stone = STIR.get(a["stir_shaken"] or "", (None, ""))
    numbers = [row(f"Number spoken in the message: {n}", "PHONE LOOKUP >", act=open_("phone", n))
               for n in dict.fromkeys(PHONE_RE.findall(a["transcript"] or ""))]
    return card(ctx, eid, "audio_recording", "AUDIO RECORDING", f"{kind}: {a['speaker_claimed'] or 'unknown speaker'}",
                subtitle=f"{dt(a['recorded_at'])}  ·  {a['duration_s'] // 60}:{a['duration_s'] % 60:02d}",
                fields=[("Type", kind), ("Recorded", dt(a["recorded_at"])),
                        ("Claimed speaker", a["speaker_claimed"]), ("Caller ID displayed", a["caller_id"]),
                        ("STIR/SHAKEN", stir, stone), ("Voiceprint", a["voiceprint_hash"]),
                        ("Source", a["source_url"]),
                        ("Description", a["analysis_note"] if verdict == "benign" else None)],
                blocks=[meter("SYNTHETIC-VOICE DETECTOR", a["synthetic_score"], "natural speech", "machine-generated",
                              "Detectors give a probability, not proof. Compare the voiceprint against real recordings."),
                        text("TRANSCRIPT", a["transcript"]),
                        rows("NUMBERS", numbers),
                        pivot_rows(("Find other recordings with this voiceprint", "audiolab", a["voiceprint_hash"]),
                                   (f"Find public recordings of '{a['speaker_claimed']}'", "audiolab", a["speaker_claimed"]))],
                pin_label=f"{kind}: {a['speaker_claimed']} ({day(a['recorded_at'])})")


METHOD = {"bank_wire": "Bank wire", "gift_card": "Gift cards (codes read out or photographed)",
          "p2p_app": "Peer-to-peer payment app", "money_transfer": "Money-transfer service",
          "crypto_exchange": "Crypto exchange account"}


def payment_card(ctx: Ctx, eid: UUID) -> dict:
    p = ctx.conn.execute("select * from payment_accounts where entity_id=%s", (eid,)).fetchone()
    return card(ctx, eid, "payment_account", "PAYMENT ACCOUNT", f"{p['provider']}  {p['identifier']}",
                subtitle=METHOD.get(p["method"], p["method"]),
                fields=[("Provider", p["provider"]), ("Method", METHOD.get(p["method"], p["method"]),
                                                      "warn" if p["method"] == "gift_card" else ""),
                        ("Account identifier", p["identifier"]), ("Name on account", p["holder_name"]),
                        ("Opened", before_incident(ctx, p["opened_on"]) if (p["opened_on"] and p["method"] != "gift_card") else None),
                        ("Fraud flags", "Provider flagged this account for money-mule activity" if p["is_mule"] else "none on file",
                         "danger" if p["is_mule"] else "")],
                blocks=[text("NOTE", "Money mules are often recruited victims themselves. The name on the account is "
                                     "rarely the person running the scam.") if p["is_mule"] else None,
                        pivot_rows(("Follow the money out of this account", "moneytrail", p["identifier"]),
                                   ("Search fraud reports for this account", "complaints", p["identifier"]),
                                   (f"Search the web for '{p['identifier']}'", "websearch", p["identifier"]),
                                   (f"Search social media and forums for '{p['identifier']}'", "social", p["identifier"]),
                                   (f"Look up the account holder '{p['holder_name']}'", "directory", p["holder_name"] or ""))],
                pin_label=f"{p['provider']} {p['identifier']}")


def wallet_card(ctx: Ctx, eid: UUID) -> dict:
    c = ctx.conn
    w = c.execute("select * from crypto_wallets where entity_id=%s", (eid,)).fetchone()
    tags = c.execute("select tags from entities where id=%s", (eid,)).fetchone()["tags"]
    label = "Clustered with an exchange deposit address (cash-out point)" if "cash-out" in tags else None
    unit = {"tron": "USDT (TRC-20)", "bitcoin": "BTC (valued in USD)"}.get(w["chain"], w["chain"])
    return card(ctx, eid, "crypto_wallet", "CRYPTO WALLET", w["address"], subtitle=f"{w['chain'].title()} blockchain",
                fields=[("Chain", w["chain"].title()), ("Asset", unit),
                        ("Total received", money(w["total_received"])), ("Transactions", f"{w['tx_count']:,}"),
                        ("Cluster label", label, "warn")],
                blocks=[pivot_rows(("Trace transfers out of this wallet", "moneytrail", w["address"]),
                                   ("Search fraud reports for this address", "complaints", w["address"]),
                                   ("Search the web for this address", "websearch", w["address"]),
                                   ("Search social media and forums for this address", "social", w["address"]))],
                pin_label=f"{w['chain']} wallet {w['address'][:10]}...")


def complaint_card(ctx: Ctx, eid: UUID) -> dict:
    cm = ctx.conn.execute("select c.*, e.value::text v from complaints c join entities e on e.id=c.entity_id "
                          "where c.entity_id=%s", (eid,)).fetchone()
    return card(ctx, eid, "complaint", "FRAUD REPORT", cm["v"], subtitle=f"{cm['portal']}  ·  filed {day(cm['filed_at'])}",
                fields=[("Filed", dt(cm["filed_at"])), ("Reporter region", cm["reporter_region"]),
                        ("Reported loss", money(cm["loss_amount"]))],
                blocks=[text("WHAT HAPPENED (in the reporter's words)", cm["narrative"]),
                        rows("INDICATORS THE REPORTER LISTED", [indicator_row(i) for i in cm["indicators"]],
                             "Reports are unverified. Similar stories can come from different crews.")],
                pin_label=f"Fraud report {cm['v']}")


def email_card(ctx: Ctx, eid: UUID) -> dict:
    c = ctx.conn
    m = c.execute("select * from email_messages where entity_id=%s", (eid,)).fetchone()
    tone = {"pass": "ok", "fail": "danger", "softfail": "warn", "none": "warn"}
    hops = [row(f"from {h['from']}  by {h['by']}  [{h['ip']}]", "INTELSEARCH >", act=open_("intelsearch", h["ip"]))
            for h in m["received_chain"]]
    links = [row(l["v"], "URL SCANNER >", act=open_("urlscan", l["v"])) for l in edges(ctx, eid, "contains_link")]
    for u in dict.fromkeys(URL_RE.findall(m["body_text"])):
        if not any(u in l["text"] for l in links):
            links.append(row(u, "URL SCANNER >", act=open_("urlscan", u)))
    att = [row(a["label"], "DOCUMENT LAB >", act=fetch_card(ctx, a["id"], "doclab")) for a in edges(ctx, eid, "attached")]
    from_addr = re.search(r"<([^>]+)>", m["header_from"])
    from_addr = from_addr.group(1) if from_addr else m["header_from"]
    piv = [(f"Sender domain {from_addr.split('@')[-1]} in IntelSearch", "intelsearch", from_addr.split("@")[-1]),
           (f"Envelope domain {m['envelope_from'].split('@')[-1]} WHOIS history", "whois", m["envelope_from"].split("@")[-1]),
           (f"Sender address {from_addr} in breach data", "breach", from_addr)]
    if m["reply_to"]:
        piv.append((f"Reply-To address {m['reply_to']} in breach data", "breach", m["reply_to"]))
    rt_tone = "danger" if (m["reply_to"] and m["reply_to"].lower() != from_addr.lower()) else ""
    return card(ctx, eid, "email_message", "EMAIL", m["subject"], subtitle=f"From: {m['header_from']}",
                fields=[("From (display)", m["header_from"]), ("Return-Path", m["envelope_from"]),
                        ("Reply-To", m["reply_to"], rt_tone), ("To", m["to_addr"]), ("Date", dt(m["sent_at"])),
                        ("SPF", m["spf_result"], tone.get(m["spf_result"], "")),
                        ("DKIM", m["dkim_result"], tone.get(m["dkim_result"], "")),
                        ("DMARC", m["dmarc_result"], tone.get(m["dmarc_result"], "")),
                        ("X-Mailer", m["x_mailer"]), ("Message-ID", m["message_id"])],
                blocks=[text("BODY", m["body_text"]),
                        rows("LINKS IN MESSAGE", links, "The visible text of a link can differ from where it goes."),
                        rows("ATTACHMENTS", att),
                        rows("RECEIVED CHAIN (newest hop first)", hops,
                             "Read from the bottom up. The last hop you can't verify is where the mail really started."),
                        text("RAW HEADERS", m["raw_headers"], mono=True),
                        pivot_rows(*piv)],
                pin_label=f"Email: {m['subject'][:48]}")


def email_address_card(ctx: Ctx, eid: UUID) -> dict:
    a = ctx.conn.execute("select * from email_addresses where entity_id=%s", (eid,)).fetchone()
    addr = a["address"]
    return card(ctx, eid, "email_address", "EMAIL ADDRESS", addr, subtitle=a["provider"] or "",
                fields=[("Provider", a["provider"]),
                        ("Disposable inbox", "yes (throwaway service)" if a["is_disposable"] else "no",
                         "warn" if a["is_disposable"] else "")],
                blocks=[pivot_rows(("Look the address up in breach data", "breach", addr),
                                   ("Find domains registered with this address", "whois", addr),
                                   ("Search fraud reports for this address", "complaints", addr),
                                   ("Search the web for this address", "websearch", addr))],
                pin_label=addr)


def url_card(ctx: Ctx, eid: UUID) -> dict:
    u = ctx.conn.execute("select * from urls where entity_id=%s", (eid,)).fetchone()
    scans = [row(f"Scan {s['label']}", "OPEN >", act=fetch_card(ctx, s["id"], "urlscan")) for s in edges(ctx, eid, "scanned_as")]
    redir = [row(f"Redirects to {r['v']}", "OPEN >", act=fetch_card(ctx, r["id"], "urlscan")) for r in edges(ctx, eid, "redirects_to")]
    files = [row(f"Downloads file: {f['label']}", "FILE ANALYSIS >", act=fetch_card(ctx, f["id"], "malwaredb"))
             for f in edges(ctx, eid, "serves_payload")]
    verdict = ctx.conn.execute("select verdict::text v from entities where id=%s", (eid,)).fetchone()["v"]
    return card(ctx, eid, "url", "URL", u["full_url"], subtitle=f"host {u['host']}", status=status_of(verdict),
                fields=[("Host", u["host"]), ("Path", u["path"])],
                blocks=[rows("SCANS", scans), rows("REDIRECTS", redir), rows("PAYLOAD", files),
                        pivot_rows((f"Look up {u['host']} in IntelSearch", "intelsearch", u["host"]),
                                   (f"DNS history of {u['host']}", "dns", u["host"]))],
                pin_label=u["full_url"])


def scan_card(ctx: Ctx, eid: UUID) -> dict:
    s = ctx.conn.execute("select * from url_scans where entity_id=%s", (eid,)).fetchone()
    verdict = ctx.conn.execute("select verdict::text v from entities where id=%s", (eid,)).fetchone()["v"]
    ip = str(s["ip_seen"]) if s["ip_seen"] else ""
    piv = [row(f"Tracking ID {t}  ·  find every page using it", "PIVOT >",
               act=fetch_path("urlscan", "/api/pivot", field="tracking_id", value=t)) for t in s["tracking_ids"]]
    if s["favicon_mmh3"] is not None:
        piv.append(row(f"Favicon hash {s['favicon_mmh3']}  ·  find pages with the same icon", "PIVOT >",
                       act=fetch_path("urlscan", "/api/pivot", field="favicon", value=s["favicon_mmh3"])))
    if s["jarm"]:
        piv.append(row(f"JARM {s['jarm'][:24]}...  ·  find servers with the same TLS fingerprint", "PIVOT >",
                       act=fetch_path("urlscan", "/api/pivot", field="jarm", value=s["jarm"])))
    if ip:
        piv.append(row(f"Server IP {ip}", "INTELSEARCH >", act=open_("intelsearch", ip)))
    fh = host_of(s["final_url"] or s["scanned_url"])
    piv.append(row(f"Host {fh}", "INTELSEARCH >", act=open_("intelsearch", fh)))
    page_text = " ".join([s["page_title"] or ""] + list(s["kit_indicators"]))
    numbers = [row(f"Phone number shown on the page: {n}", "PHONE LOOKUP >", act=open_("phone", n))
               for n in dict.fromkeys(PHONE_RE.findall(page_text))]
    redirected = s["final_url"] and s["final_url"] != s["scanned_url"]
    return card(ctx, eid, "url_scan", "URL SCAN", s["scanned_url"], subtitle=f"scanned {dt(s['scanned_at'])}",
                status=status_of(verdict),
                fields=[("Final URL", s["final_url"], "warn" if redirected else ""), ("HTTP status", s["http_status"]),
                        ("Page title", s["page_title"]), ("Server", s["server_header"]), ("IP at scan time", ip),
                        ("Screenshot similarity", s["visual_match"], "warn"),
                        ("Screenshot hash", s["phash"]), ("HTML SHA-256", s["html_sha256"])],
                blocks=[text("PAGE ARTIFACTS", "\n".join(f"- {k}" for k in s["kit_indicators"])),
                        rows("ON THE PAGE", numbers),
                        rows("PIVOTS", piv, "Strong selectors (tracking IDs, JARM) link one operator. A favicon only "
                                            "proves the same brand was copied.")],
                pin_label=f"Scan of {s['scanned_url'][:50]}")


def whois_card(ctx: Ctx, eid: UUID) -> dict:
    w = ctx.conn.execute("select * from whois_records where entity_id=%s", (eid,)).fetchone()
    piv = []
    if w["registrant_email"]:
        piv += [row(f"Registrant email {w['registrant_email']}  ·  breach data", "BREACH LOOKUP >",
                    act=open_("breach", w["registrant_email"])),
                row(f"Every domain registered with {w['registrant_email']}", "PIVOT >",
                    act=fetch_path("whois", "/api/pivot", field="registrant_email", value=w["registrant_email"]))]
    piv += [row(f"Name server {ns}  ·  every domain using it", "PIVOT >",
                act=fetch_path("whois", "/api/pivot", field="nameserver", value=ns.lower())) for ns in w["name_servers"]]
    return card(ctx, eid, "whois_record", "WHOIS SNAPSHOT", w["domain_fqdn"], subtitle=f"captured {dt(w['captured_at'])}",
                fields=[("Registrar", w["registrar_name"]), ("Created", day(w["created_on"])),
                        ("Updated", day(w["updated_on"])), ("Expires", day(w["expires_on"])),
                        ("Registrant", w["registrant_name"] or "REDACTED FOR PRIVACY"),
                        ("Organization", w["registrant_org"]),
                        ("Registrant email", w["registrant_email"] or "REDACTED", "warn" if w["registrant_email"] else ""),
                        ("Country", w["registrant_country"]), ("Privacy service", w["privacy_service"])],
                blocks=[rows("PIVOTS", piv), text("RAW RECORD", w["raw_text"], mono=True)],
                pin_label=f"WHOIS {w['domain_fqdn']} @ {day(w['captured_at'])}")


def cert_card(ctx: Ctx, eid: UUID) -> dict:
    c = ctx.conn.execute("select * from certificates where entity_id=%s", (eid,)).fetchone()
    sans = [row(s, "INTELSEARCH >", act=open_("intelsearch", s.removeprefix("www."))) for s in c["san"][:40]]
    return card(ctx, eid, "certificate", "TLS CERTIFICATE", c["subject_cn"], subtitle=f"issued by {c['issuer_cn']}",
                fields=[("Issuer", f"{c['issuer_cn']} ({c['issuer_org'] or ''})"), ("Serial", c["serial"]),
                        ("SHA-256", c["sha256"]), ("Valid", f"{day(c['not_before'])} to {day(c['not_after'])}"),
                        ("Logged", f"{c['ct_log'] or ''}  {dt(c['logged_at'])}"),
                        ("Self-signed", "yes" if c["self_signed"] else "no")],
                blocks=[rows(f"NAMES ON THIS CERTIFICATE ({len(c['san'])})", sans,
                             "One certificate covering several look-alike names usually means one operator. "
                             "A CDN's shared certificate covers thousands of unrelated sites.")],
                pin_label=f"Certificate CN={c['subject_cn']}")


def sample_card(ctx: Ctx, eid: UUID) -> dict:
    m = ctx.conn.execute("select * from malware_samples where entity_id=%s", (eid,)).fetchone()
    fam = edges(ctx, eid, "sample_of")
    c2 = edges(ctx, eid, "c2_contact")
    det = m["av_detections"]
    piv = [row(f"Family: {f['label']}", "MALWAREDB >", act=open_("malwaredb", f["label"])) for f in fam]
    piv += [row(f"Contacted {h['v']} after execution (command-and-control)", "INTELSEARCH >",
                act=open_("intelsearch", h["v"])) for h in c2]
    if m["imphash"]:
        piv.append(row(f"Import hash {m['imphash']}  ·  samples built the same way", "PIVOT >",
                       act=fetch_path("malwaredb", "/api/pivot", field="imphash", value=m["imphash"])))
    return card(ctx, eid, "malware_sample", "FILE ANALYSIS", m["file_name"] or m["sha256"][:16],
                subtitle=f"{m['file_type'] or ''}  ·  first submitted {day(m['first_submitted'])}",
                status="malicious" if det >= 10 else "suspicious" if det else "unknown",
                fields=[("SHA-256", m["sha256"]), ("SHA-1", m["sha1"]), ("MD5", m["md5"]), ("Import hash", m["imphash"]),
                        ("ssdeep", m["ssdeep"]), ("Size", f"{(m['size_bytes'] or 0):,} bytes"),
                        ("Antivirus detections", f"{det} / {m['av_total']} engines",
                         "danger" if det >= 10 else "warn" if det else ""),
                        ("Sandbox verdict", m["sandbox_verdict"])],
                blocks=[text("YARA RULE MATCHES", "\n".join(m["yara_hits"]), mono=True),
                        text("STRINGS OF INTEREST", "\n".join(m["strings_of_interest"]), mono=True),
                        text("EXTRACTED CONFIGURATION", __import__("json").dumps(m["c2_config"], indent=2), mono=True)
                        if m["c2_config"] else None,
                        rows("RELATIONS", piv, "Strings and YARA names that point at a famous group are easy to plant. "
                                               "Weigh them against infrastructure.")],
                pin_label=f"Sample {m['file_name'] or m['sha256'][:12]}")


def campaign_card(ctx: Ctx, eid: UUID) -> dict:
    cp = ctx.conn.execute("select * from campaigns where entity_id=%s", (eid,)).fetchone()
    return card(ctx, eid, "campaign", "CAMPAIGN", cp["name"],
                fields=[("Active since", day(cp["started_on"])), ("Objective", cp["objective"]),
                        ("Targeting", cp["targeting"])],
                blocks=[pivot_rows((f"Search reporting on {cp['name']}", "websearch", cp["name"]))])


BUILDERS = {"persona": persona_card, "social_post": post_card, "image": image_card, "phone": phone_card,
            "sms_message": sms_card, "document": document_card, "audio_recording": audio_card,
            "payment_account": payment_card, "crypto_wallet": wallet_card, "complaint": complaint_card,
            "email_message": email_card, "email_address": email_address_card, "url": url_card,
            "url_scan": scan_card, "whois_record": whois_card, "certificate": cert_card, "campaign": campaign_card,
            "malware_sample": sample_card}

APP_FOR_KIND = {"persona": "social", "social_post": "social", "image": "reverseimage", "phone": "phone",
                "sms_message": "sms", "document": "doclab", "audio_recording": "audiolab",
                "payment_account": "payments", "crypto_wallet": "moneytrail", "complaint": "complaints",
                "email_message": "breach", "email_address": "breach", "url": "urlscan", "url_scan": "urlscan",
                "whois_record": "whois", "certificate": "certs", "campaign": "websearch", "malware_sample": "malwaredb",
                "domain": "intelsearch", "ip": "intelsearch", "malware_family": "malwaredb",
                "threat_actor": "directory", "person": "directory"}


def card_for(ctx: Ctx, eid: UUID) -> Optional[dict]:
    kind = ctx.conn.execute("select kind::text k from entities where id=%s", (eid,)).fetchone()["k"]
    b = BUILDERS.get(kind)
    return b(ctx, eid) if b else None
