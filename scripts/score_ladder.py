"""Score systems on the vagueness ladder (SPEC-06, AC-06.8).

  python scripts/score_ladder.py --systems S1 S2 B2 full

Per system and seed: label accuracy of the target flow per rung, paired rung differences
(exact McNemar) and the confusion matrix. Only rungs both checkers accepted are scored once
the check sheet is complete; until then every rung is scored and the output says so.
Writes results/scores/ladder.json.
"""
import argparse
import json

from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.ladder import RUNG_ORDER, accepted_cases, score_ladder
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import load_runs, seeds_available

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", required=True)
    args = ap.parse_args()
    ids = [load_case(d)["case_id"] for d in case_dirs("ladder")]
    keys = [load_key("ladder", c) for c in ids]
    accepted = accepted_cases()
    out = {"check_sheet_complete": accepted is not None,
           "n_accepted": len(accepted) if accepted is not None else None}
    for system in args.systems:
        res = {}
        for seed in seeds_available("ladder", system):
            outs = load_runs("ladder", system, seed, ids)
            if outs is None:
                print(f"{system} seed{seed}: incomplete, skipped")
                continue
            res[f"seed{seed}"] = score_ladder(keys, outs, accepted)
        if res:
            out[system] = res
    path = RESULTS / "scores" / "ladder.json"
    old = json.loads(path.read_text()) if path.exists() else {}
    old.update(out)
    path.write_text(json.dumps(old, indent=1))
    print("| system | seed | " + " | ".join(RUNG_ORDER) + " | explicit vs vague (p) |")
    print("|---" * (len(RUNG_ORDER) + 3) + "|")
    for s in args.systems:
        for seed, r in out.get(s, {}).items():
            ev = r["paired"]["explicit_vs_vague"]
            print(f"| {s} | {seed} | " + " | ".join(f"{r['accuracy'][x]:.2f}" for x in RUNG_ORDER)
                  + f" | {ev['difference']:+.2f} (p={ev['p_value']:.3f}) |")
