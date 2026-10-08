"""make test -> end-to-end check against a running API + the same database.

For every scenario at a couple of difficulties:
  1. generate a case through the API,
  2. assert the SQL oracle says it is solvable,
  3. submit a WRONG report (decoy actor + a red herring) and a RIGHT report
     built from ground truth, and check scoring behaves.
Then:
  4. a bot plays every scenario through /api like the React client does,
     including interviewing the client in the Messenger (on HARD the client
     is a liar, so the bot has to show them proof),
  5. every client personality is checked: misunderstandings cost patience,
     secrets come out by that personality's rule, demanding clients chase you,
     and a client can withdraw the case,
  6. the opt-in study: consent, both surveys, validation, withdrawal.
Ground truth is read from the DB here; the game client never can.
"""
from __future__ import annotations

import http.client
import json
import os
import re
import sys
import urllib.error
import urllib.parse

from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from server.env import load_env  # noqa: E402  (backend/.env -> DATABASE_URL)

load_env()
API = os.environ.get("API_URL", "http://127.0.0.1:8000")
DB = os.environ["DATABASE_URL"]


_conn: http.client.HTTPConnection | None = None
CASE_KEYS: dict[int, str] = {}   # case number -> its X-Case-Key, from POST /api/cases


def call(method, path, body=None):
    """One request over a single keep-alive connection. A full run makes ~25,000
    requests; a new socket each time exhausts Windows' ephemeral ports (WinError 10055).
    Raises urllib.error.HTTPError on 4xx/5xx, like urlopen did."""
    global _conn
    u = urllib.parse.urlsplit(API)
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    case = re.search(r"/api/cases/(\d+)|[?&]case_id=(\d+)", path)
    if case and int(case.group(1) or case.group(2)) in CASE_KEYS:
        headers["X-Case-Key"] = CASE_KEYS[int(case.group(1) or case.group(2))]
    for attempt in range(3):
        if _conn is None:
            _conn = http.client.HTTPConnection(u.hostname, u.port or 80, timeout=120)
        try:
            _conn.request(method, path, body=data, headers=headers)
            r = _conn.getresponse()
            raw = r.read()
            break
        except (http.client.HTTPException, OSError):
            _conn.close()           # the server dropped the idle connection: reconnect
            _conn = None
            if attempt == 2:
                raise
    if r.status >= 400:
        raise urllib.error.HTTPError(API + path, r.status, raw.decode(errors="replace")[:300], r.headers, None)
    out = json.loads(raw)
    if isinstance(out, dict) and out.get("case_key"):
        CASE_KEYS[out["case_id"]] = out["case_key"]
    return out


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

    print("\n  game-client path (bot plays every scenario through /api, starting from the exhibits and the client):")
    for key in scns:
        for diff in ("easy", "hard"):
            ok, msg = play_like_client(db, key, diff, budget=1500 if diff == "hard" else 900,
                                       personality="liar" if diff == "hard" else None)
            fails += not ok
            print(f"    {key:<16} {diff:<6} {'OK  ' if ok else 'FAIL'} {msg}")

    print("\n  client personalities (Messenger):")
    fails += messenger_checks(db)
    print("\n  research study:")
    fails += study_checks(db)

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


INTERVIEW = ["Hi, I'm the analyst assigned to your case.", "What happened?", "When did this happen?",
             "How did they contact you?", "Did you click a link or enter your password anywhere?",
             "Did you pay or send any money? How much?", "Did you download anything or let anyone access your computer?",
             "Who were you talking to?", "Did they give you a phone number to call?",
             "Is there anything you're leaving out? Please be honest.", "Are you sure that's everything?"]
# what a player might show a client to confront them
SHOWABLE = {"domain", "url", "url_scan", "payment_account", "crypto_wallet", "persona", "social_post", "phone",
            "malware_sample", "malware_family", "malware", "sms_message", "email_address"}


def chat(n, text=None, evidence=None):
    body = {"text": text or ""}
    if evidence is not None:
        body["evidence_id"] = evidence
    try:
        return call("POST", f"/api/cases/{n}/messenger", body)
    except urllib.error.HTTPError:
        return {}


def play_like_client(db, scenario: str, difficulty: str, budget: int = 900, personality=None):
    """Breadth-first 'player': only follows actions the client UI offers (card rows, the
    buttons on the original record renderers, records the client hands over in the
    Messenger) plus reading text for names it mentions. A lying client is shown the
    records the bot has found. Then pins the true chain and submits from the report
    form's own options."""
    brief = call("POST", "/api/cases", {"difficulty": difficulty, "scenario": scenario, "personality": personality})
    n = brief["case_id"]
    cid = db.execute("select id from cases where seq=%s", (n,)).fetchone()[0]
    aliases = [r[0] for r in db.execute("select alias::text from actor_aliases union select primary_alias from threat_actors")]
    import heapq
    queue, seen, calls, tick = [], set(), 0, [0]
    found_ids: dict[int, str] = {}      # entity id -> kind, from pin buttons and record ids
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
        if c.get("pin"):
            found_ids[c["pin"]["entity_id"]] = c["pin"]["entity_kind"]
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
            for idk, kind in (("domain_id", "domain"), ("ip_id", "ip"), ("malware_id", "malware_family")):
                if r.get(idk):
                    found_ids[r[idk]] = kind
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

    def take_chat(st):
        for m in (st or {}).get("messages", []):
            for c in m.get("cards") or []:
                take(c)

    def sweep(limit):
        nonlocal calls
        while queue and calls < limit:
            _, _, kind, a, b = heapq.heappop(queue)
            calls += 1
            if kind == "open":
                take(get(APP_ROUTE[a], {"case_id": n, "q": b}))
            else:
                take(get(a, {"case_id": n, **(b or {})}))

    take(call("GET", f"/api/cases/{n}/exhibits"))
    if brief.get("entry_domain"):
        push("open", "intelsearch", brief["entry_domain"])
    for q in INTERVIEW:
        take_chat(chat(n, q))
    sweep(budget // 2)
    # confront the client with what the bot found; stop once they've come clean
    shown = 0
    for eid, kind in list(found_ids.items()):
        if shown >= 60 or not db.execute("""select 1 from case_client_facts where case_id=%s and secret
                                            and revealed_at is null""", (cid,)).fetchone():
            break
        if kind in SHOWABLE:
            take_chat(chat(n, "Can you explain this?", eid))
            shown += 1
    take(call("GET", f"/api/cases/{n}/exhibits"))
    sweep(budget)

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
    status = db.execute("select status from cases where id=%s", (cid,)).fetchone()[0]
    if status != "open":
        return False, f"the client closed the case ({status}) before the bot could submit"
    res = call("POST", f"/api/cases/{n}/submit", {"answers": found})
    if not res["is_correct"]:
        return False, f"submission graded wrong: {res['verdicts']}"
    hidden = [r[0] for r in db.execute("""select e.kind::text from case_entities ce join entities e on e.id=ce.entity_id
                                         where ce.case_id=%s and ce.role in ('initial_clue','chain')
                                           and ce.entity_id not in (select entity_id from case_discoveries where case_id=%s)""",
                                      (cid, cid))]
    told = db.execute("""select count(*) filter (where revealed_at is not null), count(*) from case_client_facts
                         where case_id=%s and secret""", (cid,)).fetchone()
    pers = db.execute("select personality from case_client where case_id=%s", (cid,)).fetchone()[0]
    return True, (f"solved, score {res['score']}, {calls} requests, client {pers} told {told[0]}/{told[1]} secret(s)"
                  + (f", never surfaced: {hidden}" if hidden else ""))


# ------------------------------------------------------------------ Messenger personalities
def messenger_checks(db) -> int:
    fails = 0
    for p in call("GET", "/api/personalities"):
        key, mode = p["key"], p["disclosure"]
        b = call("POST", "/api/cases", {"difficulty": "medium", "scenario": "romance", "personality": key})
        n = b["case_id"]
        cid = db.execute("select id from cases where seq=%s", (n,)).fetchone()[0]
        st0 = call("GET", f"/api/cases/{n}/messenger")
        st1 = chat(n, "zxqv blorf wibble")
        confused_ok = st1["client"]["patience"] < st0["client"]["patience"] and st1["messages"][-1]["from"] == "client"

        def told():
            return db.execute("select revealed_at is not null from case_client_facts where case_id=%s and secret",
                              (cid,)).fetchone()[0]
        chat(n, "Did you send them any money?")
        first = told()
        chat(n, "Did you send them any money? Be honest.")
        second = told()
        if mode == "proof":
            pid = db.execute("select proof[1] from case_client_facts where case_id=%s and secret", (cid,)).fetchone()[0]
            db.execute("insert into case_discoveries(case_id, entity_id, tool) values (%s,%s,'test') on conflict do nothing",
                       (cid, pid))
            chat(n, "Then what is this?", db.execute("select seq from entities where id=%s", (pid,)).fetchone()[0])
        third = told()
        rule = {"upfront": first, "asked": first, "pressed": (not first) and second,
                "proof": (not second) and third}[mode]

        chased = True
        if p["nag_after_s"]:
            before = db.execute("select count(*) from client_messages where case_id=%s", (cid,)).fetchone()[0]
            db.execute("update case_client set last_activity_at = now() - make_interval(secs => %s) where case_id=%s",
                       (p["nag_after_s"] * 2 + 5, cid))
            call("GET", f"/api/cases/{n}/messenger")
            after = db.execute("select count(*) from client_messages where case_id=%s", (cid,)).fetchone()[0]
            chased = after > before
        ok = confused_ok and rule and chased
        fails += not ok
        print(f"    {key:<11} {mode:<8} {'OK  ' if ok else 'FAIL'} misunderstanding costs patience={confused_ok} "
              f"secret by rule={rule} chases={'n/a' if not p['nag_after_s'] else chased}")

    # a client can withdraw the case from MEDIUM up, never on EASY
    for diff, should_fire in (("medium", True), ("easy", False)):
        n = call("POST", "/api/cases", {"difficulty": diff, "scenario": "tech_support", "personality": "rude"})["case_id"]
        for _ in range(12):
            if not chat(n, "zxqv blorf"):
                break
        status = db.execute("select status from cases where seq=%s", (n,)).fetchone()[0]
        ok = (status == "failed") == should_fire
        fails += not ok
        print(f"    withdraw on {diff:<6} {'OK  ' if ok else 'FAIL'} status after 12 unclear messages: {status}")

    # pinning a red herring the client recognizes makes them push back
    n = call("POST", "/api/cases", {"difficulty": "hard", "scenario": "romance", "personality": "anxious"})["case_id"]
    cid = db.execute("select id from cases where seq=%s", (n,)).fetchone()[0]
    rh = db.execute("""select ce.entity_id from case_entities ce join entities e on e.id=ce.entity_id
                       where ce.case_id=%s and ce.role='red_herring' and e.kind='persona' limit 1""", (cid,)).fetchone()
    if rh:
        db.execute("insert into case_discoveries(case_id, entity_id, tool) values (%s,%s,'test') on conflict do nothing",
                   (cid, rh[0]))
        seq = db.execute("select seq from entities where id=%s", (rh[0],)).fetchone()[0]
        call("POST", f"/api/cases/{n}/evidence", {"entity_kind": "persona", "entity_id": seq})
        last = call("GET", f"/api/cases/{n}/messenger")["messages"][-1]
        ok = last["from"] == "client"
        fails += not ok
        print(f"    wrong pin   {'OK  ' if ok else 'FAIL'} client said: {last['text'][:70]}")
    return fails


# ------------------------------------------------------------------ research study
def study_checks(db) -> int:
    fails = 0

    def answers_for(phase):
        out = {}
        for q in call("GET", f"/api/study/questions?phase={phase}")["questions"]:
            k, o = q["kind"], q["options"]
            out[q["key"]] = {"number": lambda: o["min"], "likert": lambda: 4, "choice": lambda: o[0]["value"],
                             "multi": lambda: [o[0]["value"]], "text": lambda: "Test", "longtext": lambda: "Test"}[k]()
        return out

    pid = call("POST", "/api/study/participants", {"consent": True, "adult": True})["participant_id"]
    pre = answers_for("pre")
    bad = dict(pre, age=12)
    try:
        call("POST", f"/api/study/participants/{pid}/answers", {"phase": "pre", "answers": bad})
        rejected = False
    except urllib.error.HTTPError as e:
        rejected = e.code == 422
    call("POST", f"/api/study/participants/{pid}/answers", {"phase": "pre", "answers": pre})
    n = call("POST", "/api/cases", {"difficulty": "easy", "participant_id": pid})["case_id"]
    linked = str(db.execute("select participant_id from cases where seq=%s", (n,)).fetchone()[0]) == pid
    post = call("POST", f"/api/study/participants/{pid}/answers", {"phase": "post", "answers": answers_for("post")})
    st = call("GET", f"/api/study/participants/{pid}")
    call("DELETE", f"/api/study/participants/{pid}")
    try:
        call("GET", f"/api/study/participants/{pid}")
        gone = False
    except urllib.error.HTTPError as e:
        gone = e.code == 404
    try:
        call("POST", "/api/study/participants", {"consent": True, "adult": False})
        needs_adult = False
    except urllib.error.HTTPError as e:
        needs_adult = e.code == 400
    ok = rejected and linked and st["pre_done"] and st["post_done"] and "quiz" in post and gone and needs_adult
    fails += not ok
    print(f"    study       {'OK  ' if ok else 'FAIL'} validation={rejected} case linked={linked} "
          f"surveys done={st['pre_done'] and st['post_done']} quiz={post.get('quiz')} withdraw deletes={gone} "
          f"adults only={needs_adult}")
    return fails


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
