"""Cost per case of every LLM system on the main benchmark (AC-09.7, WP-5.1).

  python scripts/cost_table.py [--split main]

Reads the saved runs in results/runs/<split>/ (no GPU, no API calls). Per system, over all seeds:
model calls per case, prompt / output / thinking tokens per case and, where the run trace records
it, wall-clock seconds per case on the Kaggle T4 servers. Writes results/scores/cost_<split>.json.

What the runs do not record, and how the table treats it:
- B1, B2 and B4 runs store tokens but no time.
- The tagger ran once over every paragraph before the pipeline runs (scripts/tag_policies.py), so
  its cost is not in any run; the table gives the paragraphs per case it had to read instead.
- `*_rv` runs re-ran only the verifier, and their stored tokens add the new verifier call to the
  original run's tokens (scripts/reverify.py), so they double-count one verifier call. The table
  reports the as-run tokens and, separately, the tokens the re-run verifier added.
- Self-consistency rows (`*_sc`) are derived from the three seeds and cost the three runs together.
"""
import argparse
import json
from statistics import mean, median

from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.paths import RESULTS
from dpdp_audit.runs import load_runs, seeds_available

SYSTEMS = ["B1", "B2", "B4", "B5", "R0", "full", "full_finetuned", "full_v2", "full_v2_finetuned"]
REVERIFIED = ["full", "full_finetuned", "full_v2", "full_v2_finetuned"]
NO_TAGGER = {"B5"}   # B5 reads the whole policy; its config still names a tagger it does not use


def per_case(runs: list[dict]) -> dict:
    usage = [r.get("usage") or {} for r in runs]
    trace = [r.get("trace") or {} for r in runs]
    out = {"runs": len(runs),
           "prompt_tokens": mean(u.get("prompt", 0) or 0 for u in usage),
           "output_tokens": mean(u.get("output", 0) or 0 for u in usage),
           "thinking_tokens": mean(u.get("thoughts", 0) or 0 for u in usage)}
    calls = [t["llm_calls"] for t in trace if "llm_calls" in t]
    out["llm_calls"] = mean(calls) if calls else (1.0 if usage[0] else 0.0)
    secs = [t["seconds"] for t in trace if t.get("seconds") is not None]
    out["seconds_mean"] = mean(secs) if secs else None
    out["seconds_median"] = median(secs) if secs else None
    paras = [t["paragraphs"] for t in trace if "paragraphs" in t]
    out["paragraphs_tagged"] = mean(paras) if paras else None
    return out


def load_all(split: str, system: str, ids: list[str]) -> list[dict]:
    runs = []
    for seed in seeds_available(split, system):
        outs = load_runs(split, system, seed, ids)
        if outs is None:
            raise SystemExit(f"{split}/{system}/seed{seed}: runs missing")
        runs += outs
    return runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    args = ap.parse_args()
    ids = [load_case(d)["case_id"] for d in case_dirs(args.split)]
    out = {"split": args.split, "cases": len(ids), "systems": {}, "reverify_added": {}}
    for system in SYSTEMS:
        runs = load_all(args.split, system, ids)
        if not runs:
            continue
        res = per_case(runs)
        res["seeds"] = len(seeds_available(args.split, system))
        res["model"] = runs[0].get("model") if res["llm_calls"] else None
        if system in NO_TAGGER:
            res["paragraphs_tagged"] = None
        out["systems"][system] = res
    for system in REVERIFIED:
        base, rv = load_all(args.split, system, ids), load_all(args.split, f"{system}_rv", ids)
        if base and rv:
            out["reverify_added"][system] = {
                k: mean((b.get("usage") or {}).get(k, 0) for b in rv) - mean((b.get("usage") or {}).get(k, 0) for b in base)
                for k in ("prompt", "output")}
    (RESULTS / "scores" / f"cost_{args.split}.json").write_text(json.dumps(out, indent=1))

    fmt = lambda v, d=0: "—" if v is None else f"{v:,.{d}f}"
    print(f"{args.split}: {len(ids)} cases; per case, mean over every seed")
    print("| system | model | seeds | model calls | prompt tokens | output tokens | thinking tokens "
          "| seconds (mean / median) | paragraphs tagged |")
    print("|---|---|---|---|---|---|---|---|---|")
    for s, r in out["systems"].items():
        secs = "—" if r["seconds_mean"] is None else f"{r['seconds_mean']:.0f} / {r['seconds_median']:.0f}"
        print(f"| {s} | {r['model'] or 'no LLM'} | {r['seeds']} | {fmt(r['llm_calls'], 1)} | {fmt(r['prompt_tokens'])} "
              f"| {fmt(r['output_tokens'])} | {fmt(r['thinking_tokens']) if r['thinking_tokens'] else '—'} | {secs} "
              f"| {fmt(r['paragraphs_tagged'])} |")
    print("\nre-run verifier (`*_rv`), tokens added per case:")
    for s, r in out["reverify_added"].items():
        print(f"  {s:18} prompt +{r['prompt']:,.0f}, output +{r['output']:,.0f}")


if __name__ == "__main__":
    main()
