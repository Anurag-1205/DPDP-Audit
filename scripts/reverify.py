"""Re-run only the evidence verifier on saved pipeline runs, with the robust reply reader.

  python scripts/reverify.py --split main --systems full full_v2_finetuned --seeds 0 1 2 [--shard 0/2]

For every saved run of SYSTEM it rebuilds the verifier's input (the findings the frozen verifier
kept after its deterministic checks, in the same order) and calls the verifier of SYSTEM_rv
(robust reader, 4,096 output tokens). The reviewers' output is reused unchanged, so SYSTEM and
SYSTEM_rv differ only in the verifier and can be compared case by case. Output:
results/runs/<split>/<SYSTEM>_rv/seed<k>/<case>.json. Existing outputs are kept (resume).
"""
import argparse
import time
from concurrent.futures import ThreadPoolExecutor

from dpdp_audit.baselines import app_facts
from dpdp_audit.cases import case_dirs, load_case
from dpdp_audit.llm import LLM
from dpdp_audit.pipeline import get_config
from dpdp_audit.pipeline.verifier import verify
from dpdp_audit.runs import load_runs, run_path, save_run

RESET = ("uncertain", "supported", "verifier_reason")


def reverify(run: dict, case: dict, cfg, llm) -> dict:
    flows = app_facts(case["app_dir"])["flows"]
    old = run["findings"]
    findings = [dict({k: v for k, v in f.items() if k not in RESET}, uncertain=False, supported=None) for f in old]
    ver = verify(findings, case["policy"], flows, llm, run["seed"], llm_gaps=cfg.llm_check_gaps, robust=True)
    # the deterministic checks were already applied; keep the frozen run's flags on evidence
    flags = {f.get("candidate_id"): f for f in old}
    for f in ver["findings"]:
        for k in ("evidence_snapped", "evidence_removed"):
            if k in flags.get(f.get("candidate_id"), {}):
                f[k] = flags[f["candidate_id"]][k]
    trace = dict(run["trace"], reverified_from=run["system"], verifier_error=ver["error"],
                 verifier_parse=ver.get("parse"), verifier_unchecked=ver.get("unchecked", 0),
                 verifier_raw=ver.get("raw"))
    gaps = cfg.llm_check_gaps
    old_calls = 1 if any(gaps is None or f["gap_type"] in gaps for f in old) else 0   # frozen verifier call
    trace["llm_calls"] = run["trace"]["llm_calls"] - old_calls + ver["llm_calls"]
    usage = dict(run.get("usage") or {})
    for k in ("prompt", "output"):
        usage[k] = usage.get(k, 0) + (ver.get("usage") or {}).get(k, 0)
    return dict(run, system=cfg.name, findings=ver["findings"], dropped=run.get("dropped", []) + ver["dropped"],
                usage=usage, trace=trace)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--systems", nargs="+", required=True)
    ap.add_argument("--seeds", nargs="+", type=int, default=[0])
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--shard", default="0/1")
    args = ap.parse_args()
    shard, n = map(int, args.shard.split("/"))
    cases = {load_case(d)["case_id"]: load_case(d) for d in case_dirs(args.split)}
    ids = [c for i, c in enumerate(cases) if i % n == shard]
    jobs = []
    for system in args.systems:
        cfg = get_config(f"{system}_rv")
        if not cfg.verifier:
            raise SystemExit(f"{system} has no verifier")
        for seed in args.seeds:
            runs = load_runs(args.split, system, seed, ids)
            if runs is None:
                raise SystemExit(f"{args.split}/{system}/seed{seed}: runs missing")
            jobs += [(r, cfg, seed) for r in runs if not run_path(args.split, cfg.name, seed, r["case_id"]).exists()]
    print(f"shard {args.shard}: {len(jobs)} runs to re-verify", flush=True)
    llm = LLM(temperature=0.0, max_tokens=4096)
    t0, done = time.time(), [0]

    def work(job):
        run, cfg, seed = job
        try:
            out = reverify(run, cases[run["case_id"]], cfg, llm)
        except Exception as exc:   # not saved, so the next invocation redoes it
            print(f"FAILED {cfg.name} seed{seed} {run['case_id']}: {exc}"[:300], flush=True)
            return {"failed": True}
        save_run(args.split, cfg.name, seed, out)
        done[0] += 1
        if done[0] % 50 == 0:
            print(f"shard {args.shard}: {done[0]}/{len(jobs)} in {time.time() - t0:.0f}s", flush=True)
        return out["trace"]

    with ThreadPoolExecutor(args.workers) as pool:
        traces = list(pool.map(work, jobs))
    failed = sum(1 for t in traces if t.get("failed"))
    traces = [t for t in traces if not t.get("failed")]
    modes = {}
    for t in traces:
        key = t.get("verifier_parse") or ("unreadable" if t.get("verifier_error") else "no check needed")
        modes[key] = modes.get(key, 0) + 1
    unchecked = sum(t.get("verifier_unchecked", 0) for t in traces)
    print(f"shard {args.shard}: finished {len(traces)} in {time.time() - t0:.0f}s; {failed} failed calls; "
          f"replies {modes}; findings left unchecked {unchecked}", flush=True)
    if failed:
        raise SystemExit(f"{failed} runs failed; run again to redo them")


if __name__ == "__main__":
    main()
