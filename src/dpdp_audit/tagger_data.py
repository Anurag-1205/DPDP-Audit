"""Segment-level tagger data from OPP-115: one example per annotated paragraph.

Each example is a policy segment (paragraph) with the set of OPP-115 categories the
consolidated annotations (threshold 0.75) give it. Segments with no annotation are left
out, as in Polisis and PrivBERT. Train and test follow data/splits.json, so no held-out
policy is seen in training.
"""
from __future__ import annotations

import json
from pathlib import Path

from .opp115 import load_all
from .split import load_split

CATEGORIES = [
    "First Party Collection/Use", "Third Party Sharing/Collection", "User Choice/Control",
    "User Access, Edit and Deletion", "Data Retention", "Data Security", "Policy Change",
    "Do Not Track", "International and Specific Audiences", "Other",
]


def examples(split_name: str) -> list[dict]:
    """split_name: "train" or "heldout"."""
    keep = set(load_split()[split_name])
    out = []
    for pol in load_all():
        if f"{pol.policy_id}_{pol.name}" not in keep:
            continue
        cats: dict[int, set[str]] = {}
        for p in pol.practices:
            if p.category in CATEGORIES:
                cats.setdefault(p.segment_id, set()).add(p.category)
        for seg_id, seg_cats in sorted(cats.items()):
            text = pol.segments[seg_id] if seg_id < len(pol.segments) else ""
            if text.strip():
                out.append({"policy_id": pol.policy_id, "segment_id": seg_id, "text": text,
                            "categories": sorted(seg_cats)})
    return out


def write(out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name in ("train", "heldout"):
        rows = examples(name)
        with (out_dir / f"{name}.jsonl").open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        counts[name] = {"segments": len(rows), "policies": len({r["policy_id"] for r in rows})}
    return counts


def claims_examples(split_name: str) -> list[dict]:
    """Annotated segments with their categories and structured claims (the claims tagger's targets).

    The claims are the oracle tagger's (pipeline.claims.oracle_paragraphs), so the fine-tuned tagger
    learns exactly the format the pipeline reads. split_name: "train" or "heldout".
    """
    from .pipeline.claims import oracle_paragraphs

    keep = set(load_split()[split_name])
    out = []
    for pol in load_all():
        if f"{pol.policy_id}_{pol.name}" not in keep:
            continue
        by_text = {}
        for seg_id, text in enumerate(pol.segments):
            by_text.setdefault(text, seg_id)
        for rec in oracle_paragraphs(pol):
            if rec["categories"]:
                out.append({"policy_id": pol.policy_id, "segment_id": by_text[rec["text"]], "hash": rec["hash"],
                            "text": rec["text"], "categories": rec["categories"], "claims": rec["claims"]})
    return out
