"""Write the Kaggle notebooks as .ipynb files (keeps their source reviewable in git)."""
import json
from pathlib import Path

HERE = Path(__file__).parent


def nb(cells):
    out = []
    for kind, src in cells:
        cell = {"cell_type": kind, "metadata": {}, "source": src.strip("\n").splitlines(keepends=True)}
        if kind == "code":
            cell.update(execution_count=None, outputs=[])
        out.append(cell)
    return {"cells": out, "metadata": {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                                       "accelerator": "GPU"}, "nbformat": 4, "nbformat_minor": 5}


QWEN = [
    ("markdown", """
# DPDP-Audit: Qwen2.5-7B-Instruct on vLLM (Kaggle, 2x T4)

Serves the reasoning model through vLLM's OpenAI-compatible API, checks that it returns
token log-probabilities, and then runs the experiment scripts against it.

Settings: *Accelerator = GPU T4 x2*, *Internet = on*. Add the repository as a Kaggle dataset
named `dpdp-audit` (or set `REPO_URL` below to a git URL).
"""),
    ("code", """
!pip install -q "vllm==0.6.3.post1"
"""),
    ("code", """
import subprocess, time, requests, os
MODEL = "Qwen/Qwen2.5-7B-Instruct-AWQ"
server = subprocess.Popen(
    ["python", "-m", "vllm.entrypoints.openai.api_server", "--model", MODEL,
     "--quantization", "awq", "--dtype", "half", "--tensor-parallel-size", "2",
     "--max-model-len", "16384", "--gpu-memory-utilization", "0.90", "--port", "8000"],
    stdout=open("vllm.log", "w"), stderr=subprocess.STDOUT)
for _ in range(120):
    try:
        if requests.get("http://localhost:8000/v1/models", timeout=2).ok:
            print("server ready"); break
    except Exception:
        time.sleep(10)
else:
    print(open("vllm.log").read()[-3000:])
"""),
    ("markdown", "## Stage 0 check: the model answers a test prompt with log-probabilities"),
    ("code", """
from openai import OpenAI
client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")
r = client.chat.completions.create(model=MODEL, messages=[{"role": "user", "content": "Reply with the word OK."}],
                                   max_tokens=5, logprobs=True, temperature=0)
print(r.choices[0].message.content, [round(t.logprob, 3) for t in r.choices[0].logprobs.content])
"""),
    ("markdown", "## Run experiments against the local server"),
    ("code", """
REPO_URL = ""  # e.g. a git URL; leave empty to use the Kaggle dataset copy
if REPO_URL:
    !git clone -q {REPO_URL} /kaggle/working/dpdp-audit
else:
    !cp -r /kaggle/input/dpdp-audit /kaggle/working/dpdp-audit
%cd /kaggle/working/dpdp-audit
!pip install -q -e . python-dotenv faiss-cpu sentence-transformers google-genai
os.environ.update(LLM_BACKEND="openai", OPENAI_BASE_URL="http://localhost:8000/v1", OPENAI_MODEL=MODEL)
"""),
    ("code", """
!python scripts/run_baselines.py --systems B1 B2 --seeds 0 1 2
!python scripts/score_runs.py --systems B1 B2
"""),
    ("code", """
# Keep results: download outputs/ from the notebook's output panel.
!tar czf /kaggle/working/outputs.tgz outputs/runs outputs/scores
"""),
]



if __name__ == "__main__":
    for name, cells in (("kaggle_qwen_vllm", QWEN),):
        (HERE / f"{name}.ipynb").write_text(json.dumps(nb(cells), indent=1))
        print(f"wrote {name}.ipynb")
