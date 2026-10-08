"""What keeps a public deployment safe: case keys, rate limits and switches.

CASE KEYS. Cases have counting numbers (/api/cases/41, /api/cases/42, ...), so a
number alone must not open a case. Every case gets a random `access_key` when it
is created; only the browser that created it is told the key, and it sends it
back as the X-Case-Key header. A wrong or missing key gets the same 404 as a
case that does not exist, so nobody can tell which numbers are in use.

RATE LIMITS. Starting a case writes a whole generated world, and the Messenger
and the study write rows too, so each client IP gets a budget per window
(in memory, per server process). Requests from this machine (127.0.0.1, ::1)
are exempt, so the playtest and local development never hit them. Behind a
reverse proxy, run uvicorn with --proxy-headers so the real client IP is used.

SWITCHES (environment variables, "on"/"off"):
  STUDY_ENABLED  default on   off: nobody new can join the study or send answers;
                              existing participants can still withdraw
  LEGACY_API     default on   off: hides the original UUID API (/cases/...),
                              which skips case keys; turn it off in production
  API_DOCS       default on   off: hides /docs and /openapi.json
"""
from __future__ import annotations

import os
import threading
import time
from collections import defaultdict, deque
from contextvars import ContextVar
from uuid import UUID

from fastapi import HTTPException, Request

from .env import load_env

load_env()


def flag(name: str, default: bool) -> bool:
    v = os.environ.get(name, "").strip().lower()
    return default if not v else v in ("1", "on", "true", "yes")


STUDY_ENABLED = flag("STUDY_ENABLED", True)
LEGACY_API = flag("LEGACY_API", True)
API_DOCS = flag("API_DOCS", True)

# ------------------------------------------------------------------ case keys
CASE_KEY_HEADER = "X-Case-Key"
_case_key: ContextVar[str | None] = ContextVar("case_key", default=None)


async def remember_case_key(request: Request, call_next):
    """Middleware: make this request's X-Case-Key available to case lookups."""
    token = _case_key.set(request.headers.get(CASE_KEY_HEADER))
    try:
        return await call_next(request)
    finally:
        _case_key.reset(token)


def case_by_seq(conn, n: int) -> UUID:
    """The case with this number, if the request carries its key; else 404."""
    key = _case_key.get()
    row = conn.execute("select id, access_key::text k from cases where seq=%s", (n,)).fetchone()
    if not row or not key or row["k"] != key.strip().lower():
        raise HTTPException(404, "unknown case")
    return row["id"]


# ------------------------------------------------------------------ rate limits
_LOCAL = {"127.0.0.1", "::1", "localhost", "testclient"}
_hits: dict[tuple[str, str], deque] = defaultdict(deque)
_lock = threading.Lock()


def _budget(name: str, default: str) -> tuple[int, int]:
    """RATE_<NAME>=count/seconds, e.g. RATE_NEW_CASE=20/3600."""
    raw = os.environ.get(f"RATE_{name.upper()}", default)
    count, seconds = raw.split("/")
    return int(count), int(seconds)


def rate_limit(name: str, default: str):
    """A route dependency: at most `count` requests per `seconds` per client IP."""
    count, seconds = _budget(name, default)

    def check(request: Request) -> None:
        ip = request.client.host if request.client else "unknown"
        if ip in _LOCAL or count <= 0:
            return
        now = time.monotonic()
        with _lock:
            q = _hits[(name, ip)]
            while q and q[0] <= now - seconds:
                q.popleft()
            if len(q) >= count:
                wait = int(q[0] + seconds - now) + 1
                raise HTTPException(429, f"Too many requests. Try again in {wait} seconds.",
                                    headers={"Retry-After": str(wait)})
            q.append(now)

    return check
