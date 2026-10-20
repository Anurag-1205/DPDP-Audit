"""Kaggle kernel: Stage 0 model check + Stage 1 single-pass baselines on Qwen2.5-7B-Instruct.

Serves Qwen2.5-7B-Instruct-AWQ with vLLM on both T4s (one server per GPU), checks that it
answers with token log-probabilities, then runs B1 and B2 on every main-benchmark case with
three seeds and scores them. Runs already in the uploaded repository are kept; failed calls
are redone. Results are packed into /kaggle/working/results.tar.gz.

T4 (sm75) has no FlashAttention. vLLM's V1 engine then falls back to FlexAttention, which
was ~10x too slow in an earlier run, so the V0 engine with xFormers is tried first.
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import tarfile
import time
import urllib.request

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
DEADLINE_MIN = 600          # stop starting new runs after 10 h (Kaggle stops GPU sessions at 12 h)
T_START = time.time()


def sh(cmd, **kw):
    print("+", cmd, flush=True)
    return subprocess.run(cmd, shell=True, check=True, **kw)


def find_repo():
    """Kaggle usually unpacks the uploaded archive; handle both forms."""
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)
    print("repository copied from", roots[0], flush=True)


def ready(port):
    try:
        urllib.request.urlopen(f"http://localhost:{port}/v1/models", timeout=3)
        return True
    except Exception:
        return False


def start_server(gpu: int, engine: str):
    env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(gpu))
    if engine == "v0-xformers":
        env.update(VLLM_USE_V1="0", VLLM_ATTENTION_BACKEND="XFORMERS")
    log = open(f"{WORK}/vllm_gpu{gpu}_{engine}.log", "w")
    proc = subprocess.Popen(
        [sys.executable, "-m", "vllm.entrypoints.openai.api_server", "--model", MODEL,
         "--quantization", "awq", "--dtype", "half", "--max-model-len", "12288",
         "--gpu-memory-utilization", "0.92", "--port", str(8000 + gpu), "--max-num-seqs", "16"],
        stdout=log, stderr=subprocess.STDOUT, env=env)
    return proc


def wait(procs, timeout=1800):
    t0 = time.time()
    while time.time() - t0 < timeout:
        if all(ready(8000 + g) for g in procs):
            return True
        if any(p.poll() is not None for p in procs.values()):
            return False
        time.sleep(10)
    return False


def main():
    try:
        run()
    finally:
        os.makedirs(f"{WORK}/outputs", exist_ok=True)
        for sub in ("runs", "scores", "logs"):
            if os.path.isdir(f"{REPO}/outputs/{sub}"):
                shutil.copytree(f"{REPO}/outputs/{sub}", f"{WORK}/outputs/{sub}", dirs_exist_ok=True)
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            t.add(f"{WORK}/outputs", arcname="outputs")
        shutil.rmtree(f"{WORK}/outputs", ignore_errors=True)
        shutil.rmtree(REPO, ignore_errors=True)


def run():
    find_repo()
    sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv")
    # vLLM 0.10.2: last release with the V0 engine (xFormers on T4); supports Python 3.13
    sh(f"{sys.executable} -m pip install -q vllm==0.10.2 transformers==4.56.2")
    sh(f"{sys.executable} -m pip install -q -e {REPO} python-dotenv faiss-cpu sentence-transformers openai "
       f"google-genai transformers==4.56.2")
    sh(f"{sys.executable} -c 'import vllm, torch, transformers; "
       f"print(vllm.__version__, torch.__version__, torch.cuda.is_available(), transformers.__version__)'")

    engine = None
    for candidate in ("v0-xformers", "v1-default"):
        procs = {g: start_server(g, candidate) for g in (0, 1)}
        if wait(procs):
            engine = candidate
            break
        for g, p in procs.items():
            p.kill()
            print(f"engine {candidate} failed on GPU {g}:\n" +
                  open(f"{WORK}/vllm_gpu{g}_{candidate}.log").read()[-2000:], flush=True)
        time.sleep(15)
    if engine is None:
        raise RuntimeError("vLLM could not start")
    print(f"servers ready on both GPUs with engine {engine} after {time.time() - T_START:.0f}s", flush=True)

    # Stage 0 check: the model answers a test prompt with token log-probabilities
    from openai import OpenAI
    client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
    r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": "Reply with the word OK."}],
                                       max_tokens=5, temperature=0, logprobs=True)
    check = {"model": MODEL, "engine": engine, "reply": r.choices[0].message.content,
             "logprobs": [round(t.logprob, 4) for t in r.choices[0].logprobs.content]}
    os.makedirs(f"{REPO}/outputs/logs", exist_ok=True)
    json.dump(check, open(f"{REPO}/outputs/logs/stage0_model_check.json", "w"), indent=1)
    print("stage 0 check:", check, flush=True)

    base_env = dict(os.environ, LLM_BACKEND="openai", OPENAI_MODEL=MODEL, TOKENIZERS_PARALLELISM="false")
    sh(f"cd {REPO} && {sys.executable} scripts/build_dpdp_index.py", env=base_env)
    remaining = DEADLINE_MIN - (time.time() - T_START) / 60
    shards = []
    for g in (0, 1):
        env = dict(base_env, OPENAI_BASE_URL=f"http://localhost:{8000 + g}/v1")
        cmd = (f"cd {REPO} && {sys.executable} scripts/run_baselines.py --systems B1 B2 --seeds 0 1 2 "
               f"--workers 8 --shard {g}/2 --redo-failed --deadline-min {remaining:.0f}")
        print("+", cmd, flush=True)
        shards.append(subprocess.Popen(cmd, shell=True, env=env))
    for p in shards:
        p.wait()
    print(f"baselines done at {(time.time() - T_START) / 60:.0f} min", flush=True)
    sh(f"cd {REPO} && {sys.executable} scripts/score_runs.py --systems B1 B2 | tee outputs/logs/scores_b1b2.md",
       env=base_env)


if __name__ == "__main__":
    main()
