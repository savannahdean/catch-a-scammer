"""Backward-compatible entry point. Real logic now lives in registry.py and the
scenarios/ package; base.py holds the shared builders."""
from .registry import generate_case, sync_catalog, SCENARIOS  # noqa: F401
