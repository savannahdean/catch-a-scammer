"""Small helper so generator code reads like the investigation it builds."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID

import psycopg
from psycopg.types.json import Jsonb
from psycopg.types.range import Range


class Writer:
    def __init__(self, conn: psycopg.Connection, case_id: Optional[UUID] = None):
        self.conn = conn
        self.case_id = case_id
        self._sources: dict[str, int] = {}

    # -- sources --------------------------------------------------------
    def source(self, name: str) -> int:
        if not self._sources:
            for sid, sname in self.conn.execute("select id, name from sources"):
                self._sources[sname] = sid
        return self._sources.get(name)

    # -- entities -------------------------------------------------------
    def ent(self, kind: str, value: str, *, label: str | None = None,
            verdict: str = "unknown", world: bool = False, tags: list[str] | None = None,
            **subtype: Any) -> UUID:
        """Insert supertype row + (optional) subtype row. Returns entity id.

        Pass the subtype table via `table=` and its columns as kwargs.
        """
        table = subtype.pop("table", None)
        case_id = None if world else self.case_id
        row = self.conn.execute(
            "insert into entities(kind, value, label, verdict, case_id, tags) "
            "values (%s,%s,%s,%s,%s,%s) returning id",
            (kind, value, label or value, verdict, case_id, tags or []),
        ).fetchone()
        eid = row[0]
        if table:
            cols = ["entity_id"] + list(subtype.keys())
            vals = [eid] + [Jsonb(v) if isinstance(v, (dict, list)) and k in JSONB_COLS else v
                            for k, v in subtype.items()]
            self.conn.execute(
                f"insert into {table}({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
                vals,
            )
        return eid

    def edge(self, src: UUID, dst: UUID, rel: str, *, start: datetime | None = None,
             end: datetime | None = None, source: str | None = None, confidence: int = 3,
             world: bool = False, note: str | None = None) -> None:
        self.conn.execute(
            "insert into entity_relationships(src_id, dst_id, rel, valid, source_id, confidence, case_id, note) "
            "values (%s,%s,%s,%s,%s,%s,%s,%s)",
            (src, dst, rel, Range(start, end, "[)"), self.source(source) if source else None,
             confidence, None if world else self.case_id, note),
        )

    def role(self, eid: UUID, role: str, hop: int | None = None, why: str | None = None) -> None:
        self.conn.execute(
            "insert into case_entities(case_id, entity_id, role, hop, explanation) values (%s,%s,%s,%s,%s) "
            "on conflict (case_id, entity_id) do update set role = case "
            "  when case_entities.role = 'initial_clue' then 'initial_clue'::case_role "        # clue is permanent
            "  when case_entities.role = 'chain' and excluded.role <> 'initial_clue' then 'chain'::case_role "  # stay chained
            "  else excluded.role end, "
            "hop = coalesce(case_entities.hop, excluded.hop), "         # keep the earliest hop assigned
            "explanation = coalesce(case_entities.explanation, excluded.explanation)",
            (self.case_id, eid, role, hop, why),
        )


JSONB_COLS = {"received_chain", "c2_config"}
