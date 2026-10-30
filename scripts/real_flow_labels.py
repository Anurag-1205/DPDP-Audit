"""Two-person labels for the real-flow sample (SPEC-08, AC-08.2; guide: docs/real-flow-labelling.md).

  python scripts/real_flow_labels.py pack              -> outputs/review/real_flows/<package>.md (one per app)
                                                          and outputs/review/real_flows_practice/<case>.md
  python scripts/real_flow_labels.py copies NAME_A NAME_B
        -> data/real_flows/labels_<NAME>.csv (the 61 flows) and practice_<NAME>.csv (8 practice flows),
           one private copy per labeller (fill your own copy only; do not open the other one)
  python scripts/real_flow_labels.py practice NAME     -> your practice answers against the known labels
  python scripts/real_flow_labels.py merge NAME_A NAME_B
        -> both labels into data/real_flows/sample.csv; agreement and Cohen's kappa
  python scripts/real_flow_labels.py disagreements NAME_A NAME_B
        -> data/real_flows/disagreements.csv: every flow labelled differently, with an empty `agreed`
           column to fill in together
  python scripts/real_flow_labels.py settle            -> settled_label in sample.csv (agreed labels,
                                                          and the `agreed` column for the rest)
  python scripts/real_flow_labels.py keys              -> data/benchmark/real_flows/answer_keys/ from the
                                                          settled labels only

The practice flows are accepted ladder rungs (2 per label), whose correct label is known; they are not
part of the sample. Packs go to outputs/ (git-ignored); only the filled sheets are versioned.
"""
import csv
import json
import random
import sys
from collections import Counter

from dpdp_audit.cases import BENCH, load_key
from dpdp_audit.paths import DATA, OUTPUTS

SRC = DATA / "real_flows"
SAMPLE = SRC / "sample.csv"
CASES = BENCH / "real_flows" / "cases"
OUT = OUTPUTS / "review"
LABELS = ["clear", "vague", "omitted", "incorrect"]
LEVEL = {"vague": "vague", "omitted": "omission", "incorrect": "explicit"}
SHEET = ["package", "flow_id", "data_type", "practice", "recipient_name", "label", "paragraph", "sentence", "notes"]


def sdk_names() -> dict[str, str]:
    return {r["sdk_id"]: f"{r['name']} ({r['vendor']})" for r in csv.DictReader((DATA / "tools" / "sdk_table.csv").open())}


def describe(recipient: str, names: dict[str, str]) -> tuple[str, str]:
    if recipient == "first_party":
        return "collects (the app's own company)", "the app's own company"
    return "shares with an SDK", names.get(recipient, recipient)


def numbered(policy: str) -> str:
    paras = [p for p in policy.split("\n\n") if p.strip()]
    return "\n\n".join(f"**[P{i}]** {p}" for i, p in enumerate(paras, 1))


def practice_cases() -> dict[str, str]:
    """{P1..P8: ladder case id}: 2 accepted ladder rungs per label, picked and shuffled with seed 13.
    The neutral ids keep the rung (and so the answer) out of the file names."""
    from dpdp_audit.ladder import accepted_cases
    rows = [r for r in csv.DictReader((BENCH / "ladder" / "check_sheet.csv").open()) if r["case_id"] in accepted_cases()]
    rng = random.Random(13)
    out = []
    for label in LABELS:
        pool = sorted(r["case_id"] for r in rows if r["gold_label"] == label)
        out += rng.sample(pool, 2)
    rng.shuffle(out)
    return {f"P{i}": cid for i, cid in enumerate(out, 1)}


def pack():
    names = sdk_names()
    rows = list(csv.DictReader(SAMPLE.open()))
    out = OUT / "real_flows"
    out.mkdir(parents=True, exist_ok=True)
    for pkg in sorted({r["package"] for r in rows}):
        meta = json.loads((CASES / pkg / "meta.json").read_text())
        flows = [r for r in rows if r["package"] == pkg]
        lines = [f"# {pkg}", "",
                 f"Policy: {meta['policy_url']} (archived copy of {meta['snapshot'][:4]}-{meta['snapshot'][4:6]}-"
                 f"{meta['snapshot'][6:8]}). Rules: docs/real-flow-labelling.md.", "",
                 "## Flows to label", "",
                 "| flow | the app sends | to | what to look for |", "|---|---|---|---|"]
        for r in flows:
            practice, who = describe(r["recipient"], names)
            look = ("a sentence where the company collects this data" if r["recipient"] == "first_party"
                    else f"a sentence about sharing this data with {who.split(' (')[0]} or its company")
            lines.append(f"| {r['flow_id']} | {r['data_type']} | {who} | {look} |")
        lines += ["", "## Policy (paragraphs numbered)", "",
                  numbered((CASES / pkg / "policy.txt").read_text())]
        (out / f"{pkg}.md").write_text("\n".join(lines))
    pout = OUT / "real_flows_practice"
    pout.mkdir(parents=True, exist_ok=True)
    for pid, cid in practice_cases().items():
        flow = json.loads((BENCH / "ladder" / "cases" / cid / "app" / "dataflows.json").read_text())[0]
        _, who = describe(flow["recipient"], names)
        lines = [f"# Practice {pid}", "", "| flow | the app sends | to |", "|---|---|---|",
                 f"| f1 | {flow['data_type']} | {who} |", "", "## Policy (paragraphs numbered)", "",
                 numbered((BENCH / "ladder" / "cases" / cid / "policy.txt").read_text())]
        (pout / f"{pid}.md").write_text("\n".join(lines))
    print(f"{len({r['package'] for r in rows})} app packs in {out}; 8 practice packs in {pout}")


def copies(names_):
    names = sdk_names()
    sample = list(csv.DictReader(SAMPLE.open()))
    for name in names_:
        for dst, rows in ((SRC / f"labels_{name}.csv", sample), (SRC / f"practice_{name}.csv", None)):
            if dst.exists():
                print(f"{dst} exists, left as it is")
                continue
            if rows is None:
                rows = []
                for pid, cid in practice_cases().items():
                    f = json.loads((BENCH / "ladder" / "cases" / cid / "app" / "dataflows.json").read_text())[0]
                    rows.append({"package": pid, "flow_id": "f1", "data_type": f["data_type"], "recipient": f["recipient"]})
            with dst.open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=SHEET)
                w.writeheader()
                for r in rows:
                    practice, who = describe(r["recipient"], names)
                    w.writerow({"package": r["package"], "flow_id": r["flow_id"], "data_type": r["data_type"],
                                "practice": practice, "recipient_name": who})
            print("wrote", dst)


def read_labels(name: str, kind: str = "labels") -> dict[tuple[str, str], dict]:
    rows = {(r["package"], r["flow_id"]): r for r in csv.DictReader((SRC / f"{kind}_{name}.csv").open())}
    bad = [k for k, r in rows.items() if r["label"].strip().lower() not in LABELS]
    if bad:
        raise SystemExit(f"{kind}_{name}.csv: {len(bad)} rows without a valid label (one of {LABELS}), e.g. {bad[0]}")
    return rows


def practice(name):
    mine = read_labels(name, "practice")
    ids = practice_cases()
    right = 0
    for (pid, _), r in sorted(mine.items(), key=lambda x: int(x[0][0][1:])):
        gold = load_key("ladder", ids[pid])["flow_labels"]["f1"]
        ok = r["label"].strip().lower() == gold
        right += ok
        print(f"{pid:4} you: {r['label']:9} correct: {gold:9} {'ok' if ok else 'DIFFERENT: re-read the guide'}")
    print(f"{right}/{len(mine)} as expected")


def kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[l] * cb[l] for l in set(a) | set(b)) / n / n
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def merge(a, b):
    ra, rb = read_labels(a), read_labels(b)
    rows = list(csv.DictReader(SAMPLE.open()))
    for r in rows:
        k = (r["package"], r["flow_id"])
        r.update(labeller_1_label=ra[k]["label"].strip().lower(), labeller_1_note=f"{a}: {ra[k]['notes']}".strip(": "),
                 labeller_2_label=rb[k]["label"].strip().lower(), labeller_2_note=f"{b}: {rb[k]['notes']}".strip(": "))
    with SAMPLE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    la, lb = [r["labeller_1_label"] for r in rows], [r["labeller_2_label"] for r in rows]
    agree = sum(x == y for x, y in zip(la, lb))
    print(f"{agree}/{len(rows)} flows labelled the same ({agree / len(rows):.0%}); Cohen's kappa {kappa(la, lb):.2f}")
    print(f"{a}: {dict(Counter(la))}\n{b}: {dict(Counter(lb))}")


def disagreements(a, b):
    ra, rb = read_labels(a), read_labels(b)
    rows = [k for k in ra if ra[k]["label"].strip().lower() != rb[k]["label"].strip().lower()]
    path = SRC / "disagreements.csv"
    with path.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["package", "flow_id", "data_type", "recipient_name", f"{a}_label", f"{a}_sentence", f"{a}_notes",
                    f"{b}_label", f"{b}_sentence", f"{b}_notes", "agreed", "reason"])
        for k in rows:
            x, y = ra[k], rb[k]
            w.writerow([*k, x["data_type"], x["recipient_name"], x["label"], x["sentence"], x["notes"],
                        y["label"], y["sentence"], y["notes"], "", ""])
    print(f"{len(rows)} disagreements written to {path}; fill `agreed` and `reason` together")


def settle():
    rows = list(csv.DictReader(SAMPLE.open()))
    path = SRC / "disagreements.csv"
    agreed = {(r["package"], r["flow_id"]): r for r in csv.DictReader(path.open())} if path.exists() else {}
    missing = []
    for r in rows:
        k = (r["package"], r["flow_id"])
        if r["labeller_1_label"] == r["labeller_2_label"] and r["labeller_1_label"] in LABELS:
            r["settled_label"], r["settled_note"] = r["labeller_1_label"], "both labellers"
        elif k in agreed and agreed[k]["agreed"].strip().lower() in LABELS:
            r["settled_label"], r["settled_note"] = agreed[k]["agreed"].strip().lower(), agreed[k]["reason"]
        else:
            missing.append(k)
    if missing:
        raise SystemExit(f"{len(missing)} flows have no settled label yet, e.g. {missing[0]}")
    with SAMPLE.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"settled: {dict(Counter(r['settled_label'] for r in rows))}")


def keys():
    sections = {r["gap_type"]: r["gold_sections"].split(";") for r in csv.DictReader((DATA / "dpdp" / "gap_to_section.csv").open())}
    rows = list(csv.DictReader(SAMPLE.open()))
    if not all(r["settled_label"] in LABELS for r in rows):
        raise SystemExit("run `settle` first: some flows have no settled label")
    out = BENCH / "real_flows" / "answer_keys"
    out.mkdir(parents=True, exist_ok=True)
    for pkg in sorted({r["package"] for r in rows}):
        flows = [r for r in rows if r["package"] == pkg]
        key = {"case_id": pkg, "policy_id": pkg, "kind": "real",
               "findings": [{"flow_id": r["flow_id"], "data_type": r["data_type"], "gap_type": r["gap_type"],
                             "level": LEVEL[r["settled_label"]], "sections": sections[r["gap_type"]]}
                            for r in flows if r["settled_label"] != "clear"],
               "flow_labels": {r["flow_id"]: r["settled_label"] for r in flows},
               "flow_gap_types": {r["flow_id"]: r["gap_type"] for r in flows}}
        (out / f"{pkg}.json").write_text(json.dumps(key, indent=1))
    print(f"{len({r['package'] for r in rows})} answer keys in {out}")


if __name__ == "__main__":
    cmd, args = sys.argv[1], sys.argv[2:]
    {"pack": lambda: pack(), "copies": lambda: copies(args), "practice": lambda: practice(args[0]),
     "merge": lambda: merge(*args), "disagreements": lambda: disagreements(*args), "settle": lambda: settle(),
     "keys": lambda: keys()}[cmd]()
