"""Score saved runs against the answer keys.

  python scripts/score_runs.py --systems B1 B2 [--split main] [--paired B2-B1 full-S1 ...]

Writes results/scores/<split>.json and prints a table: mean over seeds, with
95% policy-level bootstrap intervals on seed 0. Reports the full benchmark and
the common subset (collection/sharing), the latter under both readings of
vague disclosure. --paired A-B adds paired bootstrap intervals (seed 0, the same policy
re-samples for both systems) of A minus B for F1 in every view and for the false-alarm rate.
"""
import argparse
import json

import numpy as np

from dpdp_audit import score
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import load_runs, seeds_available


def views(keys, outs):
    full = (keys, outs)
    cs = list(zip(*[score.common_subset(k, o) for k, o in zip(keys, outs)]))
    cs_native = list(zip(*[score.native_reading(k, o) for k, o in zip(*cs)]))
    return {"full": full, "common": (list(cs[0]), list(cs[1])),
            "common_native": (list(cs_native[0]), list(cs_native[1]))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", required=True)
    ap.add_argument("--split", default="main")
    ap.add_argument("--bootstrap", type=int, default=1000)
    ap.add_argument("--paired", nargs="*", default=[], help="pairs A-B, e.g. full-B2")
    args = ap.parse_args()

    case_ids = [load_case(d)["case_id"] for d in case_dirs(args.split)]
    keys = [load_key(args.split, c) for c in case_ids]
    results = {}
    for system in args.systems:
        per_seed, ci = [], {}
        for seed in seeds_available(args.split, system):
            outs = load_runs(args.split, system, seed, case_ids)
            if outs is None:
                print(f"{system} seed{seed}: incomplete, skipped")
                continue
            failed = sum(1 for o in outs if (o.get("parse_error") or "").startswith("call failed"))
            if failed:   # a failed call is not an empty answer
                print(f"{system} seed{seed}: {failed} failed calls, skipped (re-run with --redo-failed)")
                continue
            per_seed.append({name: score.evaluate(*v) for name, v in views(keys, outs).items()})
            if not ci:
                v = views(keys, outs)
                ci = {name: score.cluster_bootstrap(*v[name], score.f1_metric, n=args.bootstrap)
                      for name in v}
                ci["false_alarm"] = score.cluster_bootstrap(keys, outs, score.false_alarm_metric, n=args.bootstrap)
        if not per_seed:
            continue
        mean = lambda f: float(np.mean([f(r) for r in per_seed]))
        results[system] = {
            "n_seeds": len(per_seed),
            "f1_full": mean(lambda r: r["full"]["detection"]["overall"]["f1"]),
            "f1_common": mean(lambda r: r["common"]["detection"]["overall"]["f1"]),
            "f1_common_native": mean(lambda r: r["common_native"]["detection"]["overall"]["f1"]),
            "label_macro_f1": mean(lambda r: r["full"]["labels"]["macro_f1"]),
            "false_alarm_rate": mean(lambda r: r["full"]["safety"]["false_alarm_rate"]),
            "citation_correct": mean(lambda r: r["full"]["grounding"]["citation_correct"]),
            "ci_seed0": ci,
            "per_seed": per_seed,
        }
    paired = {}
    for pair in args.paired:
        a, b = pair.split("-", 1)
        sa, sb = seeds_available(args.split, a), seeds_available(args.split, b)
        oa = load_runs(args.split, a, sa[0], case_ids) if sa else None
        ob = load_runs(args.split, b, sb[0], case_ids) if sb else None
        if oa is None or ob is None:
            print(f"paired {pair}: runs missing, skipped")
            continue
        va, vb = views(keys, oa), views(keys, ob)
        paired[pair] = {name: score.cluster_bootstrap(*va[name], score.f1_metric, n=args.bootstrap,
                                                      outs_b=vb[name][1]) for name in va}
        paired[pair]["false_alarm"] = score.cluster_bootstrap(keys, oa, score.false_alarm_metric,
                                                              n=args.bootstrap, outs_b=ob)
    out = RESULTS / "scores" / f"{args.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(out.read_text()) if out.exists() else {}
    old.update(results)
    if paired:
        old.setdefault("paired", {}).update(paired)
    out.write_text(json.dumps(old, indent=1))

    cols = ["f1_full", "f1_common", "f1_common_native", "label_macro_f1", "false_alarm_rate", "citation_correct"]
    print("| system | seeds | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 2) + "|")
    for s, r in results.items():
        print(f"| {s} | {r['n_seeds']} | " + " | ".join(f"{r[c]:.3f}" for c in cols) + " |")
    for pair, r in paired.items():
        print(f"paired {pair} (seed 0): " + "; ".join(
            f"{k} {v['point']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}]" for k, v in r.items()))


if __name__ == "__main__":
    main()
