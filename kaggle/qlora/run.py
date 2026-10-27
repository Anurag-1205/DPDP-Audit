"""Kaggle kernel: QLoRA clause tagger (SPEC-05, WP-2.9) and tagging for the pipeline.

1. Train Qwen2.5-3B-Instruct with QLoRA (scripts/train_tagger.py: 4-bit, rank 16, 2 epochs) on the
   80 training policies. The adapter is packed into qlora_adapter.tar.gz as soon as it is saved.
2. Serve the base model with the adapter (vLLM LoRA, no merge) on both T4s and tag every distinct
   paragraph of the main, dev and ladder policies plus every held-out segment
   -> results/tagger/claims/finetuned.jsonl.
3. Score the claims taggers (category macro-F1, tuple F1) into results/scores/tagger.json; the
   prompted tagger's claims come from the pipeline kernel (only that kernel writes prompted.jsonl).

Outputs: results.tar.gz (unpacks onto the repository root) and qlora_adapter.tar.gz (the adapter,
kept out of git).
"""
import glob
import importlib.util
import os
import shutil
import subprocess
import sys
import tarfile
import time

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
ADAPTER = f"{WORK}/qlora"
BASE = "Qwen/Qwen2.5-3B-Instruct"
SERVED = "dpdp-tagger-qlora"
SPLITS = "main dev ladder"
T_START = time.time()


def sh(cmd, **kw):
    print(f"+ [{time.time() - T_START:.0f}s] {cmd}", flush=True)
    # pipefail: a failing command piped into tee must still fail the step
    return subprocess.run(f"set -o pipefail; {cmd}", shell=True, check=True, executable="/bin/bash", **kw)


def find_repo():
    """Kaggle usually unpacks the uploaded archive; handle both forms."""
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)


def pipeline_kernel():
    spec = importlib.util.spec_from_file_location("pipeline_kernel", f"{REPO}/kaggle/pipeline/run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def tag(pk, tagger, model, extra=""):
    py = sys.executable
    pk.sharded(lambda g: f"{py} scripts/tag_policies.py --tagger {tagger} --splits {SPLITS} {extra} "
                         f"--shard {g}/2 --workers 32 --out outputs/{tagger}_shard{g}.jsonl "
                         f"| tee outputs/logs/tag_{tagger}_shard{g}.log", model)
    sh(f"cd {REPO} && {py} scripts/tag_policies.py --tagger {tagger} --merge "
       f"outputs/{tagger}_shard0.jsonl outputs/{tagger}_shard1.jsonl")


def run():
    find_repo()
    os.makedirs(f"{REPO}/outputs/logs", exist_ok=True)
    sh("nvidia-smi --query-gpu=name,memory.total --format=csv")
    sh(f"bash {REPO}/scripts/download_opp115.sh")
    py = sys.executable
    sh(f"{py} -m pip install -q peft bitsandbytes accelerate python-dotenv faiss-cpu sentence-transformers")
    sh(f"{py} -m pip install -q -e {REPO} --no-deps")
    if not os.path.exists(f"{ADAPTER}/adapter_config.json"):
        sh(f"cd {REPO} && CUDA_VISIBLE_DEVICES=0 {py} scripts/train_tagger.py --out {ADAPTER} "
           f"2>&1 | tee outputs/logs/train_tagger.log")
    shutil.copy(f"{ADAPTER}/training_info.json", f"{REPO}/results/tagger/qlora_training_info.json")
    with tarfile.open(f"{WORK}/qlora_adapter.tar.gz", "w:gz") as t:
        t.add(ADAPTER, arcname="qlora_adapter")

    sh(f"{py} -m pip install -q vllm==0.10.2 transformers==4.56.2")
    sh(f"{py} -m pip install -q -e {REPO} python-dotenv faiss-cpu sentence-transformers openai")
    pk = pipeline_kernel()
    pk.REPO, pk.WORK = REPO, WORK
    servers = pk.Servers()
    try:
        servers.start(BASE, lora={SERVED: ADAPTER})
        tag(pk, "finetuned", SERVED, "--heldout")
    finally:
        servers.stop()
    sh(f"cd {REPO} && {py} scripts/eval_tagger.py --gold results/tagger/heldout.jsonl --claims prompted finetuned "
       f"| tee outputs/logs/eval_tagger.md")


def main():
    try:
        run()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            for sub in ("results/tagger", "results/scores", "outputs/logs"):
                if os.path.isdir(f"{REPO}/{sub}"):
                    t.add(f"{REPO}/{sub}", arcname=sub)
        # the adapter stays in /kaggle/working (kernel output) as well as in qlora_adapter.tar.gz
        shutil.rmtree(REPO, ignore_errors=True)


if __name__ == "__main__":
    main()
