"""Build the vagueness ladder (SPEC-06): 35 ladders x 4 rungs from the held-out policies.

  python scripts/build_ladder.py [--seed 0]
  python scripts/export_policheck.py --split ladder

Writes data/benchmark/ladder/{cases,answer_keys}/, check_sheet.csv (one row per rung, for
the two human checkers), removed_sentences.json (what the base policy removed, and the
residual-mention flags) and summary.json.
"""
import argparse
import json

from dpdp_audit.ladder import build

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()
    print(json.dumps(build(seed=args.seed), indent=1))
