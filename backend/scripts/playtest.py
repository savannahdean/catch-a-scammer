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

    print("\n" + ("FAILED" if fails else "ALL CHECKS PASSED"))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 2)
