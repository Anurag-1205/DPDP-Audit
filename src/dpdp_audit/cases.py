"""On-disk format of benchmark cases and answer keys.

data/benchmark/<split>/cases/<case_id>/
    policy.txt          privacy policy, one paragraph (OPP-115 segment) per block
    app/                build.gradle, AndroidManifest.xml, dataflows.json
                        (tools.app also reads app_config.json, package.json and requirements.txt
                        when an app has them; generated cases do not)
    meta.json           {"case_id", "policy_id", "policy_name"} -- never the answer
data/benchmark/<split>/answer_keys/<case_id>.json   the answer: kind, findings, flow labels, planted gaps

Systems under test must not read the case id or meta.json: ids such as "1028_control" name the
case kind. B1, B2 and the pipeline build their prompts from policy.txt and app/ only
(tests/test_pipeline.py::test_prompts_never_contain_case_id).
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
