"""Seed the persistent WORLD (rows with case_id NULL).

Run once after migrations:  make db-seed
Re-running wipes world rows first (cases are left alone only if you use
`--keep-cases`; by default everything is reset for a clean demo).

The world is what makes searches noisy and realistic: hundreds of benign
domains on shared hosting, a CDN fronting everything, commodity malware used
by several actors, vendors that disagree on actor names, and thousands of
breach records that are NOT your suspect.
"""
from __future__ import annotations

import argparse
import csv
import ipaddress
import os
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg

from . import fakes as F
from .writer import Writer

UTC = timezone.utc

SOURCES = [
    # name, type, reliability, description
    ("DNSChronicle", "passive_dns", "B", "Commercial passive DNS sensor network"),
    ("WhoisVault", "whois", "B", "Historical WHOIS snapshots, captured daily"),
    ("OpenCT Mirror", "ct_log", "A", "Certificate Transparency log mirror"),
    ("urlscope", "url_scanner", "B", "Public URL scanner; community submissions"),
    ("Sandboxr", "sandbox", "B", "Automated malware detonation sandbox"),
    ("SampleBazaar", "sandbox", "B", "Community malware sample exchange"),
    ("Kestrel Threat Intelligence", "vendor_report", "B", "Established TI vendor"),
    ("Halberd Labs", "vendor_report", "C", "Mid-size vendor, occasionally over-attributes"),
    ("Northgate Security Blog", "blog", "C", "Independent researcher blog"),
    ("InfoSec Daily", "news", "C", "Security news site; relies on vendor claims"),
    ("CrowdReports", "blog", "D", "Crowd-sourced IOC feed, unvetted"),
    ("0xRumors", "forum", "E", "Anonymous underground forum scrape"),
    ("Pastepit", "paste", "E", "Paste-site monitor"),
    ("BreachIndex", "breach_corpus", "C", "Aggregated historic breach corpus"),
    ("Victim Report", "victim_report", "B", "Statement collected from the reporting user"),
    ("Internal SOC", "internal", "A", "Your organisation's own mail/proxy logs"),
    ("reverse image engine", "reverse_image", "B", "Reverse image search index"),
    ("ScamWatch Portal", "complaint_portal", "C", "Public scam/fraud complaint portal"),
    ("ChainScan", "blockchain", "B", "Public blockchain explorer / tracing"),
    ("Carrier Lookup", "carrier_lookup", "B", "Phone carrier / line-type lookup"),
    ("audio lab", "audio_lab", "B", "Voice-clone / deepfake audio analysis"),
    ("document lab", "document_lab", "B", "Document metadata / forgery analysis"),
    ("HeartLink", "social_platform", "C", "Dating platform data"),
    ("Chirper", "social_platform", "C", "Microblogging platform data"),
    ("Linkline", "social_platform", "C", "Professional network data"),
    ("Pixgram", "social_platform", "C", "Photo-sharing platform data"),
]

# name, country, type, ASN, abuse responsiveness, number of /24s
PROVIDERS = [
    ("Stratus Cloud", "US", "hyperscale_cloud", 64600, "fast", 4),
    ("Nimbus Compute", "DE", "hyperscale_cloud", 64601, "fast", 3),
    ("EdgeShield CDN", "US", "cdn", 64602, "normal", 2),
    ("Hostiva", "NL", "vps", 64603, "normal", 3),
    ("CheapVPS Ltd", "GB", "vps", 64604, "slow", 3),
    ("Voltserver", "RO", "vps", 64605, "slow", 3),
    ("SiteBarn Hosting", "US", "shared_hosting", 64606, "normal", 3),
    ("WebNest", "FR", "shared_hosting", 64607, "normal", 2),
    ("Obsidian Hosting", "SC", "bulletproof", 64608, "ignores", 3),
    ("Tessera Networks", "PA", "bulletproof", 64609, "ignores", 2),
    ("Metrolink Broadband", "US", "residential_isp", 64610, "slow", 2),
    ("Midstate University Network", "US", "university", 64611, "fast", 1),
]

REGISTRARS = [
    ("NameHarbor", 9001, False), ("RegistraPro", 9002, False), ("DomainDock", 9003, False),
    ("Cheapnames Inc", 9004, True), ("PrivacyFirst Registrar", 9005, True),
    ("Offshore Domains SA", 9006, True),
]

MALWARE = [
    # family, type, commodity?, description
    ("RavenSteal", "information stealer", True, "Sold as malware-as-a-service; browser credential and wallet theft"),
    ("Quillsteal", "information stealer", True, "Leaked builder widely reused since 2025"),
    ("Mothwing Loader", "loader", True, "Rented loader; drops follow-on payloads"),
    ("Nightjar RAT", "remote access trojan", False, "Custom RAT, tied to a single operator group"),
    ("Tallow Banker", "banking trojan", False, "Web-inject banking trojan"),
    ("Cinder", "loader", False, "Small custom downloader"),
    ("Hexbloom", "ransomware", True, "Ransomware-as-a-service affiliate program"),
    ("Warden Keylogger", "keylogger", True, "Cheap keylogger sold on forums"),
]

# primary alias -> (motivation, sophistication, active UTC hours, aliases by vendor)
ACTORS = [
    ("GLASS HERON", "financial", "intermediate", (6, 15),
     {"Kestrel Threat Intelligence": "GLASS HERON", "Halberd Labs": "TA-417", "Northgate Security Blog": "Silent Ledger"}),
    ("COPPER MANTIS", "financial", "advanced", (13, 22),
     {"Kestrel Threat Intelligence": "COPPER MANTIS", "Halberd Labs": "TA-203", "InfoSec Daily": "the Mantis crew"}),
    ("PALE ORCHID", "financial", "novice", (0, 9),
     {"Kestrel Threat Intelligence": "PALE ORCHID", "Halberd Labs": "TA-588", "CrowdReports": "OrchidPhish"}),
    ("RUST LANTERN", "financial", "intermediate", (15, 23),
     {"Kestrel Threat Intelligence": "RUST LANTERN", "Halberd Labs": "TA-311", "Northgate Security Blog": "Lantern Kit Gang"}),
    ("QUIET MERIDIAN", "espionage", "advanced", (4, 12),
     {"Kestrel Threat Intelligence": "QUIET MERIDIAN", "Halberd Labs": "TA-090", "InfoSec Daily": "Meridian"}),
    ("SALT HARVEST", "financial", "novice", (17, 24),
     {"Kestrel Threat Intelligence": "SALT HARVEST", "Halberd Labs": "TA-640", "CrowdReports": "SaltyPhish"}),
    ("STATIC KETTLE", "hacktivist", "novice", (8, 18),
     {"Kestrel Threat Intelligence": "STATIC KETTLE", "Northgate Security Blog": "KettleTeam"}),
    ("WINTER RELAY", "financial", "advanced", (1, 10),
     {"Kestrel Threat Intelligence": "WINTER RELAY", "Halberd Labs": "TA-155", "InfoSec Daily": "RelayBrokers"}),
]
ORIGINS = ["US", "BR", "NG", "GB", "RO", "VN", "IN", "UA", "TR", "ID", "MX", "PH", "ZA", "FR"]

BREACHES = [
    ("GamerHub 2019", date(2019, 6, 2), ["email", "username", "password_hash", "ip"], "md5"),
    ("ShopLane 2021", date(2021, 3, 18), ["email", "name", "password_hash", "phone"], "sha1"),
    ("Darkmarket.test forum 2023", date(2023, 11, 5), ["email", "username", "password_hash", "ip"], "bcrypt"),
    ("Fitlog App 2024", date(2024, 8, 21), ["email", "name", "username"], "bcrypt"),
    ("Pixgram scrape 2025", date(2025, 2, 11), ["username", "name", "bio"], None),
]

EMAIL_PROVIDERS = ["mailbox.example", "fastmail.test", "protonish.test", "webpost.example",
                   "tempinbox.test"]


def prefixes_for(idx: int, count: int) -> list[ipaddress.IPv4Network]:
    base = ipaddress.IPv4Network("198.18.0.0/15")
    subnets = list(base.subnets(new_prefix=24))
    return [subnets[idx * 8 + k] for k in range(count)]


def load_people(csv_path: Path | None, rng: random.Random, n: int) -> list[dict]:
    """Use the Kaggle-style OSINT profile CSV if present, else synthesize.

    Only name/username/company/city-like fields are imported. Real-looking IPs
    and domains in the CSV are ignored on purpose (they could be real).
    """
    people: list[dict] = []
    if csv_path and csv_path.exists():
        with csv_path.open(newline="", encoding="utf-8", errors="replace") as fh:
            reader = csv.DictReader(fh)
            cols = {c.lower().strip(): c for c in (reader.fieldnames or [])}

            def pick(row, *names):
                for nm in names:
                    if nm in cols and row.get(cols[nm]):
                        return row[cols[nm]].strip()
                return None
            for i, row in enumerate(reader):
                name = pick(row, "name", "full_name", "fullname")
                if not name:
                    continue
                email = pick(row, "email", "email_address") or ""
                local = email.split("@")[0] if "@" in email else F.token(rng)
                city, cc = rng.choice(F.CITIES)
                people.append({
                    "name": name, "username": pick(row, "username", "user_name", "handle") or F.handle(rng),
                    "email_local": local, "employer": pick(row, "company", "employer", "organization"),
                    "city": city, "country": cc, "row": i + 2,
                })
    while len(people) < n:
        city, cc = rng.choice(F.CITIES)
        name = F.person_name(rng)
        people.append({"name": name, "username": F.handle(rng),
                       "email_local": name.lower().replace(" ", ".") + str(rng.randint(1, 99)),
                       "employer": None, "city": city, "country": cc, "row": None})
    rng.shuffle(people)
    return people


def seed(conn: psycopg.Connection, rng: random.Random, people_csv: Path | None) -> None:
    w = Writer(conn)
    now = datetime.now(UTC)

    for name, stype, rel, desc in SOURCES:
        conn.execute("insert into sources(name, source_type, reliability, description) values (%s,%s,%s,%s)",
                     (name, stype, rel, desc))

    # --- providers, ASNs, IPs ------------------------------------------
    for idx, (name, cc, ptype, asn, abuse, n24) in enumerate(PROVIDERS):
        pid = w.ent("hosting_provider", name, verdict="suspicious" if ptype == "bulletproof" else "benign",
                    world=True, table="hosting_providers", name=name, country=cc, provider_type=ptype,
                    abuse_email=f"abuse@{name.lower().replace(' ', '')}.example",
                    abuse_responsiveness=abuse)
        aid = w.ent("asn", f"AS{asn}", label=f"AS{asn} {name.upper().replace(' ', '-')}", world=True,
                    verdict="benign", table="asns", asn=asn, as_name=name.upper().replace(" ", "-"), country=cc)
        w.edge(aid, pid, "operated_by", world=True, confidence=1)
        for net in prefixes_for(idx, n24):
            # world uses .1-.60 of each /24; cases allocate from .128-.254
            for host in range(1, 61, rng.choice([3, 4, 5])):
                ip = str(net.network_address + host)
                city, _ = rng.choice([c for c in F.CITIES if c[1] == cc] or [("", cc)])
                iid = w.ent("ip", ip, world=True, verdict="benign",
                            tags=["cdn"] if ptype == "cdn" else [],
                            table="ip_addresses", addr=ip, prefix=str(net), country=cc,
                            region=None, city=city or None, geo_accuracy_km=rng.choice([25, 50, 100, 250]),
                            is_cdn=ptype == "cdn", is_vpn=False, is_tor_exit=False,
                            reverse_dns=f"{ip.replace('.', '-')}.{name.split()[0].lower()}.example",
                            open_ports=rng.sample([22, 80, 443, 8080, 25, 3389], rng.randint(1, 3)))
                w.edge(iid, aid, "announced_by", world=True, confidence=1)

    # a couple of Tor exits and a commercial VPN pool: dead ends for email origins
    for k, ip in enumerate(["192.0.2.10", "192.0.2.11", "192.0.2.12"]):
        w.ent("ip", ip, world=True, verdict="suspicious", tags=["tor-exit"], table="ip_addresses",
              addr=ip, prefix="192.0.2.0/24", country=rng.choice(["DE", "NL", "SE"]),
              is_tor_exit=True, is_vpn=False, is_cdn=False, reverse_dns=f"tor-exit-{k}.relay.test")
    for k, ip in enumerate(["192.0.2.50", "192.0.2.51", "192.0.2.52", "192.0.2.53"]):
        w.ent("ip", ip, world=True, verdict="unknown", tags=["vpn"], table="ip_addresses",
              addr=ip, prefix="192.0.2.0/24", country=rng.choice(["CH", "PA", "IS"]),
              is_tor_exit=False, is_vpn=True, is_cdn=False, reverse_dns=f"node{k}.hideipvpn.test")
    # sinkhole used after takedowns
    w.ent("ip", "203.0.113.250", world=True, verdict="sinkholed", tags=["sinkhole"], table="ip_addresses",
          addr="203.0.113.250", prefix="203.0.113.0/24", country="US", is_cdn=False,
          reverse_dns="sinkhole.kestrel-ti.example")

    # --- registrars / nameservers --------------------------------------
    for name, iana, priv in REGISTRARS:
        rid = w.ent("registrar", name, world=True, verdict="benign", table="registrars",
                    name=name, iana_id=iana, privacy_default=priv)
        for n in (1, 2):
            host = f"ns{n}.{name.lower().split()[0]}.example"
            w.ent("nameserver", host, world=True, verdict="benign", table="nameservers", host=host)

    # --- brands (the legit sites being impersonated) -------------------
    for brand, dom, sector in F.BRANDS:
        oid = w.ent("organization", brand, world=True, verdict="benign", table="organizations",
                    name=brand, sector=sector, country="US")
        w.ent("domain", dom, world=True, verdict="benign", table="domains", fqdn=dom,
              registered_domain=dom, created_on=date(2008 + rng.randint(0, 10), rng.randint(1, 12), 1),
              popularity_rank=rng.randint(2_000, 90_000))

    # --- benign web: shared hosting + CDN customers ---------------------
    ips_by_type: dict[str, list] = {}
    for row in conn.execute("""select e.id, e.value, hp.provider_type
                               from entities e join ip_addresses i on i.entity_id=e.id
                               join entity_relationships r1 on r1.src_id=e.id and r1.rel='announced_by'
                               join entity_relationships r2 on r2.src_id=r1.dst_id and r2.rel='operated_by'
                               join hosting_providers hp on hp.entity_id=r2.dst_id
                               where e.case_id is null"""):
        ips_by_type.setdefault(row[2], []).append(row[0])
    seen = set()
    for _ in range(420):
        dom = F.benign_domain(rng)
        if dom in seen:
            continue
        seen.add(dom)
        created = now.date() - timedelta(days=rng.randint(200, 4000))
        did = w.ent("domain", dom, world=True, verdict="benign", table="domains", fqdn=dom,
                    registered_domain=dom, created_on=created,
                    popularity_rank=rng.choice([None, None, rng.randint(100_000, 999_999)]))
        host_type = rng.choices(["shared_hosting", "cdn", "hyperscale_cloud", "vps"], [5, 4, 2, 1])[0]
        ip = rng.choice(ips_by_type[host_type])
        w.edge(did, ip, "resolves_to", start=datetime.combine(created, datetime.min.time(), UTC)
               + timedelta(days=rng.randint(1, 30)), end=None, source="DNSChronicle", confidence=2, world=True)

    # --- malware families ------------------------------------------------
    fam_ids = {}
    for fam, mtype, commodity, desc in MALWARE:
        fam_ids[fam] = w.ent("malware_family", fam, world=True, verdict="malicious",
                             table="malware_families", family=fam, malware_type=mtype,
                             first_observed=date(2023 + rng.randint(0, 2), rng.randint(1, 12), rng.randint(1, 28)),
                             is_commodity=commodity, description=desc)

    # --- threat actors, aliases, historic campaigns ----------------------
    used_ops: set[str] = set()
    for primary, motive, soph, hours, aliases in ACTORS:
        aid = w.ent("threat_actor", primary, world=True, verdict="malicious", table="threat_actors",
                    primary_alias=primary, motivation=motive, sophistication=soph,
                    suspected_origin=rng.choice(ORIGINS),
                    active_hours_utc=f"[{hours[0]},{hours[1]})",
                    notes=f"{motive.title()} actor; {soph} tradecraft.")
        for vendor, alias in aliases.items():
            conn.execute("insert into actor_aliases(actor_id, alias, named_by) values (%s,%s,%s)",
                         (aid, alias, w.source(vendor)))
        # 1-3 historic campaigns; commodity malware appears across many actors
        for _ in range(rng.randint(1, 3)):
            cname = F.op_name(rng)
            while cname in used_ops:
                cname = F.op_name(rng)
            used_ops.add(cname)
            start = now.date() - timedelta(days=rng.randint(250, 900))
            cid = w.ent("campaign", cname, world=True, verdict="malicious", table="campaigns", name=cname,
                        started_on=start, ended_on=start + timedelta(days=rng.randint(20, 120)),
                        objective="credential theft" if motive == "financial" else "access",
                        targeting=rng.choice(["higher education", "credit unions", "retail", "healthcare"]))
            w.edge(cid, aid, "attributed_to", source="Kestrel Threat Intelligence", confidence=2, world=True)
            for fam in rng.sample(list(fam_ids), rng.randint(1, 2)):
                w.edge(fam_ids[fam], cid, "used_in", source="Kestrel Threat Intelligence", confidence=3, world=True)

    # --- people (Directory), organisations, personas, breaches -----------
    people = load_people(people_csv, rng, 400)
    breach_ids = {}
    for bname, bdate, classes, htype in BREACHES:
        breach_ids[bname] = (w.ent("breach", bname, world=True, verdict="unknown", table="breaches",
                                   breach_name=bname, breach_date=bdate, records=rng.randint(80_000, 4_000_000),
                                   data_classes=classes), htype)
    used_names: set[str] = set()
    used_personas: set[str] = set()
    for p in people:
        by = rng.randint(1975, 2004)
        value = p["name"] if p["name"] not in used_names else f"{p['name']} (b. {by})"
        if value in used_names:
            continue
        used_names.add(value)
        pid = w.ent("person", value, label=p["name"], world=True, verdict="unknown", table="persons",
                    full_name=p["name"], city=p["city"], country=p["country"], birth_year=by,
                    employer=p["employer"], job_title=rng.choice(F.JOBS), source_row=p["row"])
        p["entity_id"] = pid
        # most people have a breach footprint; that is what makes the real suspect hard to spot
        email = f"{p['email_local']}@{rng.choice(EMAIL_PROVIDERS)}".lower()
        for bname in rng.sample(list(breach_ids), rng.randint(0, 3)):
            bid, htype = breach_ids[bname]
            conn.execute("""insert into breach_records(breach_id, email, username, display_name,
                            password_hash, hash_type) values (%s,%s,%s,%s,%s,%s)""",
                         (bid, email, p["username"], p["name"],
                          F.fake_password_hash(rng, htype) if htype else None, htype))
        if rng.random() < 0.35:
            h = p["username"]
            platform = rng.choice(F.SOCIAL_PLATFORMS)
            pval = f"{h}@{platform.split()[0]}"
            if pval in used_personas:
                continue
            used_personas.add(pval)
            perid = w.ent("persona", pval, label=h, world=True, table="personas", handle=h,
                          platform=platform, joined_on=now.date() - timedelta(days=rng.randint(100, 3000)),
                          post_count=rng.randint(0, 2000), bio=None, language="en")
            w.edge(perid, pid, "identified_as", source="CrowdReports", confidence=4, world=True)

    conn.execute("analyze")
    from .registry import sync_catalog
    sync_catalog(conn)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=int(os.environ.get("WORLD_SEED", "1337")))
    ap.add_argument("--people-csv", type=Path, default=Path("data/osint_public_profiles_dataset.csv"))
    args = ap.parse_args()
    url = os.environ.get("DATABASE_URL")
    if not url:
        sys.exit("DATABASE_URL is not set (copy .env.example to .env)")
    with psycopg.connect(url, prepare_threshold=None) as conn:
        conn.execute("set search_path = public, extensions")
        conn.execute("""truncate sources, entities, entity_relationships, actor_aliases,
                        breach_records, cases restart identity cascade""")
        seed(conn, random.Random(args.seed), args.people_csv)
        n = conn.execute("select kind, count(*) from entities group by kind order by 2 desc").fetchall()
    print("World seeded:")
    for kind, c in n:
        print(f"  {kind:<18}{c:>6}")


if __name__ == "__main__":
    main()
