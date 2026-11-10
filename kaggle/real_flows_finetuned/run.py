"""Kaggle kernel: the headline system full_v2_finetuned_rv on the real flows (SPEC-08, AC-08.3).

The fine-tuned tagger is the QLoRA adapter trained on 29 Oct (ishaan2312/dpdp-audit-qlora), attached
as that kernel's output (kernel_sources), so the real flows use exactly the adapter behind the main
results; it is never retrained here. Steps, all from kaggle/pipeline/run.py:
  1. serve Qwen2.5-3B-Instruct + the adapter; tag every paragraph of the real-flow policies
     -> results/tagger/claims/finetuned.jsonl (new paragraphs only; earlier claims are kept)
  2. serve Qwen2.5-7B-Instruct-AWQ; run full_v2_finetuned_rv, seeds 0-2, on data/benchmark/real_flows
  3. score_runs.py on the real flows
Results: /kaggle/working/results.tar.gz, which unpacks onto the repository root.
"""
import glob
import importlib.util
import os
import sys
import tarfile

BOOT = "/kaggle/working/_boot"
SPLITS = ["real_flows"]       # add "case_study" once data/benchmark/case_study exists (SPEC-08, AC-08.4)
JOBS = [
    {"phase": "tag", "tagger": "finetuned", "splits": SPLITS},
] + [
    {"phase": "runs", "split": s, "configs": ["full_v2_finetuned_rv"], "seeds": [0, 1, 2]} for s in SPLITS
] + [
    {"phase": "score", "split": s, "systems": ["full_v2_finetuned_rv"]} for s in SPLITS
]


def load_pipeline_kernel():
    """Unpack the uploaded repository once to import kaggle/pipeline/run.py (which unpacks it again)."""
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(BOOT)
        path = f"{BOOT}/kaggle/pipeline/run.py"
    else:
        path = glob.glob("/kaggle/input/**/kaggle/pipeline/run.py", recursive=True)[0]
    spec = importlib.util.spec_from_file_location("pipeline_kernel", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pipeline_kernel"] = mod
    spec.loader.exec_module(mod)
    return mod


if __name__ == "__main__":
    pk = load_pipeline_kernel()
    pk.find_adapter()           # fail at once, before any install, if the adapter is not attached
    pk.JOBS = JOBS
    pk.main()
