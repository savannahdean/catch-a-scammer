"""Scenario registry: maps a scenario key to its class, syncs the `scenarios`
catalog table, and dispatches case generation."""
from __future__ import annotations

import json
import random
from uuid import UUID

import psycopg

from .base import Profile, Scenario
from .scenarios import phishing, social

SCENARIOS: dict[str, type[Scenario]] = {
    cls.key: cls
    for cls in (
        phishing.CredentialPhish, phishing.SpearPhish, phishing.Whaling, phishing.ClonePhish,
        phishing.AnglerPhish, phishing.Smishing, phishing.Vishing,
        social.Romance, social.AdvanceFee, social.TechSupport, social.PigButchering,
    )
}

# alias so old calls / saved cases keep working
SCENARIOS["credential_phish"] = phishing.CredentialPhish

DIFFICULTY_ORDER = ["easy", "medium", "hard", "expert"]


def sync_catalog(conn: psycopg.Connection) -> None:
    """Write each scenario's metadata into the `scenarios` table so the client
    can list what's available and build the Case Report form from report_fields."""
    for key, cls in SCENARIOS.items():
        if key == "credential_phish":
            continue
        fields = [{"key": k, "label": label, "kind": kind} for k, label, kind in cls.report_fields]
        if not any(f["key"] == "person" for f in fields):
            fields.append({"key": "person", "label": "Real person operating the scheme (hard+)", "kind": "person"})
        conn.execute(
            """insert into scenarios(key, title, category, real_world_basis, player_skill, report_fields)
               values (%s,%s,%s,%s,%s,%s)
               on conflict (key) do update set title=excluded.title, category=excluded.category,
                 real_world_basis=excluded.real_world_basis, player_skill=excluded.player_skill,
                 report_fields=excluded.report_fields""",
            (cls.key, cls.title, cls.category, cls.real_world_basis, cls.player_skill, json.dumps(fields)),
        )


def profile_for(conn: psycopg.Connection, difficulty: str) -> Profile:
    row = conn.execute("select * from difficulty_profiles where level=%s", (difficulty,)).fetchone()
    if not row:
        raise ValueError(f"unknown difficulty {difficulty}")
    return Profile(*row)


def generate_case(conn: psycopg.Connection, difficulty: str, seed: int | None = None,
                  scenario: str = "random") -> UUID:
    if seed is None:
        seed = random.SystemRandom().randrange(2**31)
    if scenario == "random":
        pool = [k for k in SCENARIOS if k != "credential_phish"]
        scenario = random.Random(seed).choice(pool)
    cls = SCENARIOS.get(scenario)
    if not cls:
        raise ValueError(f"unknown scenario '{scenario}'. known: {sorted(k for k in SCENARIOS if k!='credential_phish')}")
    return cls(conn, profile_for(conn, difficulty), seed).run()
