"""make test -> end-to-end check against a running API + the same database.

For every scenario at a couple of difficulties:
  1. generate a case through the API,
  2. assert the SQL oracle says it is solvable,
  3. submit a WRONG report (decoy actor + a red herring) and a RIGHT report
     built from ground truth, and check scoring behaves.
Also exercises the new tool endpoints. Ground truth is read from the DB here;
the game client never can.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

import psycopg

API = os.environ.get("API_URL", "http://127.0.0.1:8000")
DB = os.environ["DATABASE_URL"]


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())


def main(seeds: int = 2) -> None:
    db = psycopg.connect(DB, prepare_threshold=None, autocommit=True)
    scns = [s["key"] for s in call("GET", "/scenarios")]
    print(f"{len(scns)} scenarios: {', '.join(scns)}\n")
    fails = 0

    for key in scns:
        line = f"  {key:<16}"
        for diff in ("easy", "expert"):
            for seed in range(seeds):
                c = call("POST", "/cases", {"difficulty": diff, "seed": seed * 17 + 1, "scenario": key})
                cid = c["case_id"]
                solvable = db.execute("select case_is_solvable(%s)", (cid,)).fetchone()[0]
                slots = db.execute("select answer_slots from case_ground_truth where case_id=%s", (cid,)).fetchone()[0]
                answer = {k: str(v["entity_id"]) for k, v in slots.items()}
                chain = [str(r[0]) for r in db.execute(
                    "select entity_id from case_entities where case_id=%s and role in ('initial_clue','chain')", (cid,))]
                right = call("POST", f"/cases/{cid}/submit", {**answer, "evidence": chain})

                c2 = call("POST", "/cases", {"difficulty": diff, "seed": seed * 17 + 1, "scenario": key})
                cid2 = c2["case_id"]
                slots2 = db.execute("select answer_slots from case_ground_truth where case_id=%s", (cid2,)).fetchone()[0]
                decoy = db.execute("""select ce.entity_id from case_entities ce where ce.case_id=%s and ce.role='false_flag'
                                      and ce.entity_id in (select entity_id from threat_actors) limit 1""", (cid2,)).fetchone()
                bad = {k: str(v["entity_id"]) for k, v in slots2.items()}
                if decoy and "actor" in bad:
                    bad["actor"] = str(decoy[0])
                herring = db.execute("select entity_id from case_entities where case_id=%s and role='red_herring' limit 2", (cid2,)).fetchall()
                wrong = call("POST", f"/cases/{cid2}/submit", {**bad, "evidence": [str(h[0]) for h in herring]})

                ok = solvable and right["correct"] and (not wrong["correct"] if decoy else True)
                fails += not ok
                if not ok:
                    line += f" [{diff}/{seed} solv={solvable} right={right['correct']} wrong={wrong['correct']}]"
        print(line + ("  OK" if "[" not in line else "  <-- FAIL"))

    print("\n  tool coverage:")
    rc = call("POST", "/cases", {"difficulty": "hard", "scenario": "romance", "seed": 5})["case_id"]
    img = db.execute("select e.value::text from entities e join images i on i.entity_id=e.id where e.case_id=%s limit 1", (rc,)).fetchone()[0]
    print("    reverse_image:", len(call("GET", f"/cases/{rc}/reverse_image?q={img.split(':')[1]}")), "sightings")
    pay = db.execute("select entity_id from case_entities where case_id=%s and entity_id in (select entity_id from payment_accounts) limit 1", (rc,)).fetchone()[0]
    print("    money_trail  :", len(call("GET", f"/cases/{rc}/money_trail?start={pay}")), "hops")

    vc = call("POST", "/cases", {"difficulty": "hard", "scenario": "vishing", "seed": 5})["case_id"]
    au = call("GET", f"/cases/{vc}/audio?q=urgent")
    print("    audio        :", len(au), "recordings; synthetic scores:",
          [round(a["synthetic_score"], 2) for a in au if a.get("synthetic_score") is not None])
    af = call("POST", "/cases", {"difficulty": "easy", "scenario": "advance_fee", "seed": 5})["case_id"]
    docs = call("GET", f"/cases/{af}/document?q=Certificate")
    print("    document     :", len(docs), "docs; first author:", docs[0]["meta_author"] if docs else "-")

    print("\n  desktop-client path (bot plays every scenario through /api, starting from the exhibits):")
    for key in scns:
        for diff in ("easy", "hard"):
            ok, msg = play_like_client(db, key, diff, budget=1500 if diff == "hard" else 900)
            fails += not ok
            print(f"    {key:<16} {diff:<6} {'OK  ' if ok else 'FAIL'} {msg}")

    print("\n" + ("FAILED" if fails else "ALL CHECKS PASSED"))
    sys.exit(1 if fails else 0)


# ------------------------------------------------------------------ desktop-client path
# Which /api route each client app searches. Mirrors client/src/apps/*.
APP_ROUTE = {"intelsearch": "/api/intel", "malwaredb": "/api/malware", "websearch": "/api/websearch",
             "directory": "/api/directory", "social": "/api/social", "reverseimage": "/api/reverseimage",
             "phone": "/api/phone", "sms": "/api/sms", "doclab": "/api/documents", "audiolab": "/api/audio",
             "payments": "/api/payments", "moneytrail": "/api/moneytrail", "complaints": "/api/complaints",
             "dns": "/api/dns", "whois": "/api/whois", "certs": "/api/certs", "urlscan": "/api/urlscan",
             "breach": "/api/breach"}


def get(path, params):
    q = urllib.parse.urlencode(params)
    try:
        return call("GET", f"{path}?{q}")
    except urllib.error.HTTPError as e:
        if e.code in (404, 409, 422):
            return {}
        raise


def play_like_client(db, scenario: str, difficulty: str, budget: int = 900):
    """Breadth-first 'player': only follows actions the client UI offers (card rows, the
    buttons on the original record renderers) plus reading text for names it mentions.
    Then pins the true chain and submits from the report form's own options."""
    brief = call("POST", "/api/cases", {"difficulty": difficulty, "scenario": scenario})
    n = brief["case_id"]
    cid = db.execute("select id from cases where seq=%s", (n,)).fetchone()[0]
    aliases = [r[0] for r in db.execute("select alias::text from actor_aliases union select primary_alias from threat_actors")]
    import heapq
    queue, seen, calls, tick = [], set(), 0, [0]

    def push(kind, a, b=None, prio=0):
        """prio 0: a pivot a card offers (what a person clicks first); 1: fan-out lists."""
        k = (kind, a, json.dumps(b, sort_keys=True) if b else "")
        if k not in seen:
            seen.add(k)
            tick[0] += 1
            heapq.heappush(queue, (prio, tick[0], kind, a, b))

    def read(text):
        for al in aliases:
            if al and al.lower() in (text or "").lower():
                push("open", "directory", al)

    def take_card(c):
        if not c:
            return
        for b in c.get("blocks", []):
            if b.get("type") in ("text", "mono"):
                read(b.get("text"))
            for r in b.get("rows", []) or []:
                if "open" in r:
                    push("open", r["open"]["app"], r["open"]["query"])
                elif "fetch" in r:
                    push("fetch", r["fetch"]["path"], r["fetch"].get("params") or {})

    def take(res):
        if not isinstance(res, dict):
            return
        if "card" in res:
            take_card(res)
        for c in res.get("cards", []) or []:
            take_card(c)
        recs = []
        for key in ("domains", "ips", "malware", "campaigns", "actors", "persons", "articles"):
            recs += [(key, r) for r in res.get(key, []) or []]
        if res.get("kind"):
            recs.append((res["kind"] + "s" if res["kind"] != "malware" else "malware", res))
        for key, r in recs:
            if key == "domains":
                for ip in r.get("associated_ips", []):
                    push("fetch", f"/api/intel/ip/{ip['ip_id']}", {}, 1)
                for m in r.get("delivers_malware", []):
                    push("open", "malwaredb", m["family_name"])
                for app in ("dns", "whois", "certs", "urlscan"):
                    push("open", app, r["domain_name"], 1)
                push("open", "websearch", r["domain_name"])   # analysts search the domain early
            elif key == "ips":
                for d in r.get("related_domains", []):
                    push("fetch", f"/api/intel/domain/{d['domain_id']}", {}, 2)
                for m in r.get("related_malware", []):
                    push("open", "malwaredb", m["family_name"])
                push("open", "dns", r["ip_address"])
                push("open", "urlscan", r["ip_address"])
            elif key == "malware":
                for c in r.get("campaigns", []):
                    push("open", "websearch", c["name"])
                for i in r.get("infrastructure", []):
                    push("open", "intelsearch", i["ip_address"])
            elif key == "campaigns":
                for a in r.get("actors", []):
                    push("open", "directory", a["alias"])
            elif key == "actors":
                for c in r.get("campaigns", []):
                    push("open", "websearch", c["name"])
                read(r.get("notes"))
            elif key == "persons":
                pass
            elif key == "articles":
                read(r.get("body"))
                read(r.get("title"))

    take(call("GET", f"/api/cases/{n}/exhibits"))
    if brief.get("entry_domain"):
        push("open", "intelsearch", brief["entry_domain"])
    while queue and calls < budget:
        _, _, kind, a, b = heapq.heappop(queue)
        calls += 1
        if kind == "open":
            take(get(APP_ROUTE[a], {"case_id": n, "q": b}))
        else:
            take(get(a, {"case_id": n, **(b or {})}))

    slots = db.execute("select answer_slots from case_ground_truth where case_id=%s", (cid,)).fetchone()[0]
    opts = call("GET", f"/api/cases/{n}/report-options")["fields"]
    found = {}
    for f in opts:
        want = slots[f["key"]]["entity_id"]
        for o in f["options"]:
            if str(db.execute("select id from entities where seq=%s", (o["entity_id"],)).fetchone()[0]) == want:
                found[f["key"]] = o["entity_id"]
    missing = [k for k in slots if k not in found]
    if missing:
        return False, f"not discoverable through the client: {missing} ({calls} requests)"

    chain = [r[0] for r in db.execute("""select entity_id from case_entities where case_id=%s
                                         and role in ('initial_clue','chain')""", (cid,))] + [__import__('uuid').UUID(v['entity_id']) for v in slots.values()]
    unpinnable = 0
    for eid in chain:
        seq = db.execute("""select seq from entities where id=%s""", (eid,)).fetchone()
        try:
            call("POST", f"/api/cases/{n}/evidence", {"entity_kind": "", "entity_id": seq[0] if seq else -1})
        except urllib.error.HTTPError:
            unpinnable += 1
    res = call("POST", f"/api/cases/{n}/submit", {"answers": found})
    if not res["is_correct"]:
        return False, f"submission graded wrong: {res['verdicts']}"
    hidden = [r[0] for r in db.execute("""select e.kind::text from case_entities ce join entities e on e.id=ce.entity_id
                                         where ce.case_id=%s and ce.role in ('initial_clue','chain')
                                           and ce.entity_id not in (select entity_id from case_discoveries where case_id=%s)""",
                                      (cid, cid))]
    return True, f"solved, score {res['score']}, {calls} requests" + (f", never surfaced: {hidden}" if hidden else "")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
