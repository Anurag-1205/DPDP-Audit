"""Score saved runs against the answer keys.

  python scripts/score_runs.py --systems B1 B2 [--split main]

Writes outputs/scores/<split>.json and prints a table: mean over seeds, with
95% policy-level bootstrap intervals on seed 0. Reports the full benchmark and
the common subset (collection/sharing), the latter under both readings of
vague disclosure.
"""
import argparse
import json

import numpy as np

from dpdp_audit import score
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.paths import OUTPUTS
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
    args = ap.parse_args()

    case_ids = [load_case(d)["case_id"] for d in case_dirs(args.split)]
    keys = [load_key(args.split, c) for c in case_ids]
    results = {}
    for system in args.systems:
        per_seed = []
        for seed in seeds_available(args.split, system):
            outs = load_runs(args.split, system, seed, case_ids)
            if outs is None:
                print(f"{system} seed{seed}: incomplete, skipped")
                continue
            per_seed.append({name: score.evaluate(*v) for name, v in views(keys, outs).items()})
            if seed == seeds_available(args.split, system)[0]:
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
    out = OUTPUTS / "scores" / f"{args.split}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    old = json.loads(out.read_text()) if out.exists() else {}
    old.update(results)
    out.write_text(json.dumps(old, indent=1))

    cols = ["f1_full", "f1_common", "f1_common_native", "label_macro_f1", "false_alarm_rate", "citation_correct"]
    print("| system | seeds | " + " | ".join(cols) + " |")
    print("|---" * (len(cols) + 2) + "|")
    for s, r in results.items():
        print(f"| {s} | {r['n_seeds']} | " + " | ".join(f"{r[c]:.3f}" for c in cols) + " |")


if __name__ == "__main__":
    main()
