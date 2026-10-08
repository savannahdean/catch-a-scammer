"""Read backend/.env into the environment, so nobody has to export DATABASE_URL
by hand before running the server, the migrations, the world seed or the tests.

Variables that are already set win: `DATABASE_URL=... python ...` still works.
Format: KEY=value per line; blank lines and # comments are skipped.
"""
from __future__ import annotations

import os
from pathlib import Path

ENV_FILE = Path(__file__).resolve().parents[1] / ".env"


def load_env() -> None:
    if not ENV_FILE.is_file():
        return
    for raw in ENV_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
