"""Convert PoliCheck / PoliGraph output into runs (S1, S2) that the scorers read.

  python scripts/convert_tool_runs.py --split ladder --tools S1 S2

Reads results/tools/policheck/<split>/policheck_results.csv (S1) and
results/tools/poligraph/<split>/poligraph_results.csv (S2) and writes
results/runs/<split>/<S1|S2>/seed0/<case_id>.json for every case of the split. A case with
no exported flow gets an empty output.
"""
import argparse

from dpdp_audit.cases import BENCH, case_dirs, load_case
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import save_run
from dpdp_audit.tool_runs import policheck_outputs, poligraph_outputs

SOURCES = {"S1": ("policheck", policheck_outputs), "S2": ("poligraph", poligraph_outputs)}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--tools", nargs="+", default=["S1", "S2"])
    args = ap.parse_args()
    export = BENCH / args.split / "export" / "policheck"
    for system in args.tools:
        tool, convert = SOURCES[system]
        csv_path = RESULTS / "tools" / tool / args.split / f"{tool}_results.csv"
        if not csv_path.exists():
            print(f"{system}: {csv_path} missing, skipped")
            continue
        outs = convert(export, csv_path)
        n = 0
        for d in case_dirs(args.split):
            cid = load_case(d)["case_id"]
            out = outs.get(cid, {"case_id": cid, "findings": [], "flow_labels": {}})
            save_run(args.split, system, 0, dict(out, system=system, seed=0))
            n += 1
        matched = sum(lab.get("matched", False) for o in outs.values() for lab in o["flow_labels"].values())
        total = sum(len(o["flow_labels"]) for o in outs.values())
        print(f"{system}: {n} runs written; {matched}/{total} exported flows matched a tool row")
