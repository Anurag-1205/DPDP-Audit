"""Scoring: findings P/R/F1, false alarms, citations, disclosure labels, bootstrap.

Answer key (one per case):
  {"case_id", "policy_id", "kind": "control"|"variant",
   "findings": [{"flow_id", "data_type", "gap_type", "level", "sections"}],
   "flow_labels": {flow_id: "clear"|"vague"|"omitted"|"incorrect"},
   "flow_gap_types": {flow_id: gap_type}}

System output (one per case):
  {"case_id", "findings": [{"data_type", "gap_type", "level", "sections",
                            "uncertain": bool, "supported": bool}],
   "flow_labels": {flow_id: {"label", "confidence"}}}
"""
from __future__ import annotations

import random
from collections import defaultdict

import numpy as np
from sklearn.metrics import f1_score

from .gaps import FLOW_GAP_TYPES, LABELS, citation_ok


# ------------------------------------------------------------------ views
def reported(findings: list[dict]) -> list[dict]:
    """Findings that count as reported (uncertain ones are listed separately)."""
    return [f for f in findings if not f.get("uncertain")]


def common_subset(key: dict, out: dict) -> tuple[dict, dict]:
    """Restrict a case to the gap types PoliCheck/PoliGraph model."""
    k = dict(key, findings=[f for f in key["findings"] if f["gap_type"] in FLOW_GAP_TYPES])
    o = dict(out, findings=[f for f in out.get("findings", []) if f["gap_type"] in FLOW_GAP_TYPES])
    return k, o


def native_reading(key: dict, out: dict) -> tuple[dict, dict]:
    """The tools' reading: a vague disclosure is consistent, so not a gap."""
    k = dict(key, findings=[f for f in key["findings"] if f["level"] != "vague"])
    o = dict(out, findings=[f for f in out.get("findings", []) if f.get("level") != "vague"])
    return k, o


# --------------------------------------------------------------- matching
def match_case(key: dict, out: dict) -> list[tuple[dict, dict | None]]:
    """Greedy one-to-one match on (data_type, gap_type).

    Returns pairs (prediction, matched_key_entry_or_None); unmatched key entries
    are returned as (None, entry).
    """
    remaining = list(key["findings"])
    pairs = []
    for pred in reported(out.get("findings", [])):
        hit = next((g for g in remaining
                    if g["data_type"] == pred["data_type"] and g["gap_type"] == pred["gap_type"]), None)
        if hit is not None:
            remaining.remove(hit)
        pairs.append((pred, hit))
    pairs += [(None, g) for g in remaining]
    return pairs


def _prf(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "tp": tp, "fp": fp, "fn": fn}


def detection(keys: list[dict], outs: list[dict]) -> dict:
    """Overall, per-gap-type and per-level P/R/F1 over findings."""
    tot = [0, 0, 0]
    by_type = defaultdict(lambda: [0, 0, 0])
    by_level = defaultdict(lambda: [0, 0, 0])
    for key, out in zip(keys, outs):
        for pred, gold in match_case(key, out):
            if pred is not None and gold is not None:
                idx, gtype, lvl = 0, gold["gap_type"], gold["level"]
            elif pred is not None:
                idx, gtype, lvl = 1, pred["gap_type"], pred.get("level")
            else:
                idx, gtype, lvl = 2, gold["gap_type"], gold["level"]
            tot[idx] += 1
            by_type[gtype][idx] += 1
            by_level[lvl][idx] += 1
    return {
        "overall": _prf(*tot),
        "by_gap_type": {k: _prf(*v) for k, v in sorted(by_type.items())},
        "by_level": {k: _prf(*v) for k, v in sorted(by_level.items(), key=lambda x: str(x[0]))},
    }


def safety(keys: list[dict], outs: list[dict]) -> dict:
    controls = [(k, o) for k, o in zip(keys, outs) if k["kind"] == "control"]
    alarms = sum(1 for _, o in controls if reported(o.get("findings", [])))
    all_findings = [f for o in outs for f in reported(o.get("findings", []))]
    unsupported = sum(1 for f in all_findings if f.get("supported") is False)
    return {
        "false_alarm_rate": alarms / len(controls) if controls else float("nan"),
        "n_controls": len(controls),
        "unsupported_rate": unsupported / len(all_findings) if all_findings else 0.0,
        "n_uncertain": sum(1 for o in outs for f in o.get("findings", []) if f.get("uncertain")),
    }


def grounding(keys: list[dict], outs: list[dict]) -> dict:
    """Citation correctness over true-positive findings."""
    ok = n = 0
    for key, out in zip(keys, outs):
        for pred, gold in match_case(key, out):
            if pred is not None and gold is not None:
                n += 1
                ok += citation_ok(gold["gap_type"], pred.get("sections", []))
    return {"citation_correct": ok / n if n else float("nan"), "n": n}


def label_macro_f1(keys: list[dict], outs: list[dict]) -> dict:
    """Macro-F1 of disclosure labels over collection/sharing flows."""
    gold, pred = [], []
    for key, out in zip(keys, outs):
        labels = out.get("flow_labels", {})
        for fid, g in key["flow_labels"].items():
            if key.get("flow_gap_types", {}).get(fid, "undisclosed_sharing") not in FLOW_GAP_TYPES:
                continue
            gold.append(g)
            p = labels.get(fid, {})
            pred.append(p.get("label", "clear") if isinstance(p, dict) else p)
    if not gold:
        return {"macro_f1": float("nan"), "n": 0}
    present = [l for l in LABELS if l in gold or l in pred]
    return {"macro_f1": float(f1_score(gold, pred, labels=present, average="macro", zero_division=0)),
            "accuracy": float(np.mean([g == p for g, p in zip(gold, pred)])), "n": len(gold)}


def evaluate(keys: list[dict], outs: list[dict]) -> dict:
    return {"detection": detection(keys, outs), "safety": safety(keys, outs),
            "grounding": grounding(keys, outs), "labels": label_macro_f1(keys, outs)}


# --------------------------------------------------------------- bootstrap
def _by_policy(keys, outs):
    groups = defaultdict(list)
    for k, o in zip(keys, outs):
        groups[k["policy_id"]].append((k, o))
    return groups


def cluster_bootstrap(keys, outs, metric, n: int = 1000, seed: int = 0, outs_b=None):
    """95% interval of metric(keys, outs), resampling whole policies.

    With outs_b, returns the interval of metric(A) - metric(B) (paired).
    """
    rng = random.Random(seed)
    groups_a = _by_policy(keys, outs)
    groups_b = _by_policy(keys, outs_b) if outs_b is not None else None
    policies = sorted(groups_a)
    stats = []
    for _ in range(n):
        sample = [rng.choice(policies) for _ in policies]
        ka = [k for p in sample for k, _ in groups_a[p]]
        oa = [o for p in sample for _, o in groups_a[p]]
        value = metric(ka, oa)
        if groups_b is not None:
            ob = [o for p in sample for _, o in groups_b[p]]
            value -= metric(ka, ob)
        stats.append(value)
    point = metric(keys, outs) - (metric(keys, outs_b) if outs_b is not None else 0.0)
    lo, hi = np.percentile(stats, [2.5, 97.5])
    return {"point": float(point), "lo": float(lo), "hi": float(hi)}


def f1_metric(keys, outs) -> float:
    return detection(keys, outs)["overall"]["f1"]


def false_alarm_metric(keys, outs) -> float:
    return safety(keys, outs)["false_alarm_rate"]
