"""Score taggers against the held-out OPP-115 segments.

  python scripts/eval_tagger.py --gold results/tagger/heldout.jsonl \
      --pred S3=results/tagger/S3_pred.jsonl B3=results/tagger/B3_pred.jsonl \
      [--claims prompted finetuned]

--pred scores category predictions (one JSON line per segment). --claims scores a claims tagger
of the pipeline (results/tagger/claims/<name>.jsonl): category F1 as above, plus tuple F1 for
(category, data type, does/does not) and (category, data type, third party) against the OPP-115
annotations (needs data/raw/OPP-115). Results are merged into results/scores/tagger.json.
"""
import argparse
import json

from dpdp_audit.paths import RESULTS
from dpdp_audit.tagger_data import CATEGORIES
from dpdp_audit.tagger_eval import evaluate, evaluate_tuples


def read(path):
    return [json.loads(line) for line in open(path) if line.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", nargs="*", default=[], help="SYSTEM=path.jsonl")
    ap.add_argument("--claims", nargs="*", default=[], help="claims taggers, e.g. prompted finetuned")
    ap.add_argument("--s4", action="store_true", help="also score PolicyLint and PoliGraph statements (S4)")
    args = ap.parse_args()
    gold = read(args.gold)
    results = {}
    for item in args.pred:
        name, path = item.split("=", 1)
        results[name] = evaluate(gold, read(path))
    if args.claims:
        from dpdp_audit.pipeline.claims import load_claims
        from dpdp_audit.tagger_data import claims_examples
        gold_claims = claims_examples("heldout")
        if not gold_claims:   # an empty gold set would score every tagger 0.0 without an error
            raise SystemExit("no held-out OPP-115 segments found; run scripts/download_opp115.sh first")
        for name in args.claims:
            index = load_claims(name)
            pred = [{"policy_id": g["policy_id"], "segment_id": g["segment_id"],
                     "categories": index[g["hash"]]["categories"], "claims": index[g["hash"]]["claims"]}
                    for g in gold_claims if g["hash"] in index]
            if len(pred) < len(gold_claims):
                raise SystemExit(f"claims_{name}: {len(gold_claims) - len(pred)} of {len(gold_claims)} "
                                 "held-out segments have no claims; re-run the tagger")
            r = evaluate(gold_claims, pred)
            r.update(evaluate_tuples(gold_claims, pred))
            r["unparseable"] = sum(1 for g in gold_claims if index.get(g["hash"], {}).get("parse_error"))
            results[f"claims_{name}"] = r
    s4_results = {}
    if args.s4:   # S4: tool statements as claims, tuple F1 only (the tools give no OPP-115 categories)
        from dpdp_audit import s4
        from dpdp_audit.tagger_data import claims_examples
        gold_claims = claims_examples("heldout")
        if not gold_claims:
            raise SystemExit("no held-out OPP-115 segments found; run scripts/download_opp115.sh first")
        keys = {(str(g["policy_id"]), int(g["segment_id"])) for g in gold_claims}
        pl, pl_stats = s4.policylint_claims()
        if not keys <= set(pl):
            raise SystemExit(f"S4 PolicyLint: {len(keys - set(pl))} held-out segments missing from {s4.POLICYLINT}")
        pg, pg_stats = s4.poligraph_claims(gold_claims)
        if pg_stats["policies"] < len({k[0] for k in keys}):
            print(f"S4 PoliGraph: graphs for {pg_stats['policies']} of {len({k[0] for k in keys})} policies "
                  "(a missing policy predicts no tuple)")
        for name, claims, stats in (("S4_policylint", pl, pl_stats), ("S4_poligraph", pg, pg_stats)):
            r = evaluate_tuples(gold_claims, s4.as_predictions(gold_claims, claims))
            r["stats"] = stats
            s4_results[name] = r
    out = RESULTS / "scores" / "tagger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    merged = json.loads(out.read_text()) if out.exists() else {}
    merged.update(results)
    merged.update(s4_results)
    out.write_text(json.dumps(merged, indent=1))
    names = list(results)
    print("| category | " + " | ".join(names) + " |")
    print("|---" * (len(names) + 1) + "|")
    for c in CATEGORIES:
        print(f"| {c} | " + " | ".join(f"{results[n]['per_category'][c]['f1']:.3f}" for n in names) + " |")
    print("| **macro-F1** | " + " | ".join(f"**{results[n]['macro_f1']:.3f}**" for n in names) + " |")
    print("| micro-F1 | " + " | ".join(f"{results[n]['micro_f1']:.3f}" for n in names) + " |")
    for t in ("tuple_does", "tuple_third_party"):
        if any(t in results[n] for n in names):
            print(f"| {t} F1 | " + " | ".join(f"{results[n][t]['f1']:.3f}" if t in results[n] else "–"
                                             for n in names) + " |")
    for n, r in s4_results.items():
        print(f"{n}: tuple_does F1 {r['tuple_does']['f1']:.3f} (P {r['tuple_does']['precision']:.3f}, "
              f"R {r['tuple_does']['recall']:.3f}); tuple_third_party F1 {r['tuple_third_party']['f1']:.3f}; "
              f"{r['stats']}")
