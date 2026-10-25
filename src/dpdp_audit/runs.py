"""Where system runs live: results/runs/<split>/<system>/seed<k>/<case_id>.json."""
from __future__ import annotations

import json
from pathlib import Path

from .paths import RESULTS

RUNS = RESULTS / "runs"


def run_path(split: str, system: str, seed: int, case_id: str) -> Path:
    return RUNS / split / system / f"seed{seed}" / f"{case_id}.json"


def save_run(split: str, system: str, seed: int, out: dict) -> Path:
    p = run_path(split, system, seed, out["case_id"])
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1))
    return p


def load_runs(split: str, system: str, seed: int, case_ids: list[str]) -> list[dict] | None:
    outs = []
    for cid in case_ids:
        p = run_path(split, system, seed, cid)
        if not p.exists():
            return None
        outs.append(json.loads(p.read_text()))
    return outs


def seeds_available(split: str, system: str) -> list[int]:
    d = RUNS / split / system
    if not d.exists():
        return []
    return sorted(int(p.name[4:]) for p in d.iterdir() if p.name.startswith("seed"))
