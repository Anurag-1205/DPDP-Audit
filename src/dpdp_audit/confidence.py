"""Per-flow confidence over seeds (AC-04.13), the input of selective accuracy (SPEC-07, AC-07.1).

For each system and flow of a split: the disclosure label of every seed, the majority label,
the confidence (share of the flow's seeds that give the majority label) and a token-probability
tie-break (mean, over those seeds, of the probability of the reply that decided the label).

- Pipeline: a flow's label carries the probability of the reviewer reply that decided it
  (one reply per candidate in v2, one per reviewer call in v1). Flows no LLM decided (the
  finder's rules found them clear, or its reading was kept) have no probability.
- Single-prompt baselines (B1, B2): every flow takes the reply's probability. B4 (Gemini) has
  none, so its tie-break is empty.
- Ties between labels are broken by the higher mean probability, then by the label order
  clear < vague < omitted < incorrect, so the result is deterministic.
- A flow missing from a seed's output counts as "clear" (as the scorer reads it). A seed with a
  missing run or a failed call is left out, as in score_runs.py; `seeds` lists those used.
"""
from __future__ import annotations

from collections import Counter

from .cases import case_dirs, load_case, load_key
from .runs import load_runs, seeds_available

LABEL_ORDER = ["clear", "vague", "omitted", "incorrect"]


def flow_votes(out: dict) -> dict[str, tuple[str, float | None]]:
    """{flow_id: (label, probability)} of one run."""
    votes = {}
    run_prob = out.get("token_prob") if "trace" not in out else None   # baselines: one reply per case
    for fid, lab in (out.get("flow_labels") or {}).items():
        if isinstance(lab, dict):
            label, prob = lab.get("label") or "clear", lab.get("confidence")
        else:
            label, prob = lab or "clear", None
        votes[fid] = (label, prob if prob is not None else run_prob)
    return votes


def combine(votes: list[tuple[str, float | None]]) -> dict:
    """Majority label, agreement share and tie-break of one flow's votes (one per seed)."""
    counts = Counter(label for label, _ in votes)

    def mean_prob(label):
        ps = [p for lab, p in votes if lab == label and p is not None]
        return sum(ps) / len(ps) if ps else None

    def rank(label):
        p = mean_prob(label)
        return (counts[label], p if p is not None else -1.0, -LABEL_ORDER.index(label))

    majority = max(counts, key=rank)
    return {"label": majority, "agreement": counts[majority] / len(votes), "token_prob": mean_prob(majority),
            "votes": [label for label, _ in votes]}


def flow_confidence(split: str, system: str) -> dict:
    """Rows for every gold flow of the split; None when the system has no complete seed."""
    case_ids = [load_case(d)["case_id"] for d in case_dirs(split)]
    keys = {c: load_key(split, c) for c in case_ids}
    runs = {}
    for s in seeds_available(split, system):
        outs = load_runs(split, system, s, case_ids)
        if outs is not None and not any((o.get("parse_error") or "").startswith("call failed") for o in outs):
            runs[s] = {o["case_id"]: o for o in outs}
    seeds = sorted(runs)
    if not seeds:
        return None
    rows = []
    for c in case_ids:
        k = keys[c]
        per_seed = [flow_votes(runs[s][c]) for s in seeds]
        for fid, gold in k["flow_labels"].items():
            votes = [v.get(fid, ("clear", None)) for v in per_seed]
            rows.append(dict(case_id=c, policy_id=k["policy_id"], flow_id=fid, gold=gold,
                             rung=k.get("rung"), n_seeds=len(seeds), **combine(votes)))
    return {"system": system, "split": split, "seeds": seeds, "flows": rows}
