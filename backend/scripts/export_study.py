"""Export the research study's data as CSV files (opted-in players only).

    python scripts/export_study.py                 # -> exports/study-<date>/ and a .zip of it
    python scripts/export_study.py --out somewhere

Only players who joined the study are exported. Everyone else's games stay out,
and a participant who withdrew is already gone (their survey answers are
deleted, and their cases no longer point at them). Participants are random IDs;
the study never asks for a name or an email.

Open the CSVs in Excel, Google Sheets, R or pandas. Each file is described in
the README.txt written next to them.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

import psycopg

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from server.env import load_env  # noqa: E402  (backend/.env -> DATABASE_URL)

# cases a participant played, as a reusable filter
STUDY_CASES = "select id, participant_id, case_code from cases where participant_id is not null"

FILES: list[tuple[str, str, str]] = [
    ("participants.csv",
     "One row per participant: when they consented and finished each survey, their background answers, quiz score "
     "before and after (number of quiz questions right), and how their cases went.",
     """select participant_id, consented_at, pre_done_at, post_done_at, age, college_status, major, tech_background,
               quiz_pre, quiz_post, cases_played, cases_solved, cases_lost_client, avg_score
        from v_study_participants order by consented_at"""),
    ("answers_long.csv",
     "Every survey answer, one per row. is_correct is 1/0 for quiz questions and empty otherwise. Multiple-choice "
     "answers with several picks are joined with '; '.",
     """select a.participant_id, q.phase, q.section, q.key as question_key, q.prompt,
               case when jsonb_typeof(a.answer) = 'array'
                    then (select string_agg(x, '; ') from jsonb_array_elements_text(a.answer) x)
                    else a.answer #>> '{}' end as answer,
               case when q.correct is null then null else (a.answer #>> '{}' = q.correct)::int end as is_correct,
               a.answered_at
        from survey_answers a join survey_questions q on q.key = a.question_key
        order by a.participant_id, q.phase desc, q.ord"""),
    ("learning.csv",
     "Before vs after on every paired measure (the quiz items score 1/0, the confidence items keep their 1-5 "
     "value). One row per participant per measure.",
     "select participant_id, measure, pre_value, post_value from v_study_learning order by participant_id, measure"),
    ("cases.csv",
     "Every case a participant played: scam type, difficulty, the client's personality, outcome, report attempts, "
     "hints, score, and how long it took.",
     f"""select c.participant_id, c.case_code, c.scenario, c.difficulty, cc.personality, c.status, c.attempts,
                c.hints_used, c.score, c.created_at, c.closed_at,
                round(extract(epoch from (coalesce(c.closed_at, now()) - c.created_at)) / 60.0, 1) as minutes
         from cases c left join case_client cc on cc.case_id = c.id
         where c.id in (select id from ({STUDY_CASES}) s) order by c.participant_id, c.created_at"""),
    ("searches.csv",
     "Every search a participant ran in a tool, in order. hit_roles says what kind of record the search found "
     "(chain = a real clue, noise/false_flag = a decoy), which shows whether they were on the right track.",
     f"""select s.participant_id, s.case_code, q.at, q.tool, q.query, q.result_count,
                array_to_string(q.hit_roles, '; ') as hit_roles
         from query_log q join ({STUDY_CASES}) s on s.id = q.case_id order by s.participant_id, q.at"""),
    ("messages.csv",
     "The Messenger conversation with the client, every message in order. intents is what the game understood "
     "from a player message (empty = not understood); patience is the client's mood meter afterwards.",
     f"""select s.participant_id, s.case_code, m.created_at, m.sender, m.body, array_to_string(m.intents, '; ') intents,
                m.evidence_id is not null as showed_evidence, m.patience
         from client_messages m join ({STUDY_CASES}) s on s.id = m.case_id order by s.participant_id, m.id"""),
    ("evidence.csv",
     "What each participant pinned to their evidence board, and what it really was in the case: initial_clue or "
     "chain (a real link), noise or false_flag (a red herring), or empty (not part of the case at all).",
     f"""select s.participant_id, s.case_code, ev.added_at, e.kind, coalesce(e.label, e.value::text) as record,
                (select string_agg(distinct ce.role::text, '; ') from case_entities ce
                  where ce.case_id = ev.case_id and ce.entity_id = ev.entity_id) as role_in_case
         from case_evidence ev join entities e on e.id = ev.entity_id join ({STUDY_CASES}) s on s.id = ev.case_id
         order by s.participant_id, ev.added_at"""),
    ("submissions.csv",
     "Every Case Report a participant submitted: right or wrong, the score, and the per-field breakdown (JSON).",
     f"""select s.participant_id, s.case_code, r.submitted_at, r.correct, r.score, r.breakdown::text as breakdown
         from submissions r join ({STUDY_CASES}) s on s.id = r.case_id order by s.participant_id, r.submitted_at"""),
    ("messenger.csv",
     "One row per case: how the participant worked the client (messages sent, not understood, evidence shown, "
     "secrets uncovered, final patience, whether the client gave up on them).",
     f"""select s.participant_id, v.case_code, v.scenario, v.difficulty, v.personality, v.status, v.final_patience,
                v.max_patience, v.client_fired, v.nags, v.player_messages, v.not_understood, v.evidence_shown,
                v.secrets, v.secrets_uncovered
         from v_messenger_stats v join ({STUDY_CASES}) s on s.id = v.case_id order by s.participant_id"""),
]


def cell(v):
    if isinstance(v, datetime):
        return v.isoformat(timespec="seconds")
    if isinstance(v, (dict, list)):
        return json.dumps(v)
    return v


def write(conn, path: Path, sql: str) -> int:
    cur = conn.execute(sql)
    cols = [d.name for d in cur.description]
    rows = cur.fetchall()
    with path.open("w", newline="", encoding="utf-8-sig") as f:   # BOM: Excel opens it as UTF-8
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows([[cell(v) for v in r] for r in rows])
    return len(rows)


def answers_wide(conn, path: Path) -> int:
    """One row per participant, one column per question (in survey order)."""
    keys = [r[0] for r in conn.execute("select key from survey_questions order by phase desc, ord")]
    rows = conn.execute("""select participant_id, question_key,
                                  case when jsonb_typeof(answer) = 'array'
                                       then (select string_agg(x, '; ') from jsonb_array_elements_text(answer) x)
                                       else answer #>> '{}' end
                           from survey_answers""").fetchall()
    by: dict[str, dict[str, str]] = {}
    for pid, key, val in rows:
        by.setdefault(str(pid), {})[key] = val
    order = [str(r[0]) for r in conn.execute("select id from study_participants order by consented_at")]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["participant_id", *keys])
        for pid in order:
            w.writerow([pid, *[by.get(pid, {}).get(k, "") for k in keys]])
    return len(order)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=Path("exports") / f"study-{datetime.now():%Y-%m-%d-%H%M}")
    args = ap.parse_args()
    load_env()
    url = os.environ.get("DATABASE_URL") or sys.exit("DATABASE_URL is not set (copy .env.example to .env)")
    out: Path = args.out
    out.mkdir(parents=True, exist_ok=True)

    readme = [f"Catch-a-Scammer study export, {datetime.now():%Y-%m-%d %H:%M}", "",
              "Only players who opted into the study are included. participant_id is a random ID that links the",
              "files together; the study never collects names or emails.", ""]
    with psycopg.connect(url, prepare_threshold=None) as conn:
        conn.execute("set search_path = public, extensions")
        for name, about, sql in FILES:
            n = write(conn, out / name, sql)
            readme += [f"{name}  ({n} rows)", f"    {about}", ""]
            print(f"  {name:<18}{n:>7} rows")
            if name == "answers_long.csv":
                n = answers_wide(conn, out / "answers_wide.csv")
                readme += [f"answers_wide.csv  ({n} rows)",
                           "    The same answers, one row per participant and one column per question key.", ""]
                print(f"  {'answers_wide.csv':<18}{n:>7} rows")
        qs = conn.execute("select key, phase, prompt, correct from survey_questions order by phase desc, ord").fetchall()
    readme += ["Question keys:"] + [f"  {k:<22}{p:<5} {t}" + (f"  [answer: {c}]" if c else "") for k, p, t, c in qs]
    (out / "README.txt").write_text("\n".join(readme) + "\n", encoding="utf-8")
    archive = shutil.make_archive(str(out), "zip", root_dir=out)
    print(f"\nWrote {out}/ and {archive}")


if __name__ == "__main__":
    main()
