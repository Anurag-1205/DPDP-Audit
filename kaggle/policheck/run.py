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
SPLIT = "s4"               # "main", "ladder", "sanity" (data/tools/policheck_sanity, AC-03.4) or "s4"
#   s4: PolicyLint statement extraction on the 1,140 held-out OPP-115 segments (WP-3.6, AC-05.6)
STEP_LIMIT_S = 3600 if SPLIT == "sanity" else 3 * 3600   # main.sh as a whole
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
    # the image's ENTRYPOINT, /src/main.sh: ontologies, then extraction, consistency, cleanup, labels.
    # bash -x logs each step, and the time limit turns a hang into a saved log (a sanity run once
    # hung for 12 h with no output; the 140-case ladder takes 34 min).
    proc = subprocess.Popen("bash -x /src/main.sh", shell=True, cwd="/src", env=env, stdout=log,
                            stderr=subprocess.STDOUT, start_new_session=True)
    try:
        code = proc.wait(timeout=STEP_LIMIT_S)
    except subprocess.TimeoutExpired:
        import signal
        os.killpg(proc.pid, signal.SIGKILL)
        code = f"killed after {STEP_LIMIT_S}s"
        print(subprocess.run("ps aux --sort=-%cpu | head -8", shell=True, capture_output=True,
                             text=True).stdout, flush=True)
    log.close()
    print(open(f"{WORK}/policheck.log").read()[-6000:], flush=True)
    print(f"main.sh exit {code} after {time.time() - T_START:.0f}s", flush=True)
    shutil.copy("/ext/policheck_results.csv", f"{WORK}/policheck_results.csv")
    n = sum(1 for _ in open(f"{WORK}/policheck_results.csv")) - 1
    print(f"{n} result rows", flush=True)


def run_policylint_s4():
    """PolicyLint's extraction step only, one plaintext file per held-out segment (the unit the
    taggers are scored on), then s4_export_policylint.py writes its statements as JSON."""
    import json
    plain = f"{PC}/ext/plaintext_policies"
    shutil.rmtree(plain, ignore_errors=True)
    os.makedirs(plain)
    n = 0
    for line in open(f"{REPO}/results/tagger/heldout.jsonl"):
        seg = json.loads(line)
        with open(f"{plain}/s4_{seg['policy_id']}_{seg['segment_id']}.txt", "w") as f:
            f.write("\n".join(l.strip() for l in seg["text"].split("\n") if l.strip()) + "\n")
        n += 1
    print(f"{n} segments", flush=True)
    env = dict(os.environ, PATH=f"{ENV}/bin:{os.environ['PATH']}")
    shutil.copy(f"{REPO}/kaggle/policheck/s4_export_policylint.py", "/src/s4_export_policylint.py")
    script = " && ".join([
        # PoliCheck's ontologies (an extension of PolicyLint's, also used for S1): the entity
        # ontology shipped for PolicyLint has no "we" node, so every first-party statement was
        # dropped as unknown (first run, 29 Oct: 1,252 of 1,523 statements)
        "cp /ext/data/data_ontology_policheck.pickle data_ontology.pickle",
        "cp /ext/data/entity_ontology_policheck.pickle entity_ontology.pickle",
        "mkdir -p /ext/input/policySubsets /ext/output/policy /ext/output/analytics /ext/output/log "
        "/ext/output/log_data",
        "find /ext/plaintext_policies -type f > /ext/input/policySubsets/1.txt",
        "python2 PatternExtractionNotebook.py 1 > /ext/s4_extraction.log 2>&1",
        f"python2 s4_export_policylint.py {WORK}/policylint_s4.json",
    ])
    t0 = time.time()
    subprocess.run(f"bash -x -c '{script}'", shell=True, cwd="/src", env=env, check=True, timeout=STEP_LIMIT_S)
    print(f"PolicyLint on {n} segments in {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    try:
        find_repo()
        setup()
        run_policylint_s4() if SPLIT == "s4" else run_policheck()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            for p in (f"{WORK}/policheck_results.csv", f"{WORK}/policheck.log", f"{PC}/ext/policylint_results.csv",
                      f"{WORK}/policylint_s4.json", f"{PC}/ext/s4_extraction.log"):
                if os.path.exists(p):
                    t.add(p, arcname=os.path.basename(p))
            for p in glob.glob(f"{PC}/ext/*.log"):
                t.add(p, arcname="logs/" + os.path.basename(p))
        # keep the kernel output small: only the results are needed
        for d in (ENV, REPO, f"{WORK}/bin"):
            shutil.rmtree(d, ignore_errors=True)
