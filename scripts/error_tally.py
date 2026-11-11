"""Where the headline system goes wrong, for the failure analysis (AC-09.7, WP-5.1).

  python scripts/error_tally.py

Reads the committed runs, answer keys and confidence exports; no GPU. For `full_v2_finetuned_rv`:
1. Main, seeds 0-2 summed, per gap type: gold gaps, reported true and false positives, misses,
   findings sent to human review (`uncertain`) and how many of those were real gaps, and false
   alarms on the compliant controls. Matching is score.match_case, as in every score file.
2. Disclosure-label confusion (gold -> majority label over the seeds) on main and on the 110
   accepted ladder rungs (results/confidence/), and on the 61 real flows against the settled
   labels (majority over the seeds' runs).
Every off-diagonal cell lists up to 8 (case, flow) examples to pick worked cases from.
Writes results/scores/errors.json.
"""
import json
from collections import Counter, defaultdict

from dpdp_audit import score
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.gaps import LABELS
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import load_runs, seeds_available

SYSTEM = "full_v2_finetuned_rv"      # findings (the verifier matters)
LABEL_SYSTEM = "full_v2_finetuned"   # labels come from the reviewers, so the `_rv` re-run does not change them
EXAMPLES = 8


def gap_tally(split: str = "main") -> dict:
    ids = [load_case(d)["case_id"] for d in case_dirs(split)]
    keys = {c: load_key(split, c) for c in ids}
    rows = defaultdict(Counter)
    for seed in seeds_available(split, SYSTEM):
        for out in load_runs(split, SYSTEM, seed, ids):
            key = keys[out["case_id"]]
            for g in key["findings"]:
                rows[g["gap_type"]]["gold"] += 1
            missed = []
            for pred, gold in score.match_case(key, out):
                if pred is not None and gold is not None:
                    rows[gold["gap_type"]]["tp"] += 1
                elif pred is not None:
                    rows[pred["gap_type"]]["fp"] += 1
                    if key["kind"] == "control":
                        rows[pred["gap_type"]]["fp_on_controls"] += 1
                else:
                    rows[gold["gap_type"]]["fn"] += 1
                    missed.append(gold)
            for f in out.get("findings", []):
                if not f.get("uncertain"):
                    continue
                rows[f["gap_type"]]["sent_to_review"] += 1
                hit = next((g for g in missed if g["data_type"] == f["data_type"] and g["gap_type"] == f["gap_type"]), None)
                if hit is not None:
                    missed.remove(hit)
                    rows[f["gap_type"]]["review_was_real_gap"] += 1
    return {gt: dict(c) for gt, c in sorted(rows.items())}


def confusion(pairs: list[tuple[str, str, str]]) -> dict:
    """pairs: (gold, predicted, example id) -> counts and examples per gold -> predicted cell."""
    cells = defaultdict(lambda: {"n": 0, "examples": []})
    for gold, pred, ex in pairs:
        c = cells[f"{gold} -> {pred}"]
        c["n"] += 1
        if gold != pred and len(c["examples"]) < EXAMPLES:
            c["examples"].append(ex)
    right = sum(1 for g, p, _ in pairs if g == p)
    return {"n": len(pairs), "accuracy": right / len(pairs) if pairs else None,
            "cells": dict(sorted(cells.items()))}


def from_confidence(split: str) -> list[tuple[str, str, str]]:
    flows = json.loads((RESULTS / "confidence" / f"{split}.json").read_text())[LABEL_SYSTEM]["flows"]
    return [(r["gold"], r["label"], f"{r['case_id']} {r['flow_id']}") for r in flows if r.get("accepted", True)]


def real_flows(system: str = SYSTEM) -> list[tuple[str, str, str]]:
    ids = [load_case(d)["case_id"] for d in case_dirs("real_flows")]
    votes = defaultdict(list)
    for seed in seeds_available("real_flows", system):
        for out in load_runs("real_flows", system, seed, ids) or []:
            for fid, lab in out.get("flow_labels", {}).items():
                votes[out["case_id"], fid].append(lab.get("label", "clear") if isinstance(lab, dict) else lab)
    pairs = []
    for cid in ids:
        for fid, gold in load_key("real_flows", cid)["flow_labels"].items():
            v = votes.get((cid, fid)) or ["clear"]
            pred = max(LABELS, key=lambda l: (v.count(l), -LABELS.index(l)))   # majority; ties to the earlier label
            pairs.append((gold, pred, f"{cid} {fid}"))
    return pairs


def main():
    out = {"system": SYSTEM, "label_system": LABEL_SYSTEM,
           "gaps_main": gap_tally("main"),
           "labels": {"main": confusion(from_confidence("main")),
                      "ladder_accepted": confusion(from_confidence("ladder")),
                      "real_flows": confusion(real_flows())}}
    (RESULTS / "scores" / "errors.json").write_text(json.dumps(out, indent=1))

    print(f"{SYSTEM}, main, seeds {seeds_available('main', SYSTEM)} summed")
    print("| gap type | gold | reported right | reported wrong | of which on controls | missed "
          "| sent to review | review was a real gap |")
    print("|---|---|---|---|---|---|---|---|")
    for gt, c in out["gaps_main"].items():
        print(f"| {gt} | {c.get('gold', 0)} | {c.get('tp', 0)} | {c.get('fp', 0)} | {c.get('fp_on_controls', 0)} "
              f"| {c.get('fn', 0)} | {c.get('sent_to_review', 0)} | {c.get('review_was_real_gap', 0)} |")
    for name, conf in out["labels"].items():
        print(f"\nlabels, {name}: {conf['n']} flows, accuracy {conf['accuracy']:.3f}; errors (gold -> predicted):")
        for cell, c in sorted(conf["cells"].items(), key=lambda x: -x[1]["n"]):
            g, p = cell.split(" -> ")
            if g != p:
                print(f"  {cell:22} {c['n']:3}   e.g. {', '.join(c['examples'][:3])}")


if __name__ == "__main__":
    main()
