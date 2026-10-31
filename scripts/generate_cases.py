"""Generate the main benchmark: control + 2 variants per held-out OPP-115 policy.

  python scripts/generate_cases.py [--seed 0]
  python scripts/generate_cases.py --split dev --policy-set train --n-policies 12
  python scripts/generate_cases.py --split dev2 --policy-set train --n-policies 24 --exclude-splits dev

Writes data/benchmark/<split>/{cases,answer_keys}/ and prints the cell counts of
the planted gaps and of the answer-key findings.
"""
import argparse
import json
from collections import Counter

from dpdp_audit.cases import BENCH
from dpdp_audit.generator import generate

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--split", default="main")
    ap.add_argument("--policy-set", default="heldout", choices=["heldout", "train"])
    ap.add_argument("--n-policies", type=int, default=None)
    ap.add_argument("--exclude-splits", nargs="*", default=[], help="leave out these splits' policies")
    args = ap.parse_args()
    report = generate(seed=args.seed, split=args.split, policy_set=args.policy_set, n_policies=args.n_policies,
                      exclude_splits=tuple(args.exclude_splits))
    # sorted, so summary.json does not depend on the file system's listing order
    keys = [json.loads(p.read_text()) for p in sorted((BENCH / args.split / "answer_keys").glob("*.json"))]
    report["findings"] = {f"{g}/{l}": n for (g, l), n in sorted(
        Counter((f["gap_type"], f["level"]) for k in keys for f in k["findings"]).items())}
    report["labels"] = dict(Counter(lab for k in keys for lab in k["flow_labels"].values()))
    (BENCH / args.split / "summary.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
