"""Kaggle kernel: run PoliGraph-er and its flow-consistency check on a benchmark split (S2).

Builds a Python 3.10 environment with the versions PoliGraph was released with (its
environment.yml pins old builds that do not resolve with conda on Kaggle), downloads its
extra data, then for each of the held-out policies:
  plaintext -> html -> html_crawler -> init_document -> run_annotators -> build_graph
and runs analyses/flow-consistency on our PoliCheck-format export.

The three cases of a policy share one policy text, so each policy is processed once. The
flow check finds a policy directory by blake2s(privacy_policy_url), and reads flows.csv
without a header, so a PoliGraph copy of the export is written with one URL per policy and
no header row. Outputs go to /kaggle/working/poligraph/ and results.tar.gz.
"""
import csv
import glob
import hashlib
import html
import os
import re
import shutil
import subprocess
import tarfile
import time

WORK = "/kaggle/working"
REPO = f"{WORK}/dpdp-audit"
PG = f"{WORK}/PoliGraph"
ENV = f"{WORK}/pgenv"
PY = f"{ENV}/bin/python"
OUT = f"{WORK}/poligraph"
SPLIT = "real_flows"       # "main", "ladder", "real_flows", or "s4": statement extraction on the 35 held-out
                           # OPP-115 policies, built from their segments (WP-3.6, AC-05.6)
EXPORT = f"{REPO}/data/benchmark/{SPLIT}/export/policheck"
T_START = time.time()

PINS = [
    "torch==1.12.1+cu113", "spacy==3.5.3", "spacy-transformers==1.2.4", "transformers==4.28.1",
    "setfit==0.7.0", "sentence-transformers==2.2.2", "huggingface_hub==0.14.1", "datasets==2.12.0",
    "pyarrow==10.0.1", "preshed==3.0.6", "cymem==2.0.6", "murmurhash==1.0.7", "thinc==8.1.10",
    "srsly==2.4.6", "blis==0.7.9", "networkx==3.1", "pandas==1.5.3", "numpy==1.24.3",
    "playwright==1.32.1", "requests-cache==1.0.1", "cattrs==23.1.1", "attrs==22.1.0",
    "url-normalize==1.4.3", "tldextract==3.4.4", "inflect==6.0.4", "lxml==4.9.2",
    "pydantic==1.10.2", "anytree", "beautifulsoup4", "langdetect", "matplotlib", "regex",
    "requests", "unidecode", "pyyaml", "gdown",
    "en_core_web_trf @ https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_trf-3.5.0/en_core_web_trf-3.5.0-py3-none-any.whl",
]
EXTRA_DATA_ID = "1qHifRx93EfTkg2x1e2W_lgQAgk7HcXhP"


# Kaggle's image sets uv variables (e.g. UV_SYSTEM_PYTHON) that send installs to its own 3.13
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("UV_")}


def sh(cmd, **kw):
    print(f"+ [{time.time() - T_START:.0f}s] {cmd}", flush=True)
    return subprocess.run(cmd, shell=True, check=True, env=kw.pop("env", CLEAN_ENV), **kw)


def find_repo():
    tars = glob.glob("/kaggle/input/**/repo.tar.gz", recursive=True)
    if tars:
        with tarfile.open(tars[0]) as t:
            t.extractall(REPO)
        return
    roots = [os.path.dirname(p) for p in glob.glob("/kaggle/input/**/pyproject.toml", recursive=True)]
    shutil.copytree(roots[0], REPO)


def setup():
    sh("pip install -q uv")
    # Kaggle's own Python (3.13) has no wheels for torch 1.12: use a uv-managed 3.10
    sh("uv python install 3.10")
    sh(f"uv venv -q -p 3.10 --python-preference only-managed {ENV}")
    sh(f"{PY} --version")
    pins = " ".join(f'"{p}"' for p in PINS)
    sh(f"uv pip install -q --python {PY} --index-strategy unsafe-best-match "
       f"--extra-index-url https://download.pytorch.org/whl/cu113 {pins}")
    sh(f"git clone -q --depth 1 https://github.com/UCI-Networking-Group/PoliGraph.git {PG}")
    # html_crawler caches readability.js with requests-cache, whose cattrs serializer fails
    # here (NameError: RequestsCookieJar); the cache only saves one download, so drop it
    crawler = f"{PG}/poligrapher/scripts/html_crawler.py"
    src = open(crawler).read()
    old = 'CachedSession("py_request_cache", backend="filesystem", use_temp=True)'
    assert old in src, "html_crawler changed upstream"
    open(crawler, "w").write(src.replace(old, "requests.Session()"))
    sh(f"uv pip install -q --python {PY} -e {PG}")
    extra = f"{PG}/poligrapher/extra-data"
    os.makedirs(extra, exist_ok=True)
    sh(f"{ENV}/bin/gdown -q {EXTRA_DATA_ID} -O {WORK}/extra.tar.gz")
    sh(f"tar xf {WORK}/extra.tar.gz -C {extra} && rm {WORK}/extra.tar.gz")
    # html_crawler launches Firefox. playwright 1.32's --with-deps uses pre-24.04 package names
    # (libasound2 is libasound2t64 on Kaggle's Ubuntu 24.04), so install its libraries by name
    sh("apt-get install -y -q libgtk-3-0t64 libdbus-glib-1-2 libxt6t64 libx11-xcb1 libasound2t64 "
       "libnss3 libnspr4 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 "
       "libcairo2 libcairo-gobject2 libgdk-pixbuf-2.0-0 libxcursor1 libxi6 libxrender1 libxtst6 "
       "libpci3 > /dev/null")
    sh(f"{ENV}/bin/playwright install firefox")
    # spaCy uses the GPU only through cupy; keep it only if it actually works here
    try:
        sh(f'uv pip install -q --python {PY} "cupy-cuda11x==12.0.0"')
        sh(f'{PY} -c "import spacy; assert spacy.prefer_gpu()"')
        print("GPU: on", flush=True)
    except subprocess.CalledProcessError:
        subprocess.run(f"uv pip uninstall -q --python {PY} cupy-cuda11x", shell=True, env=CLEAN_ENV)
        print("GPU: off, running on CPU", flush=True)


def policy_key(case_id: str) -> str:
    """Main cases of a policy share its text; every ladder rung and real-flow app has its own text
    (real-flow package names may contain "_")."""
    return case_id if SPLIT in ("ladder", "real_flows") else case_id.split("_")[0]


def policy_url(policy_id: str) -> str:
    return f"https://www.p{re.sub(r'[^a-z0-9]', '', policy_id.lower())}.dpdpaudit.com/privacy"


def policy_dir(policy_id: str) -> str:
    return f"{OUT}/policies/{hashlib.blake2s(policy_url(policy_id).encode()).hexdigest()}"


def prepare_inputs() -> list[str]:
    """One html per policy, and a header-less flows.csv with one policy URL per policy."""
    index = list(csv.DictReader(open(f"{EXPORT}/flow_index.csv")))
    case_policy = {r["case_id"]: policy_key(r["case_id"]) for r in index}
    texts: dict[str, str] = {}
    for r in index:
        pid = case_policy[r["case_id"]]
        text = open(f"{EXPORT}/plaintext_policies/{r['package_name']}.txt").read()
        assert texts.setdefault(pid, text) == text, f"cases of policy {pid} differ in text"
    os.makedirs(f"{OUT}/html", exist_ok=True)
    os.makedirs(f"{OUT}/policies", exist_ok=True)
    dirs = []
    for pid, text in sorted(texts.items()):
        paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        body = "\n".join(f"<p>{html.escape(p)}</p>" for p in paras)
        path = f"{OUT}/html/{pid}.html"
        with open(path, "w") as f:
            f.write(f"<html><head><title>Privacy Policy</title></head><body>{body}</body></html>")
        dirs.append((pid, path))
    with open(f"{EXPORT}/flows.csv") as fin, open(f"{OUT}/flows_noheader.csv", "w", newline="") as fout:
        rows = list(csv.reader(fin))[1:]
        w = csv.writer(fout)
        for r in rows:
            r[8] = policy_url(policy_key(r[1]))
            w.writerow(r)
    print(f"{len(dirs)} policies, {len(rows)} flows", flush=True)
    return dirs


def prepare_inputs_s4() -> list[tuple[str, str]]:
    """One html per held-out policy: its OPP-115 segments in order, one <p> per line."""
    import json
    segs: dict[str, list] = {}
    for line in open(f"{REPO}/results/tagger/heldout.jsonl"):
        seg = json.loads(line)
        segs.setdefault(seg["policy_id"], []).append((seg["segment_id"], seg["text"]))
    os.makedirs(f"{OUT}/html", exist_ok=True)
    os.makedirs(f"{OUT}/policies", exist_ok=True)
    dirs = []
    for pid, items in sorted(segs.items()):
        lines = [l.strip() for _, text in sorted(items) for l in text.split("\n") if l.strip()]
        body = "\n".join(f"<p>{html.escape(l)}</p>" for l in lines)
        path = f"{OUT}/html/{pid}.html"
        with open(path, "w") as f:
            f.write(f"<html><head><title>Privacy Policy</title></head><body>{body}</body></html>")
        dirs.append((pid, path))
    print(f"{len(dirs)} policies, {sum(len(v) for v in segs.values())} segments", flush=True)
    return dirs


EXPORT_EDGES = """
import json, sys, yaml
out = {}
for pid, d in (a.split("=", 1) for a in sys.argv[2:]):
    g = yaml.safe_load(open(d + "/graph-original.yml"))
    out[pid] = [{k: e.get(k) for k in ("source", "target", "key", "text")} for e in g["links"]]
json.dump(out, open(sys.argv[1], "w"))
print("exported", len(out), "graphs,", sum(len(v) for v in out.values()), "edges")
"""


def main():
    find_repo()
    setup()
    policies = prepare_inputs_s4() if SPLIT == "s4" else prepare_inputs()
    workdirs = []
    for pid, path in policies:
        d = policy_dir(pid)
        try:
            sh(f"{PY} -m poligrapher.scripts.html_crawler {path} {d}")
            workdirs.append(d)
        except subprocess.CalledProcessError:
            print(f"crawl failed for policy {pid}", flush=True)
    with open(f"{OUT}/policy_dirs.csv", "w") as f:
        f.write("policy_id,dir\n" + "".join(f"{pid},{os.path.basename(policy_dir(pid))}\n" for pid, _ in policies))
    print(f"crawled {len(workdirs)} of {len(policies)} policies", flush=True)
    if not workdirs:
        raise RuntimeError("no policy was crawled; see the html_crawler errors above")
    dirs = " ".join(workdirs)
    for step in ("init_document", "run_annotators", "build_graph"):
        sh(f"{PY} -m poligrapher.scripts.{step} {dirs}", cwd=PG)
    if SPLIT == "s4":
        with open(f"{WORK}/export_edges.py", "w") as f:
            f.write(EXPORT_EDGES)
        built = [(pid, policy_dir(pid)) for pid, _ in policies
                 if os.path.exists(f"{policy_dir(pid)}/graph-original.yml")]
        args = " ".join(f"{pid}={d}" for pid, d in built)
        sh(f"{PY} {WORK}/export_edges.py {OUT}/poligraph_s4.json {args}")
        print(f"done in {time.time() - T_START:.0f}s: graphs for {len(built)} of {len(policies)} policies", flush=True)
        return
    fc = f"{PG}/analyses/flow-consistency"
    sh(f"{PY} {fc}/convert_flow_csv.py {OUT}/flows_noheader.csv {OUT}/dns_cache {OUT}/flows.json", cwd=PG)
    sh(f"{PY} {fc}/check-policheck-flow-consistency.py {OUT}/flows.json {OUT}/poligraph_results.csv "
       f"-p {OUT}/policies", cwd=PG)
    n = sum(1 for _ in open(f"{OUT}/poligraph_results.csv")) - 1
    print(f"done in {time.time() - T_START:.0f}s: {n} result rows", flush=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        with tarfile.open(f"{WORK}/results.tar.gz", "w:gz") as t:
            if os.path.isdir(OUT):
                t.add(OUT, arcname="poligraph")
        # keep the kernel output small: only results.tar.gz is needed
        for d in (ENV, PG, REPO, OUT):
            shutil.rmtree(d, ignore_errors=True)
