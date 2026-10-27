"""Answer-key spot-check (AC-01.10, WP-3.7): 20 main cases checked by hand against the policy text.

  python scripts/spot_check.py make            writes data/spot_check/main_spot_check.csv
  python scripts/spot_check.py score           error rate once the sheet is filled in

The sheet has one row per flow of the sampled cases: the app's flow, the gold label and gold
findings, and the policy sentences the OPP-115 annotations mark for that data type and practice
(to start from; the checker reads the whole policy.txt). A checker fills `agrees` (yes/no) and,
when no, the label and gap they would give. The error rate is the share of flows marked no;
the sample is 6 controls and 14 variants (seed 7).
"""
import csv
import json
import random
import sys

from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.opp115 import DATA_TYPE, GENERIC_TYPES, load_all
from dpdp_audit.paths import DATA

OUT = DATA / "spot_check" / "main_spot_check.csv"
SEED = 7
FIELDS = ["case_id", "flow_id", "data_type", "recipient", "purpose", "retention", "gold_label", "gold_findings",
          "annotated_text", "checker", "agrees", "checker_label", "checker_gap", "notes"]


def sample():
    cases = [load_case(d) for d in case_dirs("main")]
    keys = {c["case_id"]: load_key("main", c["case_id"]) for c in cases}
    controls = sorted(c for c in keys if keys[c]["kind"] == "control")
    variants = sorted(c for c in keys if keys[c]["kind"] == "variant")
    rng = random.Random(SEED)
    return sorted(rng.sample(controls, 6) + rng.sample(variants, 14)), keys


def annotated_text(policy, flow) -> str:
    cat = "First Party Collection/Use" if flow["recipient"] == "first_party" else "Third Party Sharing/Collection"
    exact, generic = [], []
    for p in policy.practices:
        if p.category not in (cat, "Data Retention", "International and Specific Audiences"):
            continue
        target = exact if p.get(DATA_TYPE) == flow["data_type"] else \
            generic if (p.get(DATA_TYPE) in GENERIC_TYPES or not p.get(DATA_TYPE)) else None
        if target is None:
            continue
        # the longest span of the practice is usually its sentence
        v = max((x for x in p.spans.values() if x and x not in ("null", "not selected")), key=len, default="")
        if len(v) > 20 and v not in exact + generic:
            target.append(v)
    parts = [f"[{flow['data_type']}] " + s for s in exact[:5]] + ["[generic] " + s for s in generic[:3]]
    return " || ".join(s.replace("\n", " ")[:300] for s in parts)


def make():
    ids, keys = sample()
    policies = {p.policy_id: p for p in load_all()}
    rows = []
    for cid in ids:
        key = keys[cid]
        flows = json.loads((DATA / "benchmark" / "main" / "cases" / cid / "app" / "dataflows.json").read_text())
        for f in flows:
            gold = [f"{g['gap_type']}/{g['level']}" for g in key["findings"] if g["flow_id"] == f["flow_id"]]
            rows.append({"case_id": cid, "flow_id": f["flow_id"], "data_type": f["data_type"],
                         "recipient": f["recipient"], "purpose": f["purpose"], "retention": f["retention"],
                         "gold_label": key["flow_labels"][f["flow_id"]], "gold_findings": "; ".join(gold) or "none",
                         "annotated_text": annotated_text(policies[key["policy_id"]], f),
                         **{k: "" for k in FIELDS[9:]}})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print(f"{len(ids)} cases, {len(rows)} flows -> {OUT}")


def score():
    rows = list(csv.DictReader(OUT.open()))
    done = [r for r in rows if r["agrees"].strip()]
    if len(done) < len(rows):
        print(f"{len(rows) - len(done)} of {len(rows)} rows not checked yet")
    wrong = [r for r in done if r["agrees"].strip().lower() in ("no", "n", "0", "false")]
    report = {"flows_checked": len(done), "flows_wrong": len(wrong),
              "error_rate": len(wrong) / len(done) if done else None,
              "cases_with_an_error": len({r["case_id"] for r in wrong}),
              "wrong": [{k: r[k] for k in ("case_id", "flow_id", "gold_label", "checker_label", "notes")} for r in wrong]}
    (DATA / "spot_check" / "main_spot_check_result.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k != "wrong"}, indent=1))


if __name__ == "__main__":
    {"make": make, "score": score}[sys.argv[1] if len(sys.argv) > 1 else "make"]()
