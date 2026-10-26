"""Score tagger predictions against the held-out OPP-115 segments.

  python scripts/eval_tagger.py --gold results/tagger/heldout.jsonl \
      --pred S3=results/tagger/S3_pred.jsonl B3=results/tagger/B3_pred.jsonl

Writes results/scores/tagger.json and prints category F1 per system.
"""
import argparse
import json

from dpdp_audit.paths import RESULTS
from dpdp_audit.tagger_data import CATEGORIES
from dpdp_audit.tagger_eval import evaluate


def read(path):
    return [json.loads(line) for line in open(path) if line.strip()]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", required=True)
    ap.add_argument("--pred", nargs="+", required=True, help="SYSTEM=path.jsonl")
    args = ap.parse_args()
    gold = read(args.gold)
    results = {}
    for item in args.pred:
        name, path = item.split("=", 1)
        results[name] = evaluate(gold, read(path))
    out = RESULTS / "scores" / "tagger.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=1))
    names = list(results)
    print("| category | " + " | ".join(names) + " |")
    print("|---" * (len(names) + 1) + "|")
    for c in CATEGORIES:
        print(f"| {c} | " + " | ".join(f"{results[n]['per_category'][c]['f1']:.3f}" for n in names) + " |")
    print("| **macro-F1** | " + " | ".join(f"**{results[n]['macro_f1']:.3f}**" for n in names) + " |")
    print("| micro-F1 | " + " | ".join(f"{results[n]['micro_f1']:.3f}" for n in names) + " |")
