"""Export a benchmark split for PoliCheck and PoliGraph.

  python scripts/export_policheck.py [--split main]
Writes data/benchmark/<split>/export/policheck/.
"""
import argparse
import json

from dpdp_audit.cases import BENCH, case_dirs, load_case
from dpdp_audit.export_policheck import export

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    args = ap.parse_args()
    cases = [load_case(d) for d in case_dirs(args.split)]
    cov = export(cases, BENCH / args.split / "export" / "policheck")
    print(json.dumps(cov, indent=1))
