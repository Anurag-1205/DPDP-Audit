"""Run single-pass baselines on every case of a split.

  python scripts/run_baselines.py --systems B1 B2 --seeds 0 1 2 [--split main] [--limit 5]
        [--shard 0/2] [--deadline-min 600] [--redo-failed]

Jobs run seed first (seed 0 of every system, then seed 1, ...), so a partial run still
gives complete first-seed scores. Existing outputs are skipped; --redo-failed re-runs
outputs whose model call failed (e.g. timed out). --shard i/n runs every n-th case, so
two model servers can share the work. --deadline-min stops starting new jobs after that
many minutes. The backend comes from LLM_BACKEND (gemini | openai); B4 forces Gemini.
"""
import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor

from dpdp_audit import baselines
from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.llm import LLM
from dpdp_audit.runs import run_path, save_run
from dpdp_audit.tools import get_flows


def needs_run(split, system, seed, case_id, redo_failed):
    p = run_path(split, system, seed, case_id)
    if not p.exists():
        return True
    return redo_failed and (json.loads(p.read_text()).get("parse_error") or "").startswith("call failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--systems", nargs="+", default=["B1", "B2"])
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--split", default="main")
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--deadline-min", type=float, default=None)
    ap.add_argument("--redo-failed", action="store_true")
    args = ap.parse_args()

    shard, n_shards = map(int, args.shard.split("/"))
    cases = [load_case(d) for d in case_dirs(args.split)][: args.limit]
    cases = [c for i, c in enumerate(cases) if i % n_shards == shard]
    llms = {s: (LLM(backend="gemini") if s == "B4" else LLM()) for s in args.systems}
    jobs = [(system, c, seed) for seed in args.seeds for system in args.systems for c in cases
            if needs_run(args.split, system, seed, c["case_id"], args.redo_failed)]
    print(f"shard {args.shard}: {len(jobs)} runs to do", flush=True)
    t0 = time.time()
    done = [0]

    def work(job):
        system, case, seed = job
        if args.deadline_min and time.time() - t0 > args.deadline_min * 60:
            return "skipped: deadline"
        llm = llms[system]
        try:
            out = baselines.run("B2" if system == "B4" else system, case, llm, seed=seed)
        except Exception as exc:  # e.g. prompt longer than the context window, or a timeout
            flow_ids = [f["flow_id"] for f in get_flows(case["app_dir"])]
            out = dict(baselines.normalise({}, flow_ids), case_id=case["case_id"], seed=seed,
                       model=llm.model, parse_error=f"call failed: {exc}"[:500])
        out["system"] = system
        save_run(args.split, system, seed, out)
        done[0] += 1
        if done[0] % 10 == 0:
            print(f"shard {args.shard}: {done[0]}/{len(jobs)} runs in {time.time() - t0:.0f}s", flush=True)
        return out.get("parse_error")

    with ThreadPoolExecutor(args.workers) as pool:
        results = list(pool.map(work, jobs))
    skipped = sum(1 for r in results if r == "skipped: deadline")
    failed = sum(1 for r in results if r and r.startswith("call failed"))
    unparsed = sum(1 for r in results if r and not r.startswith(("call failed", "skipped")))
    print(f"shard {args.shard}: finished in {time.time() - t0:.0f}s; {failed} failed calls, "
          f"{unparsed} unparseable replies, {skipped} skipped at the deadline", flush=True)


if __name__ == "__main__":
    main()
