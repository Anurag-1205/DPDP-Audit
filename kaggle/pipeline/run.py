"""Kaggle kernel: DPDP-Audit pipeline runs on 2x T4 (SPEC-04, WP-2.8 onwards).

Phases (edit JOBS below before pushing):
  tag       serve Qwen2.5-3B-Instruct on both GPUs; tag every distinct policy paragraph of the
            listed splits once (prompted tagger, greedy) -> results/tagger/claims/prompted.jsonl
  pilot     serve Qwen2.5-7B-Instruct-AWQ; 5 dev cases (training policies), timing per run
            -> results/pipeline_pilot.json
  runs      pipeline configurations x seeds on a split, sharded over the two servers
  baselines single-pass baselines (run_baselines.py), e.g. B2 on the ladder
  score     score_runs.py for the systems that ran

Runs already in the uploaded repository are kept (resume); failed calls are redone. Results
are packed into /kaggle/working/results.tar.gz, which unpacks onto the repository root.
vLLM 0.10.2 with the V0 engine and xFormers (docs/infrastructure.md#why-vllm-0102).
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
TAGGER_MODEL = "Qwen/Qwen2.5-3B-Instruct"
MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
DEADLINE_MIN = 600
T_START = time.time()

# Prompts and decision rules frozen on 26 Oct after four dev-split iterations (docs/pipeline.md).
# Robust verifier (28 Oct): the frozen reader could not read 15-40% of the verifier's replies and
# kept those findings unchecked. "reverify" re-runs only the verifier on saved runs (-> <system>_rv).
DEV_SYSTEMS = ["full", "v2_gate", "v2_read", "v2_purpose", "v2_batch"]
JOBS = [
    {"phase": "reverify", "split": "main", "systems": ["full", "full_finetuned", "full_v2", "full_v2_finetuned"],
     "seeds": [0, 1, 2]},
    {"phase": "reverify", "split": "main", "systems": ["A2", "A3", "A5", "A2_v2", "A3_v2", "A5_v2"], "seeds": [0]},
    {"phase": "reverify", "split": "dev", "systems": DEV_SYSTEMS, "seeds": [0]},
    {"phase": "reverify", "split": "dev2", "systems": DEV_SYSTEMS, "seeds": [0]},
]


def sh(cmd, **kw):
    print(f"+ [{time.time() - T_START:.0f}s] {cmd}", flush=True)
    return subprocess.run(f"set -o pipefail; {cmd}", shell=True, check=True, executable="/bin/bash", **kw)


def find_repo():
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)


def ready(port):
    try:
        urllib.request.urlopen(f"http://localhost:{port}/v1/models", timeout=3)
        return True
    except Exception:
        return False


class Servers:
    """One vLLM server per GPU."""

    def __init__(self):
        self.procs, self.model = {}, None

    def start(self, model, lora: dict | None = None):
        """lora: {served name: adapter path}, served next to the base model (vLLM --enable-lora)."""
        if self.model == (model, tuple(sorted((lora or {}).items()))):
            return
        self.stop()
        for engine in ("v0-xformers", "v1-default"):
            for g in (0, 1):
                env = dict(os.environ, CUDA_VISIBLE_DEVICES=str(g))
                if engine == "v0-xformers":
                    env.update(VLLM_USE_V1="0", VLLM_ATTENTION_BACKEND="XFORMERS")
                args = [sys.executable, "-m", "vllm.entrypoints.openai.api_server", "--model", model,
                        "--dtype", "half", "--max-model-len", "12288", "--gpu-memory-utilization", "0.92",
                        "--port", str(8000 + g), "--max-num-seqs", "16"]
                if "AWQ" in model:
                    args += ["--quantization", "awq"]
                if lora:
                    args += ["--enable-lora", "--max-lora-rank", "16", "--lora-modules"] + \
                        [f"{name}={path}" for name, path in lora.items()]
                log = open(f"{WORK}/vllm_{model.split('/')[-1]}_gpu{g}_{engine}.log", "w")
                # own process group, so stop() also kills the engine worker that holds the GPU
                self.procs[g] = subprocess.Popen(args, stdout=log, stderr=subprocess.STDOUT, env=env,
                                                 start_new_session=True)
            t0 = time.time()
            while time.time() - t0 < 1800:
                if all(ready(8000 + g) for g in self.procs):
                    self.model = (model, tuple(sorted((lora or {}).items())))
                    print(f"{model} ready with {engine} after {time.time() - T_START:.0f}s", flush=True)
                    return
                if any(p.poll() is not None for p in self.procs.values()):
                    break
                time.sleep(10)
            print(f"engine {engine} failed for {model}", flush=True)
            self.stop()
        raise RuntimeError(f"vLLM could not start {model}")

    def stop(self):
        import signal
        for p in self.procs.values():
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        for p in self.procs.values():
            p.wait()
        self.procs, self.model = {}, None
        # wait until the GPUs are actually free (a stale engine process caused an OOM once)
        for _ in range(60):
            used = subprocess.run("nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits",
                                  shell=True, capture_output=True, text=True).stdout.split()
            if used and all(int(u) < 1000 for u in used):
                break
            time.sleep(5)
        print("GPU memory in use after stop (MiB):", used, flush=True)


def env_for(gpu, model):
    return dict(os.environ, LLM_BACKEND="openai", OPENAI_MODEL=model, TOKENIZERS_PARALLELISM="false",
                OPENAI_BASE_URL=f"http://localhost:{8000 + gpu}/v1")


def sharded(cmd_for_shard, model):
    procs = [subprocess.Popen(f"cd {REPO} && {cmd_for_shard(g)}", shell=True, env=env_for(g, model))
             for g in (0, 1)]
    for p in procs:
        p.wait()
    return [p.returncode for p in procs]


def remaining_min():
    return max(1, DEADLINE_MIN - (time.time() - T_START) / 60)


def run():
    find_repo()
    sh("nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv")
    sh(f"{sys.executable} -m pip install -q vllm==0.10.2 transformers==4.56.2")
    sh(f"{sys.executable} -m pip install -q -e {REPO} python-dotenv faiss-cpu sentence-transformers openai "
       f"google-genai transformers==4.56.2")
    os.makedirs(f"{REPO}/outputs/logs", exist_ok=True)
    # the oracle tagger (A5) and tagging the held-out segments read the OPP-115 release
    if any(c.startswith("A5") for j in JOBS for c in j.get("configs", [])) or any(j.get("heldout") for j in JOBS):
        sh(f"bash {REPO}/scripts/download_opp115.sh")
    sh(f"cd {REPO} && {sys.executable} scripts/build_dpdp_index.py", env=env_for(0, MODEL))
    servers = Servers()
    py = sys.executable
    try:
        for job in JOBS:
            phase = job["phase"]
            print(f"=== {phase} {job} at {(time.time() - T_START) / 60:.0f} min", flush=True)
            if remaining_min() <= 5 and phase != "score":
                print("deadline reached, skipping", flush=True)
                continue
            if phase == "tag":
                servers.start(TAGGER_MODEL)
                held = "--heldout" if job.get("heldout") else ""
                splits = " ".join(job["splits"])
                sharded(lambda g: f"{py} scripts/tag_policies.py --tagger prompted --splits {splits} {held} "
                                  f"--shard {g}/2 --workers 32 --out outputs/claims_shard{g}.jsonl "
                                  f"| tee outputs/logs/tag_shard{g}.log", TAGGER_MODEL)
                sh(f"cd {REPO} && {py} scripts/tag_policies.py --tagger prompted --merge "
                   f"outputs/claims_shard0.jsonl outputs/claims_shard1.jsonl")
            elif phase == "pilot":
                servers.start(MODEL)
                sh(f"cd {REPO} && {py} scripts/run_pipeline.py --configs full --seeds 0 --split {job['split']} "
                   f"--limit {job['limit']} --workers 4 --pilot results/pipeline_pilot.json "
                   f"| tee outputs/logs/pilot.log", env=env_for(0, MODEL))
            elif phase == "runs":
                servers.start(MODEL)
                configs, seeds = " ".join(job["configs"]), " ".join(map(str, job["seeds"]))
                sharded(lambda g: f"{py} scripts/run_pipeline.py --configs {configs} --seeds {seeds} "
                                  f"--split {job['split']} --workers 8 --shard {g}/2 --redo-failed "
                                  f"--deadline-min {remaining_min():.0f} "
                                  f"| tee outputs/logs/runs_{job['split']}_shard{g}.log", MODEL)
            elif phase == "reverify":
                servers.start(MODEL)
                systems, seeds = " ".join(job["systems"]), " ".join(map(str, job["seeds"]))
                sharded(lambda g: f"{py} scripts/reverify.py --split {job['split']} --systems {systems} "
                                  f"--seeds {seeds} --workers 8 --shard {g}/2 "
                                  f"| tee outputs/logs/reverify_{job['split']}_shard{g}.log", MODEL)
            elif phase == "baselines":
                servers.start(MODEL)
                systems, seeds = " ".join(job["systems"]), " ".join(map(str, job["seeds"]))
                sharded(lambda g: f"{py} scripts/run_baselines.py --systems {systems} --seeds {seeds} "
                                  f"--split {job['split']} --workers 8 --shard {g}/2 --redo-failed "
                                  f"--deadline-min {remaining_min():.0f} "
                                  f"| tee outputs/logs/baselines_{job['split']}_shard{g}.log", MODEL)
            elif phase == "score":
                systems = " ".join(job["systems"])
                subprocess.run(f"cd {REPO} && {py} scripts/score_runs.py --split {job['split']} --systems "
                               f"{systems} | tee outputs/logs/scores_{job['split']}.md", shell=True,
                               env=env_for(0, MODEL))
    finally:
        servers.stop()


def main():
    try:
        run()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            for sub in ("results", "outputs/logs"):
                if os.path.isdir(f"{REPO}/{sub}"):
                    t.add(f"{REPO}/{sub}", arcname=sub)
        for log in glob.glob(f"{WORK}/vllm_*.log"):
            with open(log) as f:
                tail = f.read()[-1500:]
            print(f"--- {log} (tail)\n{tail}", flush=True)
        shutil.rmtree(REPO, ignore_errors=True)


if __name__ == "__main__":
    main()
