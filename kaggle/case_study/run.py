"""Kaggle kernel: the open-source case study (SPEC-08, AC-08.4; data/case_study/).

Three apps (Aarogya Setu, Wikipedia, DuckDuckGo) with data flows written by hand from their code
(scripts/build_case_study.py). Everything runs as frozen: the headline full_v2_finetuned_rv with the
29 Oct QLoRA adapter (dataset ishaan2312/dpdp-qlora-adapter, the same adapter as on main) and the
single-prompt baseline B2, seeds 0-2. No answer keys and no scoring: every finding is checked by hand
(data/case_study/findings.csv). Results: /kaggle/working/results.tar.gz.
"""
import glob
import importlib.util
import os
import sys
import tarfile

BOOT = "/kaggle/working/_boot"
JOBS = [
    {"phase": "tag", "tagger": "finetuned", "splits": ["case_study"]},
    {"phase": "runs", "split": "case_study", "configs": ["full_v2_finetuned_rv"], "seeds": [0, 1, 2]},
    {"phase": "baselines", "split": "case_study", "systems": ["B2"], "seeds": [0, 1, 2]},
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
