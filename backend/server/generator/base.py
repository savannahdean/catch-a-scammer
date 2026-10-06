"""Shared machinery every scam scenario is built from.

A scenario subclass only writes the part that makes its scam unique (the
lure, the social accounts, the voicemail, the money trail ...) and reuses:

  site()          realistic phishing web infrastructure (DNS history, WHOIS,
                  certs, scans, CDN fronting, sinkhole, co-hosted decoys)
  attribution()   campaign + actor + vendor report + decoy blogs + false flag
  unmask()        registrant/account email -> breach -> forum -> social -> person
  complaints()    other victims' reports: corroboration AND noise
  email_msg(), sms(), audio(), persona(), post(), image(), document(),
  phone(), payment(), wallet(), lure()     artifact builders
"""
from __future__ import annotations

import ipaddress
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg

from . import fakes as F
from .writer import Writer

UTC = timezone.utc
VICTIM_TZ = timezone(timedelta(hours=-5), "CDT")
FREE_CA = ("OpenTrust DV CA R3", "OpenTrust")
CDN_CA = ("EdgeShield Edge CA 01", "EdgeShield Inc")


@dataclass
class Profile:
    level: str
    sibling_domains: int
    shared_hosting_noise: int
    cdn_front_prob: float
    whois_privacy_prob: float
    stale_dns_traps: int
    compromised_redirector: bool
    commodity_malware: bool
    false_flag: bool
    decoy_actor_articles: int
    require_person: bool
    max_hints: int
    base_score: int


@dataclass
class Site:
    primary_id: UUID
    primary_fqdn: str
    origin_id: UUID
    origin_ip: str
    second_id: UUID
    second_ip: str
    cert_id: UUID
    siblings: list = field(default_factory=list)      # [(id, fqdn, url_id, scan_id)]
    landing_id: UUID | None = None
    landing_url: str = ""
    landing_scan: UUID | None = None
    tid: UUID | None = None
    tid_code: str = ""
    jarm: str = ""
    cdn: bool = False


class Scenario:
    # ---- catalog metadata (override in subclasses) ----------------------
    key = "base"
    title = ""
    category = ""
    real_world_basis = ""
    player_skill = ""
    report_fields: list[tuple[str, str, str]] = []   # (slot key, label, entity kind)
    victim_roles = ["Staff member"]
    actor_motivations = ("financial",)

    def __init__(self, conn: psycopg.Connection, profile: Profile, seed: int):
        self.conn, self.p, self.seed = conn, profile, seed
        self.rng = random.Random(seed)
        self.hop = 0
        self.used_hosts: set[str] = set()
        self.used_values: set[str] = set()
        self.slots: dict[str, UUID] = {}
        self.hints: list[str] = []
        self.operator: dict | None = None

    # =================================================================== run
    def run(self) -> UUID:
        rng, conn = self.rng, self.conn
        self.now = datetime.now(UTC).replace(microsecond=0)
        self.incident = (self.now - timedelta(days=rng.randint(14, 45))).replace(
            hour=rng.randint(0, 3), minute=rng.randint(0, 59), second=rng.randint(0, 59))
        self.reported = self.incident + timedelta(hours=rng.randint(10, 40))
        self.takedown = self.incident + timedelta(days=rng.randint(1, 4), hours=rng.randint(0, 23))
        self.brand, self.brand_domain, _ = rng.choice([b for b in F.BRANDS if b[0] != "Midstate University"])
        actors = conn.execute("select entity_id, primary_alias, motivation from threat_actors order by primary_alias").fetchall()
        self.actor_id, self.actor_alias, _ = rng.choice([a for a in actors if a[2] in self.actor_motivations])
        self.decoy_id, self.decoy_alias, _ = rng.choice([a for a in actors if a[0] != self.actor_id])
        self.victim = F.person_name(rng)
        self.victim_first = self.victim.split()[0]
        self.victim_email = f"{self.victim.lower().replace(' ', '.')}@midstate.example"
        self.victim_role = rng.choice(self.victim_roles)
        self.registrars = conn.execute("""select e.id, r.name from registrars r join entities e on e.id=r.entity_id
                                          where r.privacy_default order by r.name""").fetchall()
        self.registrar = rng.choice(self.registrars)
        self._load_providers()

        code = f"CASE-{self.incident:%Y}-{rng.randint(1000, 9999)}"
        while conn.execute("select 1 from cases where case_code=%s", (code,)).fetchone():
            code = f"CASE-{self.incident:%Y}-{rng.randint(1000, 9999)}"
        self.case_id = conn.execute(
            """insert into cases(case_code, scenario, difficulty, rng_seed, incident_at, reported_at,
               victim_name, victim_org, victim_role, briefing)
               values (%s,%s,%s,%s,%s,%s,%s,'Midstate University',%s,'(generating)') returning id""",
            (code, self.key, self.p.level, self.seed, self.incident, self.reported, self.victim, self.victim_role),
        ).fetchone()[0]
        self.w = Writer(conn, self.case_id)
        if self.p.require_person:
            self._make_operator()

        briefing, resolution = self.build()      # <- the scenario-specific part

        if self.p.require_person and "person" not in self.slots:
            raise RuntimeError(f"{self.key}: hard case finished without an unmasked person")
        self._finish(briefing, resolution)
        return self.case_id

    def build(self) -> tuple[str, str]:
        raise NotImplementedError

    # ================================================================ basics
    def next_hop(self) -> int:
        self.hop += 1
        return self.hop

    def chain(self, eid: UUID, why: str) -> UUID:
        self.w.role(eid, "chain", self.next_hop(), why)
        return eid

    def clue(self, eid: UUID, why: str) -> UUID:
        self.w.role(eid, "initial_clue", 0, why)
        return eid

    def support(self, eid: UUID, why: str | None = None) -> UUID:
        self.w.role(eid, "supporting", why=why)
        return eid

    def herring(self, eid: UUID, why: str, flag: bool = False) -> UUID:
        self.w.role(eid, "false_flag" if flag else "red_herring", why=why)
        return eid

    def slot(self, key: str, eid: UUID) -> None:
        self.slots[key] = eid

    def world_one(self, sql: str, params=()):
        return self.rng.choice(self.conn.execute(sql, params).fetchall())

    def value_of(self, eid: UUID) -> str:
        return self.conn.execute("select value::text from entities where id=%s", (eid,)).fetchone()[0]

    def fresh(self) -> str:
        """Label for case infra: fresh attacker assets are rarely flagged yet."""
        return {"easy": "malicious", "medium": "suspicious"}.get(self.p.level, "unknown")

    def hard(self) -> bool:
        return self.p.level in ("hard", "expert")

    def at(self, days: float = 0, hours: float = 0) -> datetime:
        return self.incident + timedelta(days=days, hours=hours)

    def local(self, dt: datetime) -> str:
        return dt.astimezone(VICTIM_TZ).strftime("%B %d at %I:%M %p")

    def unique(self, base: str) -> str:
        v = base
        while v in self.used_values:
            v = f"{base}{self.rng.randint(2, 99)}"
        self.used_values.add(v)
        return v

    # ================================================================ network
    def _load_providers(self) -> None:
        rows = self.conn.execute("""
            select hp.name, hp.provider_type, hp.country, i.prefix::text, a.id
            from hosting_providers hp
            join entities pe on pe.id = hp.entity_id and pe.case_id is null
            join entity_relationships r on r.dst_id = hp.entity_id and r.rel = 'operated_by'
            join entities a on a.id = r.src_id
            join entity_relationships r2 on r2.dst_id = a.id and r2.rel = 'announced_by' and r2.case_id is null
            join ip_addresses i on i.entity_id = r2.src_id
            group by 1,2,3,4,5""").fetchall()
        self.providers: dict[str, list[tuple]] = {}
        for name, ptype, cc, prefix, asn_id in rows:
            self.providers.setdefault(ptype, []).append((name, cc, prefix, asn_id))

    def alloc_ip(self, ptype: str, verdict: str | None = None, ports=(22, 80, 443), banner=None) -> tuple[UUID, str]:
        name, cc, prefix, asn_id = self.rng.choice(self.providers[ptype])
        net = ipaddress.IPv4Network(prefix)
        while True:
            ip = str(net.network_address + self.rng.randint(128, 254))
            if ip not in self.used_hosts:
                break
        self.used_hosts.add(ip)
        city = self.rng.choice([c for c, k in F.CITIES if k == cc] or [None])
        eid = self.w.ent("ip", ip, verdict=verdict or self.fresh(), table="ip_addresses", addr=ip, prefix=prefix,
                         country=cc, city=city, geo_accuracy_km=self.rng.choice([50, 100, 250, 500]),
                         is_cdn=False, is_vpn=False, is_tor_exit=False,
                         reverse_dns=self.rng.choice([None, f"vps{self.rng.randint(1000, 9999)}.{name.split()[0].lower()}.example"]),
                         open_ports=list(ports), banner=banner)
        self.w.edge(eid, asn_id, "announced_by", source="DNSChronicle", confidence=1)
        return eid, ip

    def actor_ns(self) -> list[tuple[UUID, str]]:
        if self.p.level == "easy":
            return self.conn.execute("select entity_id, host from nameservers where host like %s",
                                     (f"%{self.registrar[1].lower().split()[0]}%",)).fetchall()
        if hasattr(self, "_ns"):
            return self._ns
        base = f"{self.rng.choice(F.ADJ)}{self.rng.choice(['dns', 'ns', 'resolve'])}{self.rng.randint(1, 99)}.example"
        self._ns = []
        for n in (1, 2):
            host = f"ns{n}.{base}"
            nid = self.w.ent("nameserver", host, verdict=self.fresh(), table="nameservers", host=host)
            self._ns.append((nid, host))
            self.support(nid, "Actor-operated nameserver shared by its domains")
        return self._ns

    def new_lookalike(self, legit: str) -> str:
        while True:
            d = F.lookalike(self.rng, legit)
            if d not in self.used_values and d != legit and not self.conn.execute(
                    "select 1 from entities where kind='domain' and value=%s and case_id is null", (d,)).fetchone():
                self.used_values.add(d)
                return d

    def whois_raw(self, d: dict) -> str:
        red = "REDACTED FOR PRIVACY"
        lines = [f"Domain Name: {d['fqdn'].upper()}", f"Registrar: {d['registrar']}",
                 f"Updated Date: {d['updated']}T00:00:00Z",
                 f"Creation Date: {d['created']}T{self.rng.randint(0, 23):02d}:{self.rng.randint(0, 59):02d}:11Z",
                 f"Registry Expiry Date: {d['expires']}T00:00:00Z", "Domain Status: clientTransferProhibited",
                 f"Registrant Name: {d['name'] or red}", f"Registrant Organization: {d['org'] or red}",
                 f"Registrant Country: {d['country'] or red}",
                 f"Registrant Email: {d['email'] or 'Please query the RDDS service of the Registrar of Record.'}"]
        lines += [f"Name Server: {ns.upper()}" for ns in d["ns"]]
        lines += ["DNSSEC: unsigned", f">>> Last update of WHOIS database: {d['captured']} <<<"]
        if d.get("privacy"):
            lines.insert(6, f"Registrant: {d['privacy']}")
        return "\n".join(lines)

    def mk_domain(self, fqdn: str, *, created: datetime, verdict: str, ns_ids=None, privacy=True,
                  leak: bool = False, typosquat_of: str | None = None, registrar=None) -> UUID:
        """Domain + registrar + nameservers + WHOIS history. leak=True plants the
        operator's email in the first snapshot (hard/expert unmasking)."""
        reg_id, reg_name = registrar or self.registrar
        ns_ids = self.actor_ns() if ns_ids is None else ns_ids
        did = self.w.ent("domain", fqdn, verdict=verdict, table="domains", fqdn=fqdn, registered_domain=fqdn,
                         created_on=created.date(), expires_on=(created + timedelta(days=365)).date(),
                         is_typosquat_of=typosquat_of, popularity_rank=None)
        self.w.edge(did, reg_id, "registered_via", start=created, source="WhoisVault", confidence=1)
        for ns_id, _ in ns_ids:
            self.w.edge(did, ns_id, "uses_nameserver", start=created, source="DNSChronicle", confidence=1)
        leak_who = None
        if leak and self.operator:
            o = self.operator
            leak_who = {"name": "Domain Admin" if self.p.level == "expert" else o["name"], "org": None,
                        "email": o["email"], "country": self.rng.choice(["US", "PA", "NL"])}
        snaps = []
        if leak_who:
            snaps.append((created + timedelta(hours=self.rng.randint(1, 6)), leak_who, None))
        snaps.append((created + timedelta(days=self.rng.randint(1, 3)), None,
                      "Privacy service provided by Withheld for Privacy ehf" if (privacy or leak_who) else None))
        for captured, who, priv in snaps:
            who = who or ({} if priv else {"name": F.person_name(self.rng), "org": None,
                                           "email": f"{F.token(self.rng, 6)}@{self.rng.choice(['mailbox.example', 'tempinbox.test'])}",
                                           "country": self.rng.choice(["US", "PA", "NL", "VN"])})
            data = dict(fqdn=fqdn, registrar=reg_name, created=created.date(), updated=captured.date(),
                        expires=(created + timedelta(days=365)).date(), name=who.get("name"), org=who.get("org"),
                        email=who.get("email"), country=who.get("country"), ns=[n for _, n in ns_ids],
                        captured=captured.isoformat(), privacy=priv)
            wid = self.w.ent("whois_record", f"{fqdn}@{captured:%Y-%m-%dT%H}", label=f"WHOIS {fqdn} ({captured:%Y-%m-%d %H:%M})",
                             table="whois_records", domain_fqdn=fqdn, captured_at=captured, registrar_name=reg_name,
                             created_on=created.date(), updated_on=captured.date(),
                             expires_on=(created + timedelta(days=365)).date(), registrant_name=data["name"],
                             registrant_org=data["org"], registrant_email=data["email"],
                             registrant_country=data["country"], privacy_service=priv, name_servers=data["ns"],
                             status_codes=["clientTransferProhibited"], raw_text=self.whois_raw(data))
            self.w.edge(did, wid, "has_whois", start=captured, source="WhoisVault", confidence=1)
            self.support(wid)
            if who is leak_who and leak_who:
                self.w.edge(wid, self.operator_email(), "registrant_email", source="WhoisVault", confidence=1)
                self.leak_anchor = [did, wid]      # path for unmask(): domain -> whois -> email
        return did

    def mk_url(self, host_id: UUID, url: str, host: str, verdict: str | None = None) -> UUID:
        path = "/" + url.split("/", 3)[3] if url.count("/") >= 3 else "/"
        uid = self.w.ent("url", url, verdict=verdict or self.fresh(), table="urls", full_url=url, host=host, path=path)
        self.w.edge(host_id, uid, "hosts_url", source="urlscope", confidence=2)
        return uid

    def mk_scan(self, url_id: UUID, url: str, at: datetime, *, title: str, ip: str, tracking=(), favicon=None,
                jarm=None, kit=(), final=None, status=200, phash=None, visual_match=None) -> UUID:
        sid = self.w.ent("url_scan", f"scan:{F.token(self.rng, 12)}", label=f"urlscope scan of {url}",
                         table="url_scans", scanned_url=url, scanned_at=at, final_url=final or url, http_status=status,
                         page_title=title, server_header=self.rng.choice(["nginx", "Apache/2.4.58 (Ubuntu)", "LiteSpeed"]),
                         ip_seen=ip, favicon_mmh3=favicon if favicon is not None else F.mmh3_like(self.rng),
                         html_sha256=F.hexstr(self.rng, 32), jarm=jarm or F.jarm(self.rng),
                         tracking_ids=[t for _, t in tracking], kit_indicators=list(kit), screenshot_note=title,
                         phash=phash, visual_match=visual_match)
        self.w.edge(url_id, sid, "scanned_as", start=at, source="urlscope", confidence=2)
        for tid, _ in tracking:
            self.w.edge(sid, tid, "embeds_tracking_id", start=at, source="urlscope", confidence=2)
        return sid

    # =================================================================== site
    def site(self, legit: str, *, title: str, path: str, sibling_fqdns: list[str] | None = None,
             n_siblings: int | None = None, cdn_allowed: bool = True, leak: bool = True,
             phash: str | None = None, visual_match: str | None = None, sibling_title: str | None = None,
             host_type: str | None = None) -> Site:
        """A full piece of phishing infrastructure with realistic history and noise."""
        rng, w, p = self.rng, self.w, self.p
        host_type = host_type or rng.choice(["bulletproof", "vps"])
        origin_id, origin_ip = self.alloc_ip(host_type, "malicious" if p.level == "easy" else "suspicious" if p.level == "medium" else "unknown",
                                             banner="nginx/1.18.0 (Ubuntu)")
        second_id, second_ip = self.alloc_ip(host_type) if self.hard() else (origin_id, origin_ip)
        created = self.incident - timedelta(days=rng.randint(3, 12), hours=rng.randint(0, 23))
        primary_fqdn = self.new_lookalike(legit)
        primary_id = self.mk_domain(primary_fqdn, created=created,
                                    verdict={"easy": "malicious", "medium": "malicious", "hard": "suspicious"}.get(p.level, "unknown"),
                                    privacy=rng.random() < p.whois_privacy_prob, leak=leak and p.require_person,
                                    typosquat_of=legit)
        n = p.sibling_domains if n_siblings is None else n_siblings
        fqdns = sibling_fqdns or [self.new_lookalike(rng.choice([legit, rng.choice(F.BRANDS)[1]])) for _ in range(n)]
        sib_ids = []
        for fq in fqdns[:max(n, 1)]:
            self.used_values.add(fq)
            sid = self.mk_domain(fq, created=created + timedelta(hours=rng.randint(0, 30)), verdict=self.fresh())
            sib_ids.append((sid, fq))
            self.support(sid, "Sibling domain in the same actor infrastructure")

        # DNS history: origin, optional CDN, then sinkhole after takedown
        cdn = cdn_allowed and rng.random() < p.cdn_front_prob
        live = created + timedelta(hours=2)
        cdn_ip = None
        if cdn:
            cdn_ip_id, cdn_ip = self.world_one("select e.id, e.value::text from entities e join ip_addresses i on "
                                               "i.entity_id=e.id where i.is_cdn and e.case_id is null")
            onboard = self.incident - timedelta(hours=rng.randint(20, 40))
            w.edge(primary_id, origin_id, "resolves_to", start=live, end=onboard, source="DNSChronicle", confidence=2)
            w.edge(primary_id, cdn_ip_id, "resolves_to", start=onboard, end=self.takedown, source="DNSChronicle", confidence=2)
            self.herring(cdn_ip_id, "Shared CDN edge IP; hides the real origin server")
            customers = self.conn.execute("""select e.id, e.value::text from entities e join entity_relationships r
                on r.src_id=e.id and r.rel='resolves_to' where e.kind='domain' and e.case_id is null and r.dst_id=%s
                limit 12""", (cdn_ip_id,)).fetchall()
            h = F.hexstr(rng, 32)
            cc = w.ent("certificate", h, label="EdgeShield shared edge certificate", table="certificates", sha256=h,
                       serial=F.hexstr(rng, 16), issuer_cn=CDN_CA[0], issuer_org=CDN_CA[1],
                       subject_cn=f"sni{rng.randint(10000, 99999)}.edgeshield.example",
                       san=[primary_fqdn] + [c[1] for c in customers], not_before=self.at(-2), not_after=self.at(88),
                       self_signed=False, ct_log="OpenCT Mirror", logged_at=self.at(-2))
            for tgt in [primary_id] + [c[0] for c in customers]:
                w.edge(cc, tgt, "cert_covers", source="OpenCT Mirror", confidence=1)
            self.herring(cc, "Shared CDN certificate: covers many unrelated customers")
        else:
            w.edge(primary_id, origin_id, "resolves_to", start=live, end=self.takedown, source="DNSChronicle", confidence=2)
        sink = self.conn.execute("select id from entities where value='203.0.113.250' and case_id is null").fetchone()[0]
        w.edge(primary_id, sink, "resolves_to", start=self.takedown, source="DNSChronicle", confidence=2,
               note="Domain sinkholed after takedown request")
        self.herring(sink, "Sinkhole address after takedown; not attacker-controlled")
        for sid, _ in sib_ids:
            w.edge(sid, second_id, "resolves_to", start=live, end=self.takedown + timedelta(days=rng.randint(0, 10)),
                   source="DNSChronicle", confidence=2)

        # previous tenants and old phishing on the same IP
        for bid, _ in self.conn.execute("""select id, value::text from entities where kind='domain' and case_id is null
                 and verdict='benign' order by random() limit %s""", (p.shared_hosting_noise,)).fetchall():
            s = self.at(-rng.randint(150, 400))
            w.edge(bid, origin_id, "resolves_to", start=s, end=s + timedelta(days=rng.randint(20, 90)),
                   source="DNSChronicle", confidence=3, note="Historic resolution; IP since reassigned")
            w.role(bid, "noise", why="Previous tenant of the IP, months before the incident")
        for _ in range(p.stale_dns_traps):
            fq = self.new_lookalike(rng.choice(F.BRANDS)[1])
            s = self.at(-rng.randint(120, 260))
            sd = self.mk_domain(fq, created=s - timedelta(days=2), verdict="malicious", ns_ids=[], registrar=rng.choice(self.registrars))
            w.edge(sd, origin_id, "resolves_to", start=s, end=s + timedelta(days=rng.randint(5, 30)), source="DNSChronicle", confidence=2)
            self.herring(sd, "Old phishing domain on the same IP; ended months before this incident")

        # certificate that links primary + siblings
        sans = [primary_fqdn, f"www.{primary_fqdn}"] + [fq for _, fq in sib_ids[: (2 if p.level != "expert" else 1)]]
        nb = created + timedelta(hours=rng.randint(1, 5))
        h = F.hexstr(rng, 32)
        cert = w.ent("certificate", h, label=f"cert CN={primary_fqdn}", table="certificates", sha256=h,
                     serial=F.hexstr(rng, 16), issuer_cn=FREE_CA[0], issuer_org=FREE_CA[1], subject_cn=primary_fqdn,
                     san=sans, not_before=nb, not_after=nb + timedelta(days=90), self_signed=False,
                     ct_log="OpenCT Mirror", logged_at=nb + timedelta(minutes=3))
        w.edge(cert, primary_id, "cert_covers", start=nb, source="OpenCT Mirror", confidence=1)
        for sid, fq in sib_ids:
            if fq in sans:
                w.edge(cert, sid, "cert_covers", start=nb, source="OpenCT Mirror", confidence=1)
        self.support(cert, "TLS certificate whose SAN list links actor domains")

        # landing page + sibling pages sharing kit fingerprints
        tid_code = f"G-{F.token(rng, 10).upper()}"
        tid = w.ent("tracking_id", tid_code, table="tracking_ids", vendor="analytics", tracking_code=tid_code)
        self.support(tid, "Analytics ID reused across the actor's pages")
        jarm = F.jarm(rng)
        kit = rng.sample(F.PHISH_KIT_ARTIFACTS, 3)
        landing_url = f"https://{primary_fqdn}{path}"
        landing = self.mk_url(primary_id, landing_url, primary_fqdn,
                              {"easy": "malicious", "medium": "malicious"}.get(p.level, "suspicious"))
        lscan = self.mk_scan(landing, landing_url, self.at(hours=rng.randint(1, 20)), title=title,
                             ip=cdn_ip if cdn else origin_ip, tracking=[(tid, tid_code)], jarm=jarm, kit=kit,
                             phash=phash, visual_match=visual_match)
        self.support(lscan, "Scan of the landing page")
        sibs = []
        for sid, fq in sib_ids:
            u = f"https://{fq}{path.split('?')[0]}"
            uid = self.mk_url(sid, u, fq)
            sc = self.mk_scan(uid, u, self.at(rng.randint(-2, 3)), title=sibling_title or title, ip=second_ip,
                              tracking=[(tid, tid_code)], jarm=jarm, kit=kit[1:], phash=phash)
            self.support(sc)
            sibs.append((sid, fq, uid, sc))
        if second_id != origin_id:
            self.support(second_id, "Second actor server hosting the sibling domains")

        # a DIFFERENT actor's site on the same IP during the incident window
        if p.level != "easy":
            dfq = self.new_lookalike(rng.choice(F.BRANDS)[1])
            dd = self.mk_domain(dfq, created=self.at(-rng.randint(2, 20)), verdict="malicious", ns_ids=[], registrar=rng.choice(self.registrars))
            w.edge(dd, origin_id, "resolves_to", start=self.at(-1), end=self.at(6), source="DNSChronicle", confidence=2)
            old = self.conn.execute("""select c.entity_id from campaigns c join entity_relationships r on r.src_id=c.entity_id
                      and r.rel='attributed_to' and r.dst_id=%s join entities e on e.id=c.entity_id where e.case_id is null
                      limit 1""", (self.decoy_id,)).fetchone()
            if old:
                w.edge(dd, old[0], "used_in", source="CrowdReports", confidence=4)
            self.herring(dd, "Different actor's phishing site on the same bulletproof IP (shared hosting)")

        return Site(primary_id, primary_fqdn, origin_id, origin_ip, second_id, second_ip, cert, sibs, landing,
                    landing_url, lscan, tid, tid_code, jarm, cdn)

    def site_hints(self, s: Site) -> list[str]:
        h = ["Look the domain up in DNS History. Which IP did it point to at the time of the incident, not today?"]
        if s.cdn:
            h.append("A CDN address is shared by thousands of sites. Look further back in the DNS history for the origin.")
        h.append("Search certificate transparency for the domain. Certificates often cover several domains from the same operator.")
        return h

    def redirector(self, target_url_id: UUID, target_url: str) -> UUID:
        """Compromised legitimate site that 302-redirects to the phishing page."""
        cid, cfq, cip = self.conn.execute(
            "select d.id, d.value::text, host(i.addr) from entities d "
            "join entity_relationships r on r.src_id=d.id and r.rel='resolves_to' and r.case_id is null "
            "join ip_addresses i on i.entity_id=r.dst_id where d.kind='domain' and d.case_id is null "
            "and d.verdict='benign' and not i.is_cdn and d.id not in (select entity_id from case_entities where case_id=%s) "
            "order by random() limit 1", (self.case_id,)).fetchone()
        u = f"https://{cfq}/wp-content/uploads/{self.incident:%Y/%m}/{F.token(self.rng, 6)}/index.php"
        uid = self.mk_url(cid, u, cfq, "malicious")
        self.w.edge(uid, target_url_id, "redirects_to", start=self.at(-5), end=self.takedown, source="urlscope",
                    confidence=2, note="HTTP 302 observed by scanner")
        self.mk_scan(uid, u, self.at(hours=self.rng.randint(2, 30)), title="", ip=cip, final=target_url, status=302,
                     kit=["302 redirect to external domain"])
        self.support(uid, "Redirector URL on a compromised legitimate site")
        self.herring(cid, "Legitimate small-business site that was compromised; a victim, not the attacker")
        self.hints.append("The first link may sit on a hacked legitimate site. Where does it redirect?")
        return uid

    def payload(self, sib: tuple) -> tuple[UUID, UUID, str]:
        """Sibling domain serves malware; returns (payload_url_id, sample_id, family_name)."""
        rng, w = self.rng, self.w
        sid, fq = sib[0], sib[1]
        fam_id, fam = self.world_one("select entity_id, family from malware_families where is_commodity=%s",
                                     (self.p.commodity_malware,))
        u = f"https://{fq}/{rng.choice(['download', 'docs', 'files'])}/{rng.choice(['Invoice', 'Statement', 'Remittance'])}_{rng.randint(10000, 99999)}.zip"
        uid = self.mk_url(sid, u, fq)
        c2_id, c2_ip = self.alloc_ip("bulletproof", ports=(443, 8443))
        strings = [f"/gate.php?id={F.token(rng, 6)}"]
        yara = [f"MAL_{fam.replace(' ', '_')}_generic"]
        if self.p.false_flag:
            strings.append(f"built by {self.decoy_alias.lower().replace(' ', '_')} team")
            yara.append(f"APT_{self.decoy_alias.replace(' ', '_')}_strings")
        size = rng.randint(180_000, 2_400_000)
        h = F.hexstr(rng, 32)
        smp = w.ent("malware_sample", h, label=f"{fq} payload", verdict="malicious", table="malware_samples",
                    sha256=h, sha1=F.hexstr(rng, 20), md5=F.hexstr(rng, 16), imphash=F.hexstr(rng, 16),
                    ssdeep=F.ssdeep(rng, size), file_name=u.rsplit("/", 1)[1].replace(".zip", ".exe"),
                    file_type="PE32 executable (GUI) Intel 80386, for MS Windows", size_bytes=size,
                    first_submitted=self.at(hours=rng.randint(6, 72)),
                    av_detections=rng.randint(9, 48) if not self.hard() else rng.randint(2, 14), av_total=72,
                    yara_hits=yara, strings_of_interest=strings,
                    c2_config={"c2": [f"https://{c2_ip}/gate.php"], "botnet": F.token(rng, 6)},
                    sandbox_verdict=f"{fam} detected")
        w.edge(uid, smp, "serves_payload", start=self.at(-1), end=self.takedown, source="urlscope", confidence=2)
        w.edge(smp, fam_id, "sample_of", source="Sandboxr", confidence=2)
        w.edge(smp, c2_id, "c2_contact", start=self.incident, source="Sandboxr", confidence=2)
        self.support(fam_id, "Malware family; commodity families do NOT prove who used them" if self.p.commodity_malware else "Malware family")
        self.support(c2_id, "Command-and-control server from the sample's config")
        return uid, smp, fam

    def origin_client(self) -> str:
        if self.hard():
            return self.rng.choice(self.conn.execute(
                "select value::text from entities where 'tor-exit' = any(tags) or 'vpn' = any(tags)").fetchall())[0]
        return "10.8.0." + str(self.rng.randint(2, 200))

    # ============================================================= artifacts
    def email_addr(self, addr: str, verdict: str = "unknown", disposable: bool = False) -> UUID:
        if addr in self.used_values:
            return self.conn.execute("select id from entities where case_id=%s and kind='email_address' and value=%s",
                                     (self.case_id, addr)).fetchone()[0]
        self.used_values.add(addr)
        return self.w.ent("email_address", addr, verdict=verdict, table="email_addresses", address=addr,
                          provider=addr.split("@")[1], is_disposable=disposable)

    def email_msg(self, *, subject: str, body: str, from_display: str, from_addr: str, envelope: str,
                  sending_ip: tuple[UUID, str] | None, sent: datetime, reply_to: str | None = None,
                  to: str | None = None, dkim_domain: str | None = None, spf: str = "pass",
                  dmarc: str = "fail", x_mailer: str | None = "auto", origin_client: str | None = None,
                  verdict: str = "malicious", label: str | None = None, attachments=()) -> UUID:
        rng = self.rng
        to = to or self.victim_email
        env_dom = envelope.split("@")[1]
        ip = sending_ip[1] if sending_ip else "198.18.40.20"
        origin_client = origin_client or ("10.8.0." + str(rng.randint(2, 200)))
        x_mailer = rng.choice(F.X_MAILERS) if x_mailer == "auto" else x_mailer
        msg_id = f"<{F.token(rng, 12)}.{F.token(rng, 6)}@{env_dom}>"
        rfc = lambda d: d.astimezone(VICTIM_TZ).strftime("%a, %d %b %Y %H:%M:%S -0500")
        dkim = f"pass header.d={dkim_domain}" if dkim_domain else "none"
        hops = [{"from": "mx1.midstate.example", "by": "mailstore.midstate.example", "ip": "198.18.88.10", "at": (sent + timedelta(seconds=4)).isoformat()},
                {"from": f"mail.{env_dom}", "by": "mx1.midstate.example", "ip": ip, "at": (sent + timedelta(seconds=2)).isoformat()},
                {"from": f"[{origin_client}]", "by": f"mail.{env_dom}", "ip": origin_client, "at": sent.isoformat()}]
        raw = [f"Received: from mx1.midstate.example (198.18.88.10) by mailstore.midstate.example; {rfc(sent + timedelta(seconds=4))}",
               f"Received: from mail.{env_dom} (mail.{env_dom} [{ip}]) by mx1.midstate.example with ESMTPS id {F.token(rng, 10).upper()}; {rfc(sent + timedelta(seconds=2))}",
               f"Received: from [{origin_client}] (unknown [{origin_client}]) by mail.{env_dom} with ESMTPSA; {rfc(sent)}",
               f"Authentication-Results: mx1.midstate.example; spf={spf} smtp.mailfrom={envelope}; dkim={dkim}; dmarc={dmarc} header.from={from_addr.split('@')[1]}",
               f"Return-Path: <{envelope}>", f"From: \"{from_display}\" <{from_addr}>"]
        if reply_to:
            raw.append(f"Reply-To: <{reply_to}>")
        raw += [f"To: <{to}>", f"Subject: {subject}", f"Date: {rfc(sent)}", f"Message-ID: {msg_id}"]
        if x_mailer:
            raw.append(f"X-Mailer: {x_mailer}")
        if attachments:
            raw.append("Content-Type: multipart/mixed; boundary=\"b1_" + F.token(rng, 16) + "\"")
        mid = self.w.ent("email_message", msg_id, label=label or f"Email: {subject}", verdict=verdict,
                         table="email_messages", message_id=msg_id, subject=subject,
                         header_from=f"\"{from_display}\" <{from_addr}>", envelope_from=envelope, reply_to=reply_to,
                         to_addr=to, sent_at=sent, x_mailer=x_mailer, spf_result=spf, dkim_result=dkim.split()[0],
                         dmarc_result=dmarc, received_chain=hops, body_text=body, raw_headers="\n".join(raw))
        if sending_ip:
            self.w.edge(mid, sending_ip[0], "sent_from_ip", start=sent, source="Internal SOC", confidence=1)
        self.w.edge(mid, self.email_addr(envelope, self.fresh() if verdict != "benign" else "benign"),
                    "envelope_from", start=sent, source="Internal SOC", confidence=1)
        if reply_to:
            self.w.edge(mid, self.email_addr(reply_to, disposable=True), "reply_to", start=sent, source="Internal SOC", confidence=1)
        for doc in attachments:
            self.w.edge(mid, doc, "attached", start=sent, source="Internal SOC", confidence=1)
        # connect the message to the domain it was sent from (envelope domain), if that domain is a case entity
        dom_row = self.conn.execute("select id from entities where kind='domain' and value=%s and (case_id is null or case_id=%s)",
                                    (env_dom, self.case_id)).fetchone()
        if dom_row:
            self.w.edge(mid, dom_row[0], "sent_via", start=sent, source="Internal SOC", confidence=1)
        return mid

    def mail_domain(self, fqdn: str, *, leak: bool = False, typosquat_of: str | None = None,
                    created: datetime | None = None) -> tuple[UUID, UUID, str]:
        """A sending domain with MX on an actor VPS. Returns (domain_id, ip_id, ip)."""
        created = created or self.at(-self.rng.randint(2, 10))
        did = self.mk_domain(fqdn, created=created, verdict=self.fresh(), leak=leak and self.p.require_person,
                             typosquat_of=typosquat_of)
        ip_id, ip = self.alloc_ip("vps", ports=(25, 587, 22))
        self.w.edge(did, ip_id, "mx_record", start=created, source="DNSChronicle", confidence=1)
        self.w.edge(did, ip_id, "resolves_to", start=created, source="DNSChronicle", confidence=2)
        return did, ip_id, ip

    def phone(self, e164: str, *, line_type: str, carrier: str, cnam: str | None = None, spam: int = 0,
              verdict: str | None = None, country: str = "US", world_check: bool = True) -> UUID:
        self.used_values.add(e164)
        return self.w.ent("phone", e164, verdict=verdict or self.fresh(), table="phone_numbers", e164=e164,
                          country=country, line_type=line_type, carrier=carrier, cnam=cnam, spam_reports=spam,
                          first_reported=(self.at(-self.rng.randint(1, 30)).date() if spam else None))

    def fict_number(self, area: str = "615", toll_free: bool = False) -> str:
        """555-0100..0199 is reserved for fiction in the North American Numbering Plan."""
        while True:
            n = f"+1{'888' if toll_free else area}55501{self.rng.randint(0, 99):02d}"
            if n not in self.used_values:
                return n

    def pretty(self, e164: str) -> str:
        return f"({e164[2:5]}) {e164[5:8]}-{e164[8:]}" if e164.startswith("+1") else e164

    def persona(self, handle: str, platform: str, *, verdict: str = "unknown", **cols) -> UUID:
        short = platform.split("'")[1] if "'" in platform else platform.split()[0]
        value = self.unique(f"{handle}@{short}")
        cols.setdefault("joined_on", (self.at(-self.rng.randint(5, 900))).date())
        return self.w.ent("persona", value, label=cols.get("display_name") or handle, verdict=verdict,
                          table="personas", handle=handle, platform=platform, **cols)

    def post(self, author: UUID, handle: str, platform: str, body: str, at: datetime, *, dm=False,
             reply_to: tuple[UUID, str] | None = None, likes: int = 0, language: str = "en",
             verdict: str = "unknown") -> UUID:
        pid = self.w.ent("social_post", f"post:{F.token(self.rng, 10)}", label=f"@{handle}: {body[:60]}",
                         verdict=verdict, table="social_posts", platform=platform, author_handle=handle,
                         posted_at=at, body=body, language=language,
                         reply_to_handle=reply_to[1] if reply_to else None, is_direct_message=dm, likes=likes)
        self.w.edge(author, pid, "posted", start=at, source="Linkline" if "Linkline" in platform else "Chirper", confidence=1)
        if reply_to:
            self.w.edge(pid, reply_to[0], "replied_to", start=at, source="Chirper", confidence=1)
        return pid

    def image(self, description: str, *, phash: str | None = None, synthetic: float | None = None,
              exif_camera=None, exif_taken=None, exif_location=None) -> UUID:
        ph = phash or F.hexstr(self.rng, 8)
        return self.w.ent("image", f"img:{ph}:{F.token(self.rng, 4)}", label=description, table="images", phash=ph,
                          width=self.rng.choice([640, 1080, 1200]), height=self.rng.choice([640, 1080, 1350]),
                          exif_camera=exif_camera, exif_taken_at=exif_taken, exif_location=exif_location,
                          synthetic_score=synthetic, description=description)

    def document(self, file_name: str, *, excerpt: str, author=None, modified_by=None, company=None,
                 tool="Microsoft Word 2016", created: datetime | None = None, verdict: str | None = None,
                 published_url: str | None = None, pages: int = 1) -> UUID:
        h = F.hexstr(self.rng, 32)
        created = created or self.at(-self.rng.randint(1, 5))
        return self.w.ent("document", h, label=file_name, verdict=verdict or self.fresh(), table="documents",
                          file_name=file_name, file_type="PDF document" if file_name.endswith(".pdf") else "Office document",
                          sha256=h, size_bytes=self.rng.randint(40_000, 900_000), meta_author=author,
                          meta_last_modified_by=modified_by, meta_company=company, meta_creator_tool=tool,
                          meta_created=created, meta_modified=created + timedelta(minutes=self.rng.randint(5, 600)),
                          page_count=pages, text_excerpt=excerpt, published_url=published_url)

    def audio(self, kind: str, *, transcript: str, at: datetime, duration: int, speaker: str, caller_id=None,
              stir=None, synthetic=None, voiceprint=None, source_url=None, note=None, verdict="unknown") -> UUID:
        return self.w.ent("audio_recording", f"audio:{F.token(self.rng, 10)}", label=f"{kind}: {speaker}",
                          verdict=verdict, table="audio_recordings", recording_type=kind, duration_s=duration,
                          recorded_at=at, caller_id=caller_id, stir_shaken=stir, speaker_claimed=speaker,
                          synthetic_score=synthetic, voiceprint_hash=voiceprint or F.hexstr(self.rng, 16),
                          transcript=transcript, source_url=source_url, analysis_note=note)

    def sms(self, *, from_number: str, body: str, at: datetime, language="en-US", style=None, channel="SMS") -> UUID:
        return self.w.ent("sms_message", f"sms:{F.token(self.rng, 10)}", label=f"SMS from {self.pretty(from_number)}",
                          verdict="malicious", table="sms_messages", from_number=from_number, to_number="+16155550100",
                          sent_at=at, body=body, language=language, style_notes=style, channel=channel)

    def payment(self, method: str, provider: str, identifier: str, *, holder=None, mule=False, notes=None,
                verdict: str | None = None) -> UUID:
        return self.w.ent("payment_account", self.unique(f"{provider}:{identifier}"), label=f"{provider} {identifier}",
                          verdict=verdict or self.fresh(), table="payment_accounts", method=method, provider=provider,
                          identifier=identifier, holder_name=holder, opened_on=self.at(-self.rng.randint(20, 400)).date(),
                          is_mule=mule, notes=notes)

    def wallet(self, chain: str = "tron", received: float | None = None) -> UUID:
        rng = self.rng
        addr = ("T" + "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz123456789") for _ in range(33))
                if chain == "tron" else "bc1q" + F.token(rng, 38))
        return self.w.ent("crypto_wallet", addr, verdict=self.fresh(), table="crypto_wallets", chain=chain, address=addr,
                          total_received=round(received if received is not None else rng.uniform(500, 90_000), 2),
                          tx_count=rng.randint(4, 400))

    def lure(self, theme: str, locale: str, language: str, sample: str, *, hook=None, kit=None,
             template_hash: str | None = None) -> UUID:
        th = template_hash or F.hexstr(self.rng, 16)
        return self.w.ent("lure_template", f"tpl:{th[:12]}:{locale}", label=f"{theme} ({locale})", verdict=self.fresh(),
                          table="lure_templates", template_hash=th, theme=theme, locale=locale, language=language,
                          cultural_hook=hook, kit_name=kit, sample_text=sample)

    def complaints(self, mentions: list[UUID], narratives: list[str], *, indicators: list[str],
                   n: int | None = None, loss=(50, 4000), role: str = "supporting") -> list[UUID]:
        """Other victims' reports to a (fictional) fraud portal. Each mentions the given entities."""
        rng = self.rng
        out = []
        for _ in range(n or (2 if self.p.level == "easy" else 3 if self.p.level == "medium" else 4)):
            region = rng.choice(["TN", "KY", "GA", "AL", "TX", "OH", "FL", "ON (Canada)", "England (UK)"])
            cid = self.w.ent("complaint", f"SW-{self.at().year}-{rng.randint(100000, 999999)}", label="ScamWatch report",
                             table="complaints", portal="ScamWatch Portal", filed_at=self.at(rng.uniform(-20, 10)),
                             reporter_region=region, loss_amount=round(rng.uniform(*loss), 2),
                             narrative=rng.choice(narratives), indicators=indicators)
            for m in mentions:
                self.w.edge(cid, m, "mentions", start=self.at(-20), source="ScamWatch Portal", confidence=3)
            self.w.role(cid, role, why="Report from another victim of the same operation")
            out.append(cid)
        # unrelated reports that surface on keyword searches
        for _ in range(rng.randint(2, 5)):
            other = self.fict_number(rng.choice(["615", "629", "931", "901"]))
            self.used_values.add(other)
            nid = self.w.ent("complaint", f"SW-{self.at().year}-{rng.randint(100000, 999999)}", label="ScamWatch report",
                             table="complaints", portal="ScamWatch Portal", filed_at=self.at(rng.uniform(-60, 10)),
                             reporter_region=rng.choice(["TN", "NC", "VA", "MI"]), loss_amount=round(rng.uniform(0, 900), 2),
                             narrative=rng.choice(narratives).split(".")[0] + ". Different caller each time.",
                             indicators=[other])
            self.w.role(nid, "noise", why="Similar story, different operation")
        return out

    # =========================================================== attribution
    def attribution(self, anchors: list[UUID], *, summary: str, mention: list[UUID] | None = None,
                    targeting: str = "higher education") -> UUID:
        """Campaign + vendor attribution + decoys. `anchors` are what the vendor tied to the campaign."""
        rng, w, conn = self.rng, self.w, self.conn
        cname = F.op_name(rng)
        while conn.execute("select 1 from campaigns where name=%s", (cname,)).fetchone():
            cname = F.op_name(rng)
        camp = w.ent("campaign", cname, verdict="malicious", table="campaigns", name=cname,
                     started_on=self.at(-rng.randint(5, 30)).date(), ended_on=None, objective=self.category,
                     targeting=targeting)
        for a in anchors:
            w.edge(a, camp, "used_in", source="Kestrel Threat Intelligence", confidence=2)
        w.edge(camp, self.actor_id, "attributed_to", source="Kestrel Threat Intelligence", confidence=2)

        vendors = conn.execute("""select s.name, s.reliability, a.alias from actor_aliases a join sources s on s.id=a.named_by
                                  where a.actor_id=%s and s.reliability in ('B','C') order by s.name""", (self.actor_id,)).fetchall()
        if self.p.level == "easy":
            vendor, rel, alias = next((v for v in vendors if v[0].startswith("Kestrel")), vendors[0])
        else:
            vendor, rel, alias = rng.choice([v for v in vendors if not v[0].startswith("Kestrel")] or vendors)
        pub = min(self.now - timedelta(days=1), self.at(rng.randint(3, 9)))
        body = (f"{vendor} is tracking an operation we call {cname}. {summary} "
                f"Indicators: {', '.join(self.value_of(m) for m in (mention or anchors)[:4])}. "
                f"We assess with moderate confidence that {cname} is run by the group we track as {alias}.")
        art = w.ent("web_article", f"{vendor}: {cname}", table="web_articles", publisher=vendor,
                    author=F.person_name(rng), title=f"{cname}: {self.title} activity targeting {targeting}",
                    published_at=pub, body=body, source_id=w.source(vendor))
        for t in [camp, self.actor_id] + (mention or anchors):
            w.edge(art, t, "mentions", start=pub, source=vendor, confidence=2)
        self.support(art, f"Vendor report (reliability {rel}) naming the actor as '{alias}'")
        self.vendor_alias = alias

        dalias = conn.execute("select alias from actor_aliases where actor_id=%s order by alias limit 1",
                              (self.decoy_id,)).fetchone()[0]
        self.decoy_alias_used = dalias
        target = (mention or anchors)[0]
        srcs = ["CrowdReports", "0xRumors", "InfoSec Daily"]
        for k in range(self.p.decoy_actor_articles):
            src = srcs[k % len(srcs)]
            d = w.ent("web_article", f"{src} post {F.token(rng, 5)}", table="web_articles", publisher=src,
                      author=F.handle(rng), title=rng.choice([f"{dalias} back at it?", f"IOC dump: new {self.title.lower()} wave",
                                                             f"Is {dalias} behind this {self.title.lower()} wave?"]),
                      published_at=min(self.now - timedelta(hours=6), self.at(rng.randint(1, 5))),
                      body=rng.choice([f"Seeing {self.value_of(target)} pop up again. Smells like {dalias}. Unconfirmed.",
                                       f"TTPs line up with {dalias}: same lure style, edu targets. Low confidence, sharing anyway.",
                                       f"Our honeypot saw {self.value_of(target)} next to known {dalias} infra. Not verified."]),
                      source_id=w.source(src))
            w.edge(d, target, "mentions", source=src, confidence=5)
            w.edge(d, self.decoy_id, "mentions", source=src, confidence=5)
            self.herring(d, f"Low-reliability post blaming {dalias}", flag=True)
        if self.p.false_flag:
            w.edge(camp, self.decoy_id, "attributed_to", source="CrowdReports", confidence=5,
                   note="Based on lure similarity only; not corroborated")
            self.herring(self.decoy_id, "Decoy actor: similar style, no infrastructure or money overlap", flag=True)
        elif self.p.decoy_actor_articles:
            self.herring(self.decoy_id, "Actor blamed by unreliable sources only")
        self.campaign_id, self.campaign_name = camp, cname
        self.slot("campaign", camp)
        self.slot("actor", self.actor_id)
        return camp

    def attribution_hints(self) -> list[str]:
        return ["Vendors name the same actor differently. Look the report's alias up in the Directory.",
                "Weigh your sources. A D- or E-rated post is a lead, not proof. Does anything actually overlap?"]

    # ============================================================ unmasking
    def _make_operator(self) -> None:
        pid, pname, pcity = self.world_one("""select p.entity_id, p.full_name, p.city from persons p
                                              join entities e on e.id=p.entity_id where e.case_id is null""")
        h = F.handle(self.rng)
        self.operator = dict(person_id=pid, name=pname, city=pcity, handle=h,
                             email=f"{h}{self.rng.randint(1, 99)}@{self.rng.choice(['mailbox.example', 'webpost.example'])}")
        self._op_email = None

    def operator_email(self) -> UUID:
        if self._op_email is None:
            self._op_email = self.email_addr(self.operator["email"])
        return self._op_email

    def unmask(self, lead_in: list[UUID]) -> None:
        """lead_in: chain entities from an already-chained node to the operator email
        (e.g. [domain, whois_record]). Builds email -> breach -> forum -> social -> person."""
        if not self.operator:
            return
        rng, w, o = self.rng, self.w, self.operator
        em = self.operator_email()
        for b, uname in (("Darkmarket%", o["handle"]), ("GamerHub%", o["handle"] + str(rng.randint(1, 9)))):
            bid = self.conn.execute("select id from entities where kind='breach' and value like %s", (b,)).fetchone()[0]
            self.conn.execute("""insert into breach_records(breach_id,email,username,password_hash,hash_type,signup_ip,case_id)
                                 values (%s,%s,%s,%s,'bcrypt',%s,%s)""",
                              (bid, o["email"], uname, F.fake_password_hash(rng, "bcrypt"),
                               rng.choice(["192.0.2.50", "192.0.2.51"]), self.case_id))
            w.edge(em, bid, "leaked_in", source="BreachIndex", confidence=2)
        forum = rng.choice(F.FORUM_PLATFORMS)
        fp = self.persona(o["handle"], forum, verdict="suspicious", post_count=rng.randint(40, 700),
                          bio=self.forum_bio(), pgp_fingerprint=F.hexstr(rng, 20).upper(), language="en",
                          utc_offset_guess=rng.choice([-6, -5, 0, 1, 2, 3]), last_active=self.at(2),
                          joined_on=self.at(-rng.randint(300, 900)).date())
        w.edge(fp, em, "uses_email", source="BreachIndex", confidence=2, note="from the forum's leaked user table")
        w.edge(fp, self.actor_id, "alias_of", source="0xRumors", confidence=4, note="advertises services matching this campaign")
        social = rng.choice(F.SOCIAL_PLATFORMS)
        sp = self.persona(o["handle"], social, post_count=rng.randint(5, 300),
                          bio=f"{o['name'].split()[0]} | {o['city']} | python, side hustles, crypto",
                          joined_on=self.at(-rng.randint(900, 2500)).date(), language="en")
        w.edge(fp, sp, "same_username", source="Internal SOC", confidence=3, note="identical handle and matching avatar")
        w.edge(sp, o["person_id"], "identified_as", source="Internal SOC", confidence=2,
               note="first name and city in bio match; profile links a personal site")
        # Connect the operator email into the existing chain so the identity path is reachable.
        if lead_in:
            for eid in lead_in:
                self.chain(eid, "Lead toward the operator's real identity")
        else:
            # tie the email to the last scam persona already on the chain (romance, pig-butchering, ...)
            anchor = self.conn.execute(
                "select entity_id from case_entities where case_id=%s and role='chain' "
                "and entity_id in (select entity_id from personas) order by hop desc limit 1",
                (self.case_id,)).fetchone()
            if not anchor:
                anchor = self.conn.execute(
                    "select entity_id from case_entities where case_id=%s and role in ('chain','initial_clue') "
                    "order by hop desc limit 1", (self.case_id,)).fetchone()
            w.edge(anchor[0], em, "uses_email", source="BreachIndex", confidence=3,
                   note="operator reused this email on the account behind the scheme")
        self.chain(em, "Operator email, reused across breached sites")
        self.chain(fp, "Criminal-forum persona tied to the campaign")
        self.chain(sp, "Same handle on a personal platform")
        self.chain(o["person_id"], "The person behind the operation")
        decoy = self.world_one("""select p.entity_id from persons p join entities e on e.id=p.entity_id
                                  where e.case_id is null and p.entity_id <> %s""", (o["person_id"],))[0]
        lp = self.persona(o["handle"] + "_", "Pixgram (photos)", post_count=rng.randint(10, 900), bio="travel + coffee")
        w.edge(lp, decoy, "identified_as", source="CrowdReports", confidence=3)
        self.herring(lp, "Similar handle, different person, no link to the forum account")
        self.slot("person", o["person_id"])
        self.hints += ["WHOIS history and leaked user tables keep old records. Find an email the operator reused.",
                       "Search that email in Breach Lookup, then the username on other platforms."]

    def forum_bio(self) -> str:
        return "selling fresh logs + mule accounts. escrow only. no edu refunds."

    # =============================================================== finish
    def _finish(self, briefing: str, resolution: str) -> None:
        conn = self.conn
        fields = {k: (label, kind) for k, label, kind in self.report_fields}
        # labels/kinds for slots that attribution() or unmask() add
        kind_of = {"actor": "threat_actor", "campaign": "campaign", "person": "person"}
        defaults = {"actor": "Threat actor responsible", "campaign": "Campaign",
                    "person": "Real person operating the scheme"}
        for k in self.slots:
            if k not in fields:
                kind = kind_of.get(k) or self.conn.execute(
                    "select kind::text from entities where id=%s", (self.slots[k],)).fetchone()[0]
                fields[k] = (defaults.get(k, k.replace("_", " ").title()), kind)
        # weights: actor 0.3, person 0.2, rest split the remainder
        weights = {k: (0.30 if k == "actor" else 0.20 if k == "person" else None) for k in self.slots}
        rest = [k for k, v in weights.items() if v is None]
        left = max(0.1, 1.0 - sum(v for v in weights.values() if v))
        for k in rest:
            weights[k] = round(left / len(rest), 3)
        slots = {k: {"entity_id": str(v), "label": fields[k][0], "kind": fields[k][1], "weight": weights[k]}
                 for k, v in self.slots.items()}
        conn.execute("""insert into case_ground_truth(case_id, actor_id, campaign_id, primary_domain_id, origin_ip_id,
                        person_id, resolution_text, answer_slots) values (%s,%s,%s,%s,%s,%s,%s,%s)""",
                     (self.case_id, self.actor_id, self.slots.get("campaign"),
                      self.slots.get("primary_domain") or self.slots.get("lookalike_domain"),
                      self.slots.get("origin_ip"), self.slots.get("person"), resolution,
                      __import__("json").dumps(slots)))
        hints = self.hints + self.attribution_hints()
        for i, h in enumerate(hints, start=1):
            conn.execute("insert into case_hints(case_id, step, hint, cost) values (%s,%s,%s,%s)", (self.case_id, i, h, 50 * i))
        objective = ("\n\nCASE REPORT NEEDS: " + "; ".join(fields[k][0] for k in self.slots))
        conn.execute("update cases set briefing=%s where id=%s", (briefing + objective, self.case_id))
        conn.execute("""insert into case_entities(case_id, entity_id, role) select %s, id, 'noise' from entities
                        where case_id=%s on conflict do nothing""", (self.case_id, self.case_id))
