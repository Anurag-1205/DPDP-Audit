"""Run the DPDP-Audit pipeline (full or an ablation) on every case of a split.

  python scripts/run_pipeline.py --configs full --seeds 0 [--split main] [--limit 5] [--cases ID ...]
        [--shard 0/2] [--workers 4] [--deadline-min 600] [--redo-failed] [--pilot results/pipeline_pilot.json]

Same failure handling as the baselines: jobs run seed first, existing runs are skipped,
a failed call is saved as a failed run and --redo-failed re-runs it, and no new job starts
after --deadline-min. Runs go to results/runs/<split>/<config>/seed<k>/. --pilot writes
seconds and LLM calls per run and extrapolates them to the full run budget.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dpdp_audit.baselines import normalise
from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.llm import LLM
from dpdp_audit.pipeline import get_config, run_case
from dpdp_audit.pipeline.claims import load_claims
from dpdp_audit.runs import run_path, save_run
from dpdp_audit.tools import get_flows


def needs_run(split, system, seed, case_id, redo_failed):
    p = run_path(split, system, seed, case_id)
    if not p.exists():
        return True
    return redo_failed and (json.loads(p.read_text()).get("parse_error") or "").startswith("call failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--configs", nargs="+", default=["full"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--split", default="main")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--cases", nargs="+", default=None)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--deadline-min", type=float, default=None)
    ap.add_argument("--redo-failed", action="store_true")
    ap.add_argument("--pilot", default=None, help="write timing per run to this JSON file")
    args = ap.parse_args()

    shard, n_shards = map(int, args.shard.split("/"))
    cases = [load_case(d) for d in case_dirs(args.split)]
    if args.cases:
        cases = [c for c in cases if c["case_id"] in set(args.cases)]
    cases = cases[: args.limit]
    cases = [c for i, c in enumerate(cases) if i % n_shards == shard]
    cfgs = {name: get_config(name) for name in args.configs}
    claims = {t: load_claims(t) for t in {c.tagger for c in cfgs.values()}}
    for t, idx in claims.items():
        print(f"tagger {t}: {len(idx)} tagged paragraphs", flush=True)
    any_cfg = next(iter(cfgs.values()))
    llms = {name: LLM(temperature=c.reviewer_temperature, max_tokens=c.reviewer_max_tokens) for name, c in cfgs.items()}
    llm = llms[next(iter(cfgs))]
    verifier_llm = LLM(temperature=any_cfg.verifier_temperature, max_tokens=any_cfg.verifier_max_tokens)
    jobs = [(name, c, seed) for seed in args.seeds for name in args.configs for c in cases
            if needs_run(args.split, name, seed, c["case_id"], args.redo_failed)]
    print(f"shard {args.shard}: {len(jobs)} runs to do", flush=True)
    t0 = time.time()
    done, timings = [0], []

    def work(job):
        name, case, seed = job
        if args.deadline_min and time.time() - t0 > args.deadline_min * 60:
            return "skipped: deadline"
        cfg = cfgs[name]
        start = time.time()
        try:
            out = run_case(case, llms[name], seed, cfg, claims_index=claims[cfg.tagger], verifier_llm=verifier_llm)
        except Exception as exc:  # e.g. prompt longer than the context window, or a timeout
            flow_ids = [f["flow_id"] for f in get_flows(case["app_dir"])]
            out = dict(normalise({}, flow_ids), case_id=case["case_id"], system=name, seed=seed,
                       model=llm.model, tagger=cfg.tagger, parse_error=f"call failed: {exc}"[:500])
        save_run(args.split, name, seed, out)
        timings.append({"case_id": case["case_id"], "config": name, "seed": seed,
                        "seconds": round(time.time() - start, 2),
                        "llm_calls": out.get("trace", {}).get("llm_calls"),
                        "candidates": len(out.get("trace", {}).get("candidates", [])),
                        "failed": bool(out.get("parse_error"))})
        done[0] += 1
        if done[0] % 10 == 0:
            print(f"shard {args.shard}: {done[0]}/{len(jobs)} runs in {time.time() - t0:.0f}s", flush=True)
        return out.get("parse_error")

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(work, jobs))
    skipped = sum(1 for r in results if r == "skipped: deadline")
    failed = sum(1 for r in results if r and r.startswith("call failed"))
    wall = time.time() - t0
    print(f"shard {args.shard}: finished in {wall:.0f}s; {failed} failed calls, {skipped} skipped at the deadline",
          flush=True)
    if args.pilot and timings:
        n = len(timings)
        per_run = sum(t["seconds"] for t in timings) / n
        calls = [t["llm_calls"] for t in timings if t["llm_calls"] is not None]
        report = {
            "runs": n, "workers": args.workers, "wall_seconds": round(wall, 1),
            "mean_seconds_per_run": round(per_run, 2),
            "mean_llm_calls_per_run": round(sum(calls) / len(calls), 2) if calls else None,
            "wall_seconds_per_run": round(wall / n, 2),
            # one server per GPU, two GPUs, the same worker count per server
            "extrapolated_hours": {k: round(v * wall / n / 2 / 3600, 2) for k, v in
                                   {"main_1_seed": 102, "main_3_seeds": 306, "ladder_3_seeds": 420,
                                    "ablations_5x_main": 510}.items()},
            "runs_detail": timings,
        }
        Path(args.pilot).parent.mkdir(parents=True, exist_ok=True)
        Path(args.pilot).write_text(json.dumps(report, indent=1))
        print(json.dumps({k: v for k, v in report.items() if k != "runs_detail"}, indent=1), flush=True)


if __name__ == "__main__":
    main()
