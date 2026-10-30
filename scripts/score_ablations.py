"""Ablations of v2 on three seeds (WP-3.3), and the B5 baseline: each against the headline system, per seed.

  python scripts/score_ablations.py

For seeds 0-2: F1, recall and false-alarm rate of `full_v2_finetuned_rv` and of each ablation
(A1_v2: verifier off; A2_v2_rv: no DPDP retrieval; A3_v2_rv: one generalist reviewer; A5_v2_rv:
oracle tagger), and the paired policy-level cluster bootstrap of the difference (1,000
re-samples, seed 0), as score_runs.py does for seed 0. Writes results/scores/ablations.json.
"""
import json

from dpdp_audit import score
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import load_runs

HEADLINE = "full_v2_finetuned_rv"
ABLATIONS = {"A1_v2": "verifier off", "A2_v2_rv": "no DPDP retrieval",
             "A3_v2_rv": "one generalist reviewer, no aggregator", "A5_v2_rv": "oracle tagger",
             "B5": "baseline: one call over the whole policy, evidence first (no tagger, finder or agents)"}
SEEDS = [0, 1, 2]


def summary(keys, outs):
    ev = score.evaluate(keys, outs)
    return {"f1": ev["detection"]["overall"]["f1"], "recall": ev["detection"]["overall"]["recall"],
            "false_alarm_rate": ev["safety"]["false_alarm_rate"],
            "citation_correct": ev["grounding"]["citation_correct"]}


def main():
    ids = [load_case(d)["case_id"] for d in case_dirs("main")]
    keys = [load_key("main", c) for c in ids]
    runs = {}
    for system in [HEADLINE, *ABLATIONS]:
        for seed in SEEDS:
            outs = load_runs("main", system, seed, ids)
            if outs is None:
                raise SystemExit(f"main/{system}/seed{seed}: runs missing")
            runs[system, seed] = outs
    result = {"headline": HEADLINE, "seeds": SEEDS, "systems": {}, "paired": {}}
    for system in [HEADLINE, *ABLATIONS]:
        result["systems"][system] = {f"seed{s}": summary(keys, runs[system, s]) for s in SEEDS}
    for system, change in ABLATIONS.items():
        result["paired"][system] = {"change": change}
        for s in SEEDS:   # headline - ablation (A5: ablation - headline, as in the report)
            a, b = (runs[system, s], runs[HEADLINE, s]) if system == "A5_v2_rv" else (runs[HEADLINE, s], runs[system, s])
            result["paired"][system][f"seed{s}"] = {
                "f1": score.cluster_bootstrap(keys, a, score.f1_metric, outs_b=b),
                "false_alarm": score.cluster_bootstrap(keys, a, score.false_alarm_metric, outs_b=b)}
    (RESULTS / "scores" / "ablations.json").write_text(json.dumps(result, indent=1))

    mean = lambda sys_, k: sum(result["systems"][sys_][f"seed{s}"][k] for s in SEEDS) / len(SEEDS)
    print("| config | F1 (mean, 3 seeds) | false-alarm rate | paired F1 difference, seeds 0 / 1 / 2 |")
    print("|---|---|---|---|")
    print(f"| {HEADLINE} | {mean(HEADLINE, 'f1'):.3f} | {mean(HEADLINE, 'false_alarm_rate'):.3f} | — |")
    for system in ABLATIONS:
        diffs = " / ".join("{point:+.3f} [{lo:+.3f}, {hi:+.3f}]".format(**result["paired"][system][f"seed{s}"]["f1"])
                           for s in SEEDS)
        print(f"| {system} | {mean(system, 'f1'):.3f} | {mean(system, 'false_alarm_rate'):.3f} | {diffs} |")


if __name__ == "__main__":
    main()
