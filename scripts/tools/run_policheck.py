"""Run PoliCheck in Docker on exported cases.

  python scripts/tools/run_policheck.py --split main --cases 1028_control 1028_v1   # smoke test
  python scripts/tools/run_policheck.py --split main                                # all cases

PoliCheck outputs are converted and saved like any system run (system S1, seed 0).
"""
import argparse
import json
import shutil
import time

from dpdp_audit import tool_runs
from dpdp_audit.cases import BENCH
from dpdp_audit.paths import OUTPUTS
from dpdp_audit.runs import save_run

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--cases", nargs="*", default=None)
    args = ap.parse_args()
    export_dir = BENCH / args.split / "export" / "policheck"
    tool_runs.prepare_ext(export_dir, args.cases, "policheck")
    t0 = time.time()
    proc = tool_runs.run_docker("policheck")
    log = OUTPUTS / "logs" / f"policheck_{args.split}.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    log.write_text(proc.stdout + "\n----- stderr -----\n" + proc.stderr)
    print(f"docker exit {proc.returncode} in {time.time() - t0:.0f}s; log: {log}")
    raw = OUTPUTS / "tools" / "policheck" / args.split
    raw.mkdir(parents=True, exist_ok=True)
    shutil.copy(tool_runs.REPO / "ext" / "policheck_results.csv", raw / "policheck_results.csv")
    outs = tool_runs.policheck_outputs(export_dir)
    for cid, out in outs.items():
        if args.cases is None or cid in args.cases:
            save_run(args.split, "S1", 0, dict(out, system="S1", seed=0))
    print(json.dumps({cid: o["flow_labels"] for cid, o in outs.items() if args.cases is None or cid in args.cases}, indent=1))
