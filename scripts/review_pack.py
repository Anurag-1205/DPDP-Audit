"""Reading packs and sheet handling for the two human checks.

  python scripts/review_pack.py ladder            -> outputs/review/ladder/L<policy>.md (one per ladder)
  python scripts/review_pack.py spotcheck         -> outputs/review/spot_check/<case>.md (one per case)
  python scripts/review_pack.py copies NAME_A NAME_B
        -> data/benchmark/ladder/check_sheet_<NAME>.csv and data/spot_check/main_spot_check_<NAME>.csv,
           one private copy per checker (fill your own copy only; do not open the other one)
  python scripts/review_pack.py merge NAME_A NAME_B
        -> writes both checkers' answers into check_sheet.csv (checker_1/2 columns) and
           main_spot_check.csv (one row per flow and checker), then prints agreement
  python scripts/review_pack.py disagreements NAME_A NAME_B
        -> data/benchmark/ladder/disagreements.csv and data/spot_check/disagreements.csv: every row
           the two checkers answered differently, side by side, with an empty `agreed` column to
           fill in together

Packs go to outputs/ (git-ignored); only the filled sheets are versioned.
"""
import csv
import json
import sys
from pathlib import Path

from dpdp_audit.cases import BENCH, load_key
from dpdp_audit.paths import DATA, OUTPUTS

LADDER = BENCH / "ladder"
SPOT = DATA / "spot_check" / "main_spot_check.csv"
OUT = OUTPUTS / "review"


def ladder_pack():
    removed = {r["ladder_id"]: r for r in json.loads((LADDER / "removed_sentences.json").read_text())}
    rows = list(csv.DictReader((LADDER / "check_sheet.csv").open()))
    out = OUT / "ladder"
    out.mkdir(parents=True, exist_ok=True)
    for lid in sorted({r["ladder_id"] for r in rows}):
        rungs = {r["rung"]: r for r in rows if r["ladder_id"] == lid}
        info, first = removed[lid], rungs["clear"]
        base = (LADDER / "cases" / f"{lid}_r4" / "policy.txt").read_text()
        clear = (LADDER / "cases" / f"{lid}_r1" / "policy.txt").read_text()
        pos = clear.index(first["inserted_sentence"])
        context = (clear[max(0, pos - 400):pos] + "**" + first["inserted_sentence"] + "**"
                   + clear[pos + len(first["inserted_sentence"]):pos + len(first["inserted_sentence"]) + 400])
        practice = "shares it with" if info["kind"] == "sharing" else "collects it (first party)"
        lines = [
            f"# {lid} — {info['kind']} of {info['data_type']}",
            "",
            f"**App flow:** the app {practice} `{first['recipient']}`; data type **{info['data_type']}**.",
            "",
            "## What to check",
            "1. **Deleted rung (r4) = base policy.** Read the whole base policy below. It must NOT disclose "
            f"this flow: no sentence that says the company {'shares' if info['kind'] == 'sharing' else 'collects'} "
            f"{info['data_type']} (or personal information in general) — otherwise r4 is not 'omitted'. "
            "The flagged sentences are the likeliest problems.",
            "2. **Each inserted sentence** must, in the base policy, give the gold label: r1 clear, r2 "
            "incorrect (contradiction), r3 vague. Also check it reads naturally where it is placed.",
            "",
            "## Rungs",
            "| case | rung | gold label | inserted sentence |",
            "|---|---|---|---|",
        ] + [f"| {rungs[r]['case_id']} | {r} | {rungs[r]['gold_label']} | {rungs[r]['inserted_sentence'] or '(none)'} |"
             for r in ("clear", "explicit", "vague", "deleted")] + [
            "",
            "## Insertion point (r1 shown, inserted sentence in bold)",
            "> " + context.replace("\n", "\n> "),
            "",
            f"## Residual flags in the base policy ({len(info['residual_flags'])})",
            "TYPE = names the data type next to a practice verb; GENERIC = generic data next to a sharing word.",
            "",
        ] + [f"- {f}" for f in info["residual_flags"]] + [
            "",
            f"## Removed from the original policy ({len(info['removed'])} sentences)",
            "",
        ] + [f"- {s}" for s in info["removed"]] + [
            "",
            "## Base policy (r4, full text)",
            "",
            base,
        ]
        (out / f"{lid}.md").write_text("\n".join(lines))
    print(f"{len(removed)} ladder packs in {out}")


def spot_pack():
    rows = list(csv.DictReader(SPOT.open()))
    out = OUT / "spot_check"
    out.mkdir(parents=True, exist_ok=True)
    for cid in sorted({r["case_id"] for r in rows}):
        flows = [r for r in rows if r["case_id"] == cid]
        key = load_key("main", cid)
        policy = (BENCH / "main" / "cases" / cid / "policy.txt").read_text()
        lines = [
            f"# {cid} ({key['kind']})",
            "",
            "## What to check",
            "For every flow: read the policy and decide whether the gold label and gold findings are right.",
            "- **clear**: the policy explicitly names this data type for this practice (collection by the "
            "company; for an SDK, sharing with that company/SDK for a stated purpose).",
            "- **vague**: only generic wording covers it ('personal information', 'partners').",
            "- **omitted**: nothing covers it. **incorrect**: the policy says it does NOT do this.",
            "- Also check the purpose (stated for this data type?), retention ('Indefinitely' in the app vs "
            "a limit in the policy) and children (child-directed app sending data to an ad SDK).",
            "",
            "## Flows",
            "| flow | data type | recipient | purpose | retention | gold label | gold findings |",
            "|---|---|---|---|---|---|---|",
        ] + [f"| {r['flow_id']} | {r['data_type']} | {r['recipient']} | {r['purpose']} | {r['retention']} | "
             f"{r['gold_label']} | {r['gold_findings']} |" for r in flows] + [
            "",
            "## Sentences the annotators marked (a starting point, not the whole story)",
            "",
        ] + [f"- **{r['flow_id']}**: " + r["annotated_text"].replace(" || ", "\n  - ") for r in flows] + [
            "",
            "## Policy (full text)",
            "",
            policy,
        ]
        (out / f"{cid}.md").write_text("\n".join(lines))
    print(f"{len({r['case_id'] for r in rows})} spot-check packs in {out}")


def copies(names):
    for name in names:
        for src in (LADDER / "check_sheet.csv", SPOT):
            dst = src.with_name(f"{src.stem}_{name}.csv")
            if dst.exists():
                print(f"{dst} exists, left as it is")
                continue
            rows = list(csv.DictReader(src.open()))
            keep = [k for k in rows[0] if not k.startswith(("checker_2", "checker_1"))
                    and k not in ("checker", "agrees", "checker_label", "checker_gap", "notes")]
            extra = ["ok", "notes"] if "rung" in rows[0] else ["agrees", "checker_label", "checker_gap", "notes"]
            with dst.open("w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=keep + extra)
                w.writeheader()
                w.writerows({**{k: r[k] for k in keep}, **{e: "" for e in extra}} for r in rows)
            print("wrote", dst)


def merge(a, b):
    sheet = list(csv.DictReader((LADDER / "check_sheet.csv").open()))
    ra = {r["case_id"]: r for r in csv.DictReader((LADDER / f"check_sheet_{a}.csv").open())}
    rb = {r["case_id"]: r for r in csv.DictReader((LADDER / f"check_sheet_{b}.csv").open())}
    for r in sheet:
        r.update(checker_1=a, checker_1_ok=ra[r["case_id"]]["ok"], checker_2=b, checker_2_ok=rb[r["case_id"]]["ok"],
                 notes=" | ".join(x for x in (ra[r["case_id"]]["notes"], rb[r["case_id"]]["notes"]) if x))
    with (LADDER / "check_sheet.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0]))
        w.writeheader()
        w.writerows(sheet)
    ok = lambda v: v.strip().lower() in ("ok", "yes", "y", "1", "true")
    both = sum(ok(r["checker_1_ok"]) and ok(r["checker_2_ok"]) for r in sheet)
    agree = sum(ok(r["checker_1_ok"]) == ok(r["checker_2_ok"]) for r in sheet)
    print(f"ladder: {both}/{len(sheet)} rungs accepted by both; checkers agree on {agree}/{len(sheet)}")

    spot = list(csv.DictReader(SPOT.open()))
    merged = []
    for name in (a, b):
        mine = {(r["case_id"], r["flow_id"]): r for r in csv.DictReader(SPOT.with_name(f"{SPOT.stem}_{name}.csv").open())}
        for r in spot:
            m = mine[(r["case_id"], r["flow_id"])]
            merged.append({**r, "checker": name, "agrees": m["agrees"], "checker_label": m["checker_label"],
                           "checker_gap": m["checker_gap"], "notes": m["notes"]})
    with SPOT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(spot[0]))
        w.writeheader()
        w.writerows(merged)
    print(f"spot-check: {len(merged)} rows ({len(spot)} flows x 2 checkers) written; "
          "run `python scripts/spot_check.py score`")


def disagreements(a, b):
    ok = lambda v: v.strip().lower() in ("ok", "yes", "y", "1", "true")
    for src, key, col in ((LADDER / "check_sheet.csv", ("case_id",), "ok"), (SPOT, ("case_id", "flow_id"), "agrees")):
        mine = {n: {tuple(r[k] for k in key): r for r in csv.DictReader(src.with_name(f"{src.stem}_{n}.csv").open())}
                for n in (a, b)}
        base = [r for r in csv.DictReader(src.with_name(f"{src.stem}_{a}.csv").open())]
        rows = []
        for r in base:
            k = tuple(r[x] for x in key)
            ra, rb = mine[a][k], mine[b][k]
            if ok(ra[col]) != ok(rb[col]) or (col == "agrees" and not ok(ra[col]) and
                                               (ra["checker_label"], ra["checker_gap"]) != (rb["checker_label"], rb["checker_gap"])):
                extra = ["checker_label", "checker_gap"] if col == "agrees" else []
                rows.append({**{x: r[x] for x in r if x not in (col, "notes", *extra)},
                             **{f"{n}_{c}": m[c] for n, m in ((a, ra), (b, rb)) for c in (col, *extra, "notes")},
                             "agreed": "", "agreed_notes": ""})
        out = src.with_name("disagreements.csv")
        with out.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["case_id"])
            w.writeheader()
            w.writerows(rows)
        print(f"{out}: {len(rows)} rows to settle")


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "ladder":
        ladder_pack()
    elif cmd == "spotcheck":
        spot_pack()
    elif cmd == "copies":
        copies(sys.argv[2:])
    elif cmd == "merge":
        merge(sys.argv[2], sys.argv[3])
    elif cmd == "disagreements":
        disagreements(sys.argv[2], sys.argv[3])
