"""Selective accuracy (SPEC-07): how much human review a checker needs before its labels can be trusted.

Input: the per-flow rows of results/confidence/<split>.json (confidence.py, AC-07.1): majority
label over three seeds, agreement (share of seeds giving it) and a token-probability tie-break.

- Review order (AC-07.2): flows are reviewed from least to most confident, by agreement, then token
  probability. A flow without a probability (decided by the pipeline's rules, or a B4 reply) ranks
  above every probability of its agreement level. A reviewed flow takes its gold label.
- Ties (AC-07.7): flows with the same (agreement, probability) form a group reviewed in random
  order, so the curve is the *expected* accuracy: reviewing j of a group of n removes j/n of its
  correct flows. The result is deterministic and does not depend on the order flows are listed in.
- Curve: the accuracy of the flows not yet reviewed against the share reviewed, at every flow
  (0..N). With every flow reviewed nothing is left to be wrong, so the last point is 1.
- Metrics (AC-07.3): area under that curve (trapezoid over 0..1), R@95 = the smallest share reviewed
  at which the unreviewed flows are at least 95% accurate, and the share needed to reach a target
  accuracy (e.g. the best tool's). A system already at the target needs 0.
- Intervals (AC-07.6): policy-level cluster bootstrap, as in score.cluster_bootstrap.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

TARGET = 0.95


def _key(r: dict) -> tuple[float, float]:
    p = r.get("token_prob")
    return (r["agreement"], math.inf if p is None else p)


def curve(rows: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """(share reviewed, accuracy of the unreviewed flows) at k = 0..N reviewed flows."""
    n = len(rows)
    if n == 0:
        return np.array([0.0, 1.0]), np.array([1.0, 1.0])
    groups = defaultdict(lambda: [0, 0])     # key -> [flows, correct]
    for r in rows:
        g = groups[_key(r)]
        g[0] += 1
        g[1] += r["label"] == r["gold"]
    correct_left = float(sum(c for _, c in groups.values()))
    acc = [correct_left / n]
    for k in sorted(groups):
        size, correct = groups[k]
        for _ in range(size):
            correct_left -= correct / size
            left = n - len(acc)
            acc.append(correct_left / left if left else 1.0)
    return np.arange(n + 1) / n, np.array(acc)


def review_needed(share: np.ndarray, acc: np.ndarray, target: float = TARGET) -> float:
    """Smallest share reviewed at which the unreviewed flows reach the target accuracy."""
    hit = np.nonzero(acc >= target - 1e-12)[0]
    return float(share[hit[0]]) if len(hit) else 1.0


def auc(share: np.ndarray, acc: np.ndarray) -> float:
    return float(np.sum((share[1:] - share[:-1]) * (acc[1:] + acc[:-1]) / 2))


def accuracy(rows: list[dict]) -> float:
    return sum(r["label"] == r["gold"] for r in rows) / len(rows) if rows else float("nan")


def summary(rows: list[dict], match: float | None = None) -> dict:
    share, acc = curve(rows)
    out = {"n_flows": len(rows), "accuracy": accuracy(rows), "auc": auc(share, acc),
           "r95": review_needed(share, acc, TARGET)}
    if match is not None:
        out["review_to_match"] = review_needed(share, acc, match)
    return out


def _by_policy(rows: list[dict]) -> dict[str, list[dict]]:
    groups = defaultdict(list)
    for r in rows:
        groups[r["policy_id"]].append(r)
    return groups


def bootstrap_r95(rows: list[dict], n: int = 1000, seed: int = 0, rows_b: list[dict] | None = None,
                  target: float = TARGET) -> dict:
    """R@95 with a 95% policy-level interval; with rows_b, the paired difference R@95(a) - R@95(b)
    on the same policy re-samples (both systems must cover the same flows)."""
    def stat(a, b):
        ra = review_needed(*curve(a), target)
        return ra if b is None else ra - review_needed(*curve(b), target)

    ga = _by_policy(rows)
    gb = _by_policy(rows_b) if rows_b is not None else None
    pids = sorted(ga)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n):
        pick = rng.choice(len(pids), size=len(pids), replace=True)
        a = [r for i in pick for r in ga[pids[i]]]
        b = [r for i in pick for r in gb.get(pids[i], [])] if gb is not None else None
        vals.append(stat(a, b))
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return {"point": stat(rows, rows_b), "lo": float(lo), "hi": float(hi)}


def rung_confidence(rows: list[dict], a: str = "vague", b: str = "explicit", n: int = 1000,
                    seed: int = 0) -> dict:
    """Paired confidence of the target flow on two rungs of the same ladder (AC-07.5): mean of
    (rung a - rung b) for agreement and token probability, with a 95% interval over ladders, and
    how many ladders are lower, equal and higher on rung a. Ladder id = case id before "_r"."""
    by = defaultdict(dict)
    for r in rows:
        by[r["case_id"].rsplit("_r", 1)[0]][r["rung"]] = r
    pairs = [(x[a], x[b]) for x in by.values() if a in x and b in x]
    out = {"n_ladders": len(pairs)}
    rng = np.random.default_rng(seed)
    for field in ("agreement", "token_prob"):
        d = np.array([ra[field] - rb[field] for ra, rb in pairs
                      if ra[field] is not None and rb[field] is not None], dtype=float)
        if not len(d):
            out[field] = None
            continue
        boots = [rng.choice(d, size=len(d), replace=True).mean() for _ in range(n)]
        lo, hi = np.percentile(boots, [2.5, 97.5])
        out[field] = {"n": len(d), "mean_difference": float(d.mean()), "lo": float(lo), "hi": float(hi),
                      "lower": int((d < 0).sum()), "equal": int((d == 0).sum()), "higher": int((d > 0).sum())}
    return out
