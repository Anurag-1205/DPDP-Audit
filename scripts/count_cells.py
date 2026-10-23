"""Count usable cases per gap type x level over the held-out policies.

Writes data/benchmark/cell_counts.csv. Cells with fewer than MIN_CELL policies
are marked exploratory: their cases keep their true labels, but results for
them are reported as exploratory (the plan's merge rule).
"""
import csv

from dpdp_audit.cells import count_cells
from dpdp_audit.gaps import GAP_TYPES, LEVELS
from dpdp_audit.opp115 import load_all
from dpdp_audit.paths import DATA
from dpdp_audit.split import load_split

MIN_CELL = 10

if __name__ == "__main__":
    held = set(load_split()["heldout"])
    policies = [p for p in load_all() if f"{p.policy_id}_{p.name}" in held]
    cells = count_cells(policies)
    out = DATA / "benchmark" / "cell_counts.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["gap_type", "level", "n_policies", "status"])
        for g in GAP_TYPES:
            for lvl in LEVELS:
                n = len(cells.get((g, lvl), []))
                if g == "childrens_data" and lvl == "vague":
                    continue
                w.writerow([g, lvl, n, "main" if n >= MIN_CELL else ("exploratory" if n else "empty")])
    print(out.read_text())
