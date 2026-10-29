"""Export per-flow confidence over seeds (AC-04.13) for selective accuracy (SPEC-07).

  python scripts/export_confidence.py --split main --systems B1 B2 B4 full full_finetuned full_v2 full_v2_finetuned

Writes results/confidence/<split>.json: {system: {"seeds", "flows": [{case_id, policy_id, flow_id,
gold, rung, n_seeds, label, agreement, token_prob, votes}]}} (src/dpdp_audit/confidence.py).
On the ladder each row also says whether the human check accepted the rung (`accepted`); score
only accepted rungs, as score_ladder.py does.
Flow labels do not depend on the verifier, so the *_rv runs are not needed.
"""
import argparse
import json

from dpdp_audit.confidence import flow_confidence
from dpdp_audit.paths import RESULTS

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--systems", nargs="+", required=True)
    args = ap.parse_args()
    accepted = None
    if args.split == "ladder":
        from dpdp_audit.ladder import accepted_cases
        accepted = accepted_cases()
    out = {}
    for system in args.systems:
        res = flow_confidence(args.split, system)
        if res is None:
            raise SystemExit(f"{args.split}/{system}: no complete seed")
        rows = res["flows"]
        if accepted is not None:
            for r in rows:
                r["accepted"] = r["case_id"] in accepted
        out[system] = {"seeds": res["seeds"], "flows": rows}
        acc = sum(r["label"] == r["gold"] for r in rows) / len(rows)
        unanimous = sum(r["agreement"] == 1 for r in rows) / len(rows)
        with_prob = sum(r["token_prob"] is not None for r in rows) / len(rows)
        print(f"{system:18} seeds {res['seeds']}  flows {len(rows)}  majority accuracy {acc:.3f}  "
              f"unanimous {unanimous:.2f}  with token prob {with_prob:.2f}")
    path = RESULTS / "confidence" / f"{args.split}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=0))
    print(f"wrote {path}")
