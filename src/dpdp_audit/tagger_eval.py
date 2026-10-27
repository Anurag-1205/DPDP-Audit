"""Score a tagger: multi-label OPP-115 category F1 per category, macro and micro.

Gold and predictions are lists of {"policy_id", "segment_id", "categories": [...]}; a
segment with no prediction counts as predicting no category.
"""
from __future__ import annotations

from .tagger_data import CATEGORIES


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": p, "recall": r, "f1": 2 * p * r / (p + r) if p + r else 0.0,
            "support": tp + fn}


def evaluate(gold: list[dict], pred: list[dict]) -> dict:
    by_key = {(str(p["policy_id"]), int(p["segment_id"])): set(p.get("categories", [])) for p in pred}
    counts = {c: [0, 0, 0] for c in CATEGORIES}
    for g in gold:
        gs = set(g["categories"])
        ps = by_key.get((str(g["policy_id"]), int(g["segment_id"])), set())
        for c in CATEGORIES:
            idx = 0 if c in gs and c in ps else 1 if c in ps else 2 if c in gs else None
            if idx is not None:
                counts[c][idx] += 1
    per = {c: _prf(*v) for c, v in counts.items()}
    tot = [sum(v[i] for v in counts.values()) for i in range(3)]
    return {"macro_f1": sum(v["f1"] for v in per.values()) / len(per),
            "micro_f1": _prf(*tot)["f1"], "per_category": per, "n_segments": len(gold),
            "n_predicted": sum(1 for g in gold if (str(g["policy_id"]), int(g["segment_id"])) in by_key)}


def _tuples(claims: list[dict]) -> tuple[set, set]:
    does = {(c["category"], c["data_type"], c["does"]) for c in claims
            if c["category"] in ("First Party Collection/Use", "Third Party Sharing/Collection")}
    party = {(c["category"], c["data_type"], c["third_party"]) for c in claims
             if c["category"] == "Third Party Sharing/Collection"}
    return does, party


def evaluate_tuples(gold: list[dict], pred: list[dict]) -> dict:
    """Micro P/R/F1 of (category, data type, does/does not) and (category, data type, third party) tuples.

    Gold and predictions carry "claims" (pipeline.claims format) per (policy_id, segment_id).
    """
    by_key = {(str(p["policy_id"]), int(p["segment_id"])): p.get("claims", []) for p in pred}
    counts = {"does": [0, 0, 0], "third_party": [0, 0, 0]}
    for g in gold:
        gd, gp = _tuples(g.get("claims", []))
        pd, pp = _tuples(by_key.get((str(g["policy_id"]), int(g["segment_id"])), []))
        for name, gs, ps in (("does", gd, pd), ("third_party", gp, pp)):
            counts[name][0] += len(gs & ps)
            counts[name][1] += len(ps - gs)
            counts[name][2] += len(gs - ps)
    return {f"tuple_{k}": _prf(*v) for k, v in counts.items()}
