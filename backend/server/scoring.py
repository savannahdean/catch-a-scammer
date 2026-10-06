"""Grade a Case Report against the scenario's declared answer slots.

Being right is not enough: the cited evidence must form a connected,
time-valid chain from the initial clue to each conclusion (recursive CTE in
SQL), and citing red herrings / false-flag items costs points.
"""
from __future__ import annotations

from uuid import UUID

KIND_ALIASES = {"threat_actor": "threat_actor"}


def resolve(conn, case_id: UUID, kind: str, value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        eid = UUID(str(value))
        row = conn.execute("select id from entities where id=%s and kind=%s and (case_id is null or case_id=%s)",
                           (eid, kind, case_id)).fetchone()
        return row["id"] if row else None
    except ValueError:
        pass
    if kind == "threat_actor":
        row = conn.execute("""select actor_id as id from actor_aliases where alias=%s
                              union select id from entities where kind='threat_actor' and value=%s limit 1""",
                           (value, value)).fetchone()
        return row["id"] if row else None
    rows = conn.execute("""select id from entities where kind=%s and (value=%s or label=%s)
                           and (case_id is null or case_id=%s)""", (kind, value, value, case_id)).fetchall()
    return rows[0]["id"] if len(rows) == 1 else None


def grade(conn, case: dict, answer: dict, evidence: list[UUID]) -> dict:
    cid = case["id"]
    truth = conn.execute("select answer_slots, resolution_text from case_ground_truth where case_id=%s", (cid,)).fetchone()
    prof = conn.execute("select * from difficulty_profiles where level=%s", (case["difficulty"],)).fetchone()
    slots = truth["answer_slots"]

    fields, expected, picked, weights = {}, {}, {}, {}
    for key, spec in slots.items():
        expected[key] = UUID(spec["entity_id"])
        weights[key] = float(spec.get("weight") or 0)
        picked[key] = resolve(conn, cid, spec["kind"], answer.get(key))
        fields[key] = picked[key] is not None and picked[key] == expected[key]
    total_w = sum(weights.values()) or 1.0
    correct = all(fields.values())
    base = prof["base_score"]
    points = sum(base * weights[k] / total_w for k, ok in fields.items() if ok)

    ev = list(dict.fromkeys(evidence))
    reach = {r["entity_id"] for r in conn.execute(
        "select entity_id from reachable_evidence(%s, %s::uuid[])", (cid, ev)).fetchall()}
    unsupported = [k for k, ok in fields.items() if ok and expected[k] not in reach]
    points -= base * 0.10 * len(unsupported)

    roles = {r["entity_id"]: r["role"] for r in conn.execute(
        "select entity_id, role from case_entities where case_id=%s and entity_id = any(%s::uuid[])", (cid, ev)).fetchall()}
    bad = [e for e in ev if roles.get(e) in ("red_herring", "false_flag")]
    points -= base * 0.05 * min(len(bad), 6)
    orphan = [e for e in ev if e not in reach]

    points -= base * 0.15 * case["attempts"]
    hint_cost = conn.execute("select coalesce(sum(cost),0) s from case_hints where case_id=%s and step <= %s",
                             (cid, case["hints_used"])).fetchone()["s"]
    points -= hint_cost
    score = max(0, round(points))

    return {"correct": correct, "score": score, "fields": fields,
            "unsupported_conclusions": unsupported, "misleading_evidence": [str(e) for e in bad],
            "disconnected_evidence": [str(e) for e in orphan], "hint_penalty": int(hint_cost),
            "attempt_penalty_pct": 15 * case["attempts"]}
