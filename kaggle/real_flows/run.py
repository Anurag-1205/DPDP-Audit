"""Kaggle kernel: real-flow sampling (SPEC-08, AC-08.1) from another IP than the laptop.

The Wayback Machine rate-limits one address at a time, so scripts/sample_real_flows.py runs here,
resuming from the committed data/real_flows/progress.jsonl. PoliCheck's flows come from a fresh
clone of the authors' repository. Output: /kaggle/working/real_flows.tar.gz with data/real_flows/
(unpack it at the repository root). The run stops after BUDGET seconds at the latest.
"""
import glob
import os
import shutil
import subprocess
import sys
import tarfile

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
PC = f"{REPO}/data/external/PrivacyPolicyAnalysis"
N, MAX_TRIED = 45, 250
BUDGET = 11 * 3600   # seconds: stop before the 12 h kernel limit so the output is always packed


def sh(cmd):
    print(f"+ {cmd}", flush=True)
    subprocess.run(cmd, shell=True, check=True)


if __name__ == "__main__":
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
    else:   # Kaggle may have unpacked the archive
        roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
        print("input roots:", roots, flush=True)
        shutil.copytree(roots[0], REPO)
    sh(f"git clone -q --depth 1 https://github.com/benandow/PrivacyPolicyAnalysis.git {PC}")
    env = dict(os.environ, PYTHONPATH=f"{REPO}/src")
    try:
        # progress.jsonl and policies/ are written as they come, so a timeout keeps everything
        # fetched; apps.json and flows_raw.csv are then rebuilt locally from progress.jsonl
        subprocess.run([sys.executable, "-u", "scripts/sample_real_flows.py", "--n", str(N),
                        "--max-tried", str(MAX_TRIED)], cwd=REPO, env=env, check=True, timeout=BUDGET)
    except subprocess.TimeoutExpired:
        print(f"time budget of {BUDGET}s reached; packing what was fetched", flush=True)
    finally:
        with tarfile.open(f"{WORK}/real_flows.tar.gz", "w:gz") as t:
            t.add(f"{REPO}/data/real_flows", arcname="data/real_flows")
        shutil.rmtree(REPO, ignore_errors=True)
