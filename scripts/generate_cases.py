"""Generate the main benchmark: control + 2 variants per held-out OPP-115 policy.

  python scripts/generate_cases.py [--seed 0]

Writes data/benchmark/main/{cases,answer_keys}/ and prints the cell counts of
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
    args = ap.parse_args()
    report = generate(seed=args.seed)
    keys = [json.loads(p.read_text()) for p in (BENCH / "main" / "answer_keys").glob("*.json")]
    report["findings"] = {f"{g}/{l}": n for (g, l), n in sorted(
        Counter((f["gap_type"], f["level"]) for k in keys for f in k["findings"]).items())}
    report["labels"] = dict(Counter(lab for k in keys for lab in k["flow_labels"].values()))
    (BENCH / "main" / "summary.json").write_text(json.dumps(report, indent=1))
    print(json.dumps(report, indent=1))
