"""Table of ~20 common analytics, advertising and crash-reporting SDKs."""
from __future__ import annotations

import csv
from functools import lru_cache

from ..paths import DATA


@lru_cache(maxsize=1)
def sdk_table() -> list[dict]:
    with (DATA / "tools" / "sdk_table.csv").open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["ad_or_tracking"] = r["ad_or_tracking"] == "true"
    return rows


def lookup_sdk(name_or_coordinate: str) -> dict | None:
    """Match an SDK id, display name or package coordinate (gradle/npm/pypi)."""
    key = name_or_coordinate.strip().lower()
    for r in sdk_table():
        candidates = [r["sdk_id"], r["name"].lower(), r["gradle"].lower(), r["npm"].lower(), r["pypi"].lower()]
        if key in {c for c in candidates if c}:
            return r
        if r["gradle"] and key.startswith(r["gradle"].lower() + ":"):  # gradle with version
            return r
    return None
