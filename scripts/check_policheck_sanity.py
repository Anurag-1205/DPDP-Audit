"""Compare PoliCheck's labels on the known-answer set with the expected ones (AC-03.4).

  python scripts/check_policheck_sanity.py results/tools/policheck/sanity/policheck_results.csv
"""
import csv
import json
import sys

from dpdp_audit.paths import DATA, RESULTS
from dpdp_audit.tool_runs import policheck_outputs

if __name__ == "__main__":
    src = DATA / "tools" / "policheck_sanity"
    outs = policheck_outputs(src, __import__("pathlib").Path(sys.argv[1]))
    rows = []
    for r in csv.DictReader((src / "expected.csv").open()):
        got = outs.get(r["package_name"], {}).get("flow_labels", {}).get("f1", {})
        rows.append({"package": r["package_name"], "expected": r["expected"], "policheck": got.get("native"),
                     "match": got.get("native") == r["expected"]})
    report = {"agree": sum(r["match"] for r in rows), "n": len(rows), "rows": rows}
    (RESULTS / "tools" / "policheck" / "sanity").mkdir(parents=True, exist_ok=True)
    (RESULTS / "tools" / "policheck" / "sanity" / "check.json").write_text(json.dumps(report, indent=1))
    for r in rows:
        print(f"{r['package']:28s} expected {r['expected']:9s} PoliCheck {r['policheck']}")
    print(f"{report['agree']}/{report['n']} agree")
