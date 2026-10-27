"""Kaggle kernel: run PoliCheck (S1) on a whole benchmark split (SPLIT below), without Docker.

Kaggle has no Docker, so the authors' image (python:2.7 + spaCy 2.0.12) is rebuilt as a
micromamba Python 2.7 environment. The code reads and writes the fixed paths /ext and /src,
which are symlinked to the cloned repository. Inputs are prepared with our own
tool_runs.prepare_ext (as scripts/tools/run_policheck.py does locally), then the four steps
of the image's main.sh run in order. Output: /kaggle/working/policheck_results.csv and
results.tar.gz (raw output + logs).
"""
import glob
import os
import shutil
import subprocess
import sys
import tarfile
import time

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
PC = f"{REPO}/data/external/PrivacyPolicyAnalysis"
MAMBA = f"{WORK}/bin/micromamba"
ENV = f"{WORK}/py27"
NLP_MODEL_ID = "1yMB3TJt8oZX3-GHm9oB_eKU7oeJXfLbA"
SPLIT = "sanity"           # "main", "ladder", or "sanity" (data/tools/policheck_sanity, AC-03.4)
T_START = time.time()


def sh(cmd, **kw):
    print(f"+ [{time.time() - T_START:.0f}s] {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=True, **kw)


def find_repo():
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)


def setup():
    sh(f"mkdir -p {WORK}/bin && curl -sL https://micro.mamba.pm/api/micromamba/linux-64/latest "
       f"| tar -xj -C {WORK} bin/micromamba")
    sh(f"{MAMBA} create -y -q -p {ENV} -c conda-forge python=2.7 pip")
    pip = f"{ENV}/bin/pip"
    sh(f"{pip} install -q spacy==2.0.12 networkx==2.2 lxml==4.9.3 pandas==0.24.2 enum34 dill==0.3.4")
    sh(f"git clone -q --depth 1 https://github.com/benandow/PrivacyPolicyAnalysis.git {PC}")
    sh(f"{sys.executable} -m pip install -q gdown")
    sh(f"gdown -q {NLP_MODEL_ID} -O {WORK}/nlp.tgz && tar xzf {WORK}/nlp.tgz -C {PC}/ext && rm {WORK}/nlp.tgz")
    for link, target in (("/ext", f"{PC}/ext"), ("/src", f"{PC}/DockerImage/code")):
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(target, link)


def run_policheck():
    sys.path.insert(0, f"{REPO}/src")
    from pathlib import Path
    from dpdp_audit import tool_runs
    export = (f"{REPO}/data/tools/policheck_sanity" if SPLIT == "sanity"
              else f"{REPO}/data/benchmark/{SPLIT}/export/policheck")
    tool_runs.prepare_ext(Path(export), None, "policheck")
    env = dict(os.environ, PATH=f"{ENV}/bin:{os.environ['PATH']}")
    log = open(f"{WORK}/policheck.log", "w")
    # the image's ENTRYPOINT, /src/main.sh: ontologies, then extraction, consistency, cleanup, labels
    proc = subprocess.run("bash /src/main.sh", shell=True, cwd="/src", env=env, stdout=log,
                          stderr=subprocess.STDOUT)
    log.close()
    print(open(f"{WORK}/policheck.log").read()[-4000:], flush=True)
    print(f"main.sh exit {proc.returncode} after {time.time() - T_START:.0f}s", flush=True)
    shutil.copy("/ext/policheck_results.csv", f"{WORK}/policheck_results.csv")
    n = sum(1 for _ in open(f"{WORK}/policheck_results.csv")) - 1
    print(f"{n} result rows", flush=True)


if __name__ == "__main__":
    try:
        find_repo()
        setup()
        run_policheck()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            for p in (f"{WORK}/policheck_results.csv", f"{WORK}/policheck.log", f"{PC}/ext/policylint_results.csv"):
                if os.path.exists(p):
                    t.add(p, arcname=os.path.basename(p))
            for p in glob.glob(f"{PC}/ext/*.log"):
                t.add(p, arcname="logs/" + os.path.basename(p))
        # keep the kernel output small: only the results are needed
        for d in (ENV, REPO, f"{WORK}/bin"):
            shutil.rmtree(d, ignore_errors=True)
