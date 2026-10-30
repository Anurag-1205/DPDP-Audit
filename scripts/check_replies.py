"""Gate on reply quality (no scores): fail if too many reviewer replies of a system are unreadable.

  python scripts/check_replies.py --system B5 --splits dev dev2 --max-unreadable 0.03

Counts, over the saved seed-0 runs, failed calls and reviewer replies that could not be read at all
(after the robust reader, if the configuration uses it). Exits 1 if any call failed or the share of
unreadable replies is above the limit. Used by the Kaggle job to run B5 on main and the ladder only
after its dev runs pass (rule fixed on 30 Oct, before those runs).
"""
import argparse
import collections
import sys

from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.runs import load_runs

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--system", required=True)
    ap.add_argument("--splits", nargs="+", required=True)
    ap.add_argument("--max-unreadable", type=float, default=0.03)
    args = ap.parse_args()
    replies = unreadable = failed = 0
    modes = collections.Counter()
    for split in args.splits:
        ids = [load_case(d)["case_id"] for d in case_dirs(split)]
        runs = load_runs(split, args.system, 0, ids)
        if runs is None:
            sys.exit(f"{split}/{args.system}: runs missing")
        for r in runs:
            if (r.get("parse_error") or "").startswith("call failed"):
                failed += 1
                continue
            for i, v in enumerate(r["trace"]["reviews"]):
                replies += 1
                unreadable += bool(v.get("parse_error"))
                mode = (r["trace"].get("reviewer_parse") or [None] * (i + 1))[i]
                modes["unreadable" if v.get("parse_error") else mode or "json"] += 1
    share = unreadable / max(1, replies)
    print(f"{args.system} on {' '.join(args.splits)}: {replies} replies, {unreadable} unreadable ({share:.1%}), "
          f"{failed} failed calls; read as {dict(modes)}")
    if failed or share > args.max_unreadable:
        sys.exit(f"gate failed: limit {args.max_unreadable:.0%} unreadable, 0 failed calls")
    print("gate passed")
