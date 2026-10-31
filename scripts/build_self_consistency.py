"""Self-consistency versions of the single-pass baselines: the majority over their three seeds.

  python scripts/build_self_consistency.py --split main --systems B1 B2 B4

For each case, <system>_sc (saved as seed 0) keeps:
- per flow, the majority disclosure label over the seeds (confidence.combine: ties broken by
  token probability, then label order);
- every finding reported by at least two of the three seeds, matched as the scorer matches
  (same data type and gap type); its level is the majority level, and its flow, sections and
  evidence are those of the first seed (in seed order) that reported it at that level.
Nothing is re-run: the output depends only on the saved runs.
"""
import argparse
from collections import Counter

from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.confidence import combine, flow_votes
from dpdp_audit.runs import load_runs, save_run, seeds_available

SEEDS = [0, 1, 2]


def majority_findings(runs: list[dict]) -> list[dict]:
    by_key: dict[tuple, list[tuple[int, dict]]] = {}
    for s, run in enumerate(runs):
        seen = set()
        for f in run.get("findings", []):
            key = (f.get("data_type"), f.get("gap_type"))
            if key in seen:   # one vote per seed
                continue
            seen.add(key)
            by_key.setdefault(key, []).append((s, f))
    out = []
    for key, votes in by_key.items():
        if len(votes) * 2 <= len(runs):
            continue
        levels = Counter(f.get("level") for _, f in votes)
        top = max(levels.values())
        level = next(f.get("level") for _, f in votes if levels[f.get("level")] == top)
        first = next(f for _, f in votes if f.get("level") == level)
        out.append(dict(first, level=level, votes=len(votes)))
    return out


def build(split: str, system: str) -> int:
    ids = [load_case(d)["case_id"] for d in case_dirs(split)]
    if [s for s in SEEDS if s in seeds_available(split, system)] != SEEDS:
        raise SystemExit(f"{split}/{system}: needs seeds {SEEDS}")
    runs = {s: load_runs(split, system, s, ids) for s in SEEDS}
    if any(r is None for r in runs.values()):
        raise SystemExit(f"{split}/{system}: runs missing")
    for s, outs in runs.items():
        failed = [o["case_id"] for o in outs if (o.get("parse_error") or "").startswith("call failed")]
        if failed:
            raise SystemExit(f"{split}/{system} seed{s}: failed calls in {failed[:3]}")
    name = f"{system}_sc"
    for i, cid in enumerate(ids):
        case_runs = [runs[s][i] for s in SEEDS]
        votes = [flow_votes(r) for r in case_runs]
        flows = sorted({f for v in votes for f in v}, key=lambda f: int(f[1:]) if f[1:].isdigit() else f)
        labels = {}
        for fid in flows:
            c = combine([v.get(fid, ("clear", None)) for v in votes])
            labels[fid] = {"label": c["label"], "confidence": c["agreement"]}
        probs = [r.get("token_prob") for r in case_runs if r.get("token_prob") is not None]
        save_run(split, name, 0, {
            "case_id": cid, "system": name, "seed": 0, "model": case_runs[0].get("model"),
            "findings": majority_findings(case_runs), "flow_labels": labels,
            "token_prob": sum(probs) / len(probs) if probs else None,
            "usage": {k: sum((r.get("usage") or {}).get(k, 0) or 0 for r in case_runs) for k in ("prompt", "output")},
            "parse_error": None, "self_consistency_of": system, "seeds": SEEDS})
    return len(ids)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--systems", nargs="+", required=True)
    args = ap.parse_args()
    for system in args.systems:
        print(f"{args.split}/{system}_sc: {build(args.split, system)} cases")
