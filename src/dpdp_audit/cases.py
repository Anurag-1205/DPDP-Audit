"""On-disk format of benchmark cases and answer keys.

data/benchmark/<split>/cases/<case_id>/
    policy.txt          privacy policy, one paragraph (OPP-115 segment) per block
    app/                build.gradle, AndroidManifest.xml, app_config.json, dataflows.json
    meta.json           {"case_id", "policy_id", "kind", "planted": [...]}
data/benchmark/<split>/answer_keys/<case_id>.json
"""
from __future__ import annotations

import json
from pathlib import Path

from .paths import DATA

BENCH = DATA / "benchmark"


def case_dirs(split: str = "main") -> list[Path]:
    root = BENCH / split / "cases"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.exists() else []


def load_case(case_dir: Path) -> dict:
    meta = json.loads((case_dir / "meta.json").read_text())
    return dict(meta, dir=case_dir, policy=(case_dir / "policy.txt").read_text(), app_dir=case_dir / "app")


def load_key(split: str, case_id: str) -> dict:
    return json.loads((BENCH / split / "answer_keys" / f"{case_id}.json").read_text())


def load_split(split: str = "main") -> tuple[list[dict], list[dict]]:
    cases = [load_case(d) for d in case_dirs(split)]
    keys = [load_key(split, c["case_id"]) for c in cases]
    return cases, keys


def raw_app_files(app_dir: Path) -> str:
    """Concatenate the application's files as they appear on disk (for B1)."""
    parts = []
    for p in sorted(app_dir.iterdir()):
        if p.is_file():
            parts.append(f"--- {p.name} ---\n{p.read_text()}")
    return "\n\n".join(parts)
