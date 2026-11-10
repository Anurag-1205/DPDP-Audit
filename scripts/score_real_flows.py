"""Score every system on the real flows (SPEC-08, AC-08.3; docs/stage-4-plan.md §5).

  python scripts/score_real_flows.py [--systems S1 S2 B1 B2 full_v2_rv full_v2_finetuned_rv]

Against the settled human labels (data/benchmark/real_flows/answer_keys/, from
data/real_flows/sample.csv): flow-label accuracy and macro-F1, gap detection P/R/F1 in the common
and common-native views, per-flow false alarms on flows settled as clear, and Cohen's kappa of each
system with each labeller next to the labellers' own kappa. Means over seeds; 95% app-level
bootstrap intervals on seed 0; paired intervals of the headline system minus every other system.
Writes results/scores/real_flows.json.
"""
import argparse
import csv
import json

import numpy as np

from dpdp_audit import real_flow_score as rf
from dpdp_audit import score
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.paths import DATA, RESULTS
from dpdp_audit.runs import load_runs, seeds_available

SPLIT = "real_flows"
HEADLINE = "full_v2_finetuned_rv"
DEFAULT = ["S1", "S2", "B1", "B2", "full_v2_rv", HEADLINE]


def labellers():
    rows = list(csv.DictReader(open(DATA / "real_flows" / "sample.csv")))
    names = {}
    for i in (1, 2):   # the note starts with the labeller's name ("naveen: ...")
        names[i] = rows[0][f"labeller_{i}_note"].split(":", 1)[0].strip() or f"labeller_{i}"
    labs = {names[i]: {(r["package"], r["flow_id"]): r[f"labeller_{i}_label"] for r in rows} for i in (1, 2)}
    a, b = list(labs.values())
    keys = sorted(a)
    human = {"kappa": rf.cohen_kappa([a[k] for k in keys], [b[k] for k in keys]),
             "agreement": float(np.mean([a[k] == b[k] for k in keys])), "n": len(keys), "labellers": list(labs)}
    return labs, human


def per_seed(keys, outs, labs):
    common = [score.common_subset(k, o) for k, o in zip(keys, outs)]
    ck, co = [c[0] for c in common], [c[1] for c in common]
    native = [score.native_reading(k, o) for k, o in zip(ck, co)]
    return {
        "label_accuracy": rf.label_accuracy(keys, outs),
        "label_macro_f1": score.label_macro_f1(keys, outs)["macro_f1"],
        "gap_accuracy": rf.gap_accuracy(keys, outs),
        "flow_false_alarm": rf.flow_false_alarm(keys, outs),
        "detection_common": score.detection(ck, co)["overall"],
        "detection_common_native": score.detection([n[0] for n in native], [n[1] for n in native])["overall"],
        "citation_correct": score.grounding(keys, outs)["citation_correct"],
        "labeller_kappa": rf.labeller_agreement(keys, outs, labs),
        "confusion": rf.confusion(keys, outs),
    }


def f1_common(keys, outs):
    c = [score.common_subset(k, o) for k, o in zip(keys, outs)]
    return score.f1_metric([x[0] for x in c], [x[1] for x in c])


METRICS = {"label_accuracy": rf.label_accuracy, "gap_accuracy": rf.gap_accuracy,
           "flow_false_alarm": rf.flow_false_alarm, "f1_common": f1_common}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=DEFAULT)
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args()

    case_ids = [load_case(d)["case_id"] for d in case_dirs(SPLIT)]
    keys = [load_key(SPLIT, c) for c in case_ids]
    labs, human = labellers()
    results, seed0 = {}, {}
    for system in args.systems:
        runs = []
        for seed in seeds_available(SPLIT, system):
            outs = load_runs(SPLIT, system, seed, case_ids)
            if outs is None:
                print(f"{system} seed{seed}: incomplete, skipped")
                continue
            if any((o.get("parse_error") or "").startswith("call failed") for o in outs):
                print(f"{system} seed{seed}: failed calls, skipped")
                continue
            runs.append(per_seed(keys, outs, labs))
            seed0.setdefault(system, outs)
        if not runs:
            print(f"{system}: no complete runs")
            continue
        mean = lambda f: float(np.nanmean([f(r) for r in runs]))
        results[system] = {
            "n_seeds": len(runs),
            "label_accuracy": mean(lambda r: r["label_accuracy"]),
            "label_macro_f1": mean(lambda r: r["label_macro_f1"]),
            "gap_accuracy": mean(lambda r: r["gap_accuracy"]),
            "flow_false_alarm": mean(lambda r: r["flow_false_alarm"]),
            "f1_common": mean(lambda r: r["detection_common"]["f1"]),
            "f1_common_native": mean(lambda r: r["detection_common_native"]["f1"]),
            "citation_correct": mean(lambda r: r["citation_correct"]),
            "kappa": {n: mean(lambda r, n=n: r["labeller_kappa"][n]["kappa"]) for n in labs},
            "ci_seed0": {m: score.cluster_bootstrap(keys, seed0[system], f, n=args.bootstrap)
                         for m, f in METRICS.items()},
            "per_seed": runs,
        }
    paired = {}
    if HEADLINE in seed0:
        for other in seed0:
            if other != HEADLINE:
                paired[f"{HEADLINE}-{other}"] = {
                    m: score.cluster_bootstrap(keys, seed0[HEADLINE], f, n=args.bootstrap, outs_b=seed0[other])
                    for m, f in METRICS.items()}
    gold = [g for k in keys for g in k["flow_labels"].values()]
    out = {"n_apps": len(keys), "n_flows": len(gold), "settled_labels": dict(sorted(
        {l: gold.count(l) for l in set(gold)}.items())), "human": human,
        "systems": results, "paired_seed0": paired}
    path = RESULTS / "scores" / f"{SPLIT}.json"
    path.write_text(json.dumps(out, indent=1))

    names = list(labs)
    print(f"{len(keys)} apps, {len(gold)} flows; labellers {names[0]} vs {names[1]}: kappa {human['kappa']:.3f}")
    cols = ["label_accuracy", "label_macro_f1", "gap_accuracy", "flow_false_alarm", "f1_common", "f1_common_native"]
    print("| system | seeds | " + " | ".join(cols) + " | " + " | ".join(f"kappa {n}" for n in names) + " |")
    print("|---" * (len(cols) + 2 + len(names)) + "|")
    for s, r in results.items():
        print(f"| {s} | {r['n_seeds']} | " + " | ".join(f"{r[c]:.3f}" for c in cols) + " | "
              + " | ".join(f"{r['kappa'][n]:.3f}" for n in names) + " |")
    for pair, r in paired.items():
        print(f"paired {pair} (seed 0): " + "; ".join(
            f"{k} {v['point']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}]" for k, v in r.items()))
    print("wrote", path)


if __name__ == "__main__":
    main()
