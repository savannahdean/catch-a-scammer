"""Opt-in research study: consent, the pre-game and post-game surveys.

Questions live in survey_questions (migration 008), so the client renders
whatever is there. Answers are validated against each question's kind and
options. Quiz answer keys (survey_questions.correct) never leave the server;
after the post-game survey the player sees only their own before/after score.

A participant can withdraw at any time: DELETE removes the participant and
every answer (cascade); their cases stay, unlinked (participant_id -> null).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from .db import tx
from .guard import STUDY_ENABLED, rate_limit

router = APIRouter(prefix="/api/study")

CONSENT_VERSION = "2026-10-v1"
CONSENT_TEXT = (
    "Catch-a-Scammer is a class project for a Database Management Systems course. If you take part, we store your "
    "survey answers and what you do in the game (searches, messages to the client, your case report) in the "
    "project database, linked to a random ID rather than your name. Everything in the game is fictional.\n\n"
    "Taking part is optional and does not change the game. You must be 18 or older. You can skip any question that "
    "is marked optional, stop at any time, and withdraw from the Start menu, which deletes your survey answers.\n\n"
    "We use the results only to see what players learn about open-source intelligence (OSINT) and to improve the game."
)


def _participant(conn, pid: UUID) -> dict:
    row = conn.execute("select * from study_participants where id=%s", (pid,)).fetchone()
    if not row:
        raise HTTPException(404, "unknown participant")
    return row


@router.get("/config")
def config():
    """Whether the study is taking new participants (STUDY_ENABLED in the environment)."""
    return {"enabled": STUDY_ENABLED}


def _require_open() -> None:
    if not STUDY_ENABLED:
        raise HTTPException(403, "The research study is closed.")


@router.get("/consent")
def consent():
    return {"version": CONSENT_VERSION, "text": CONSENT_TEXT}


class Join(BaseModel):
    consent: bool
    adult: bool
    consent_version: str = CONSENT_VERSION
    user_agent: Optional[str] = None


@router.post("/participants", dependencies=[Depends(rate_limit("join_study", "10/3600"))])
def join(body: Join):
    _require_open()
    if not (body.consent and body.adult):
        raise HTTPException(400, "consent and age confirmation are required to join the study")
    with tx() as conn:
        row = conn.execute("insert into study_participants(consent_version, user_agent) values (%s,%s) returning id",
                           (body.consent_version, (body.user_agent or "")[:300])).fetchone()
    return {"participant_id": str(row["id"])}


@router.get("/participants/{pid}")
def status(pid: UUID):
    with tx() as conn:
        p = _participant(conn, pid)
        cases = conn.execute("select count(*) n, count(*) filter (where status <> 'open') closed from cases "
                             "where participant_id=%s", (pid,)).fetchone()
    return {"participant_id": str(pid), "pre_done": p["pre_done_at"] is not None,
            "post_done": p["post_done_at"] is not None, "cases_played": cases["n"], "cases_closed": cases["closed"]}


@router.delete("/participants/{pid}")
def withdraw(pid: UUID):
    with tx() as conn:
        conn.execute("delete from study_participants where id=%s", (pid,))
    return {"ok": True}


@router.get("/questions")
def questions(phase: str):
    if phase not in ("pre", "post"):
        raise HTTPException(400, "phase is 'pre' or 'post'")
    with tx() as conn:
        rows = conn.execute("""select key, section, prompt, kind, options, required, show_if from survey_questions
                               where phase=%s order by ord, key""", (phase,)).fetchall()
    return {"phase": phase, "questions": rows}


class Answers(BaseModel):
    phase: str
    answers: dict[str, Any]


def _visible(q: dict, answers: dict) -> bool:
    cond = q["show_if"]
    if not cond:
        return True
    return all(str(answers.get(k)) in [str(v) for v in vals] for k, vals in cond.items())


def _check(q: dict, value: Any) -> Any:
    """Validate one answer against its question. Returns the value to store."""
    kind, opts = q["kind"], q["options"] or {}
    label = q["prompt"]
    if kind == "number":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise HTTPException(422, f"'{label}' needs a whole number")
        if not (opts.get("min", -10**9) <= v <= opts.get("max", 10**9)):
            raise HTTPException(422, f"'{label}' must be between {opts.get('min')} and {opts.get('max')}")
        return v
    if kind == "likert":
        try:
            v = int(value)
        except (TypeError, ValueError):
            raise HTTPException(422, f"'{label}' needs a rating")
        if not (opts["min"] <= v <= opts["max"]):
            raise HTTPException(422, f"'{label}' is out of range")
        return v
    if kind == "choice":
        allowed = {o["value"] for o in opts}
        if value not in allowed:
            raise HTTPException(422, f"'{label}' needs one of the listed answers")
        return value
    if kind == "multi":
        allowed = {o["value"] for o in opts}
        vals = value if isinstance(value, list) else [value]
        if any(v not in allowed for v in vals):
            raise HTTPException(422, f"'{label}' has an answer that isn't listed")
        return list(dict.fromkeys(vals))
    text = str(value).strip()
    if len(text) > 2000:
        raise HTTPException(422, f"'{label}' is too long (2000 characters max)")
    return text


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == []


@router.post("/participants/{pid}/answers", dependencies=[Depends(rate_limit("answers", "20/3600"))])
def answer(pid: UUID, body: Answers):
    _require_open()
    if body.phase not in ("pre", "post"):
        raise HTTPException(400, "phase is 'pre' or 'post'")
    with tx() as conn:
        p = _participant(conn, pid)
        if body.phase == "pre" and p["pre_done_at"]:
            raise HTTPException(409, "the pre-game survey is already done")
        if body.phase == "post" and p["post_done_at"]:
            raise HTTPException(409, "the post-game survey is already done")
        qs = conn.execute("select * from survey_questions where phase=%s order by ord", (body.phase,)).fetchall()
        known = {q["key"] for q in qs}
        unknown = set(body.answers) - known
        if unknown:
            raise HTTPException(422, f"unknown question(s): {sorted(unknown)}")
        rows = []
        for q in qs:
            if not _visible(q, body.answers):
                continue
            v = body.answers.get(q["key"])
            if _empty(v):
                if q["required"]:
                    raise HTTPException(422, f"Please answer: {q['prompt']}")
                continue
            rows.append((pid, q["key"], Jsonb(_check(q, v))))
        for r in rows:
            conn.execute("""insert into survey_answers(participant_id, question_key, answer) values (%s,%s,%s)
                            on conflict (participant_id, question_key) do update set answer=excluded.answer,
                            answered_at=now()""", r)
        col = "pre_done_at" if body.phase == "pre" else "post_done_at"
        conn.execute(f"update study_participants set {col}=%s where id=%s", (datetime.now(timezone.utc), pid))
        out: dict[str, Any] = {"ok": True}
        if body.phase == "post":
            score = conn.execute("""select sum(pre_value) pre, sum(post_value) post, count(*) n from v_study_learning
                                    where participant_id=%s and measure like 'quiz%%'""", (pid,)).fetchone()
            out["quiz"] = {"before": int(score["pre"] or 0), "after": int(score["post"] or 0), "total": int(score["n"] or 0)}
    return out
