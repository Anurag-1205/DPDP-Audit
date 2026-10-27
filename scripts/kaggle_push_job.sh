#!/usr/bin/env bash
# Upload code + every benchmark split + existing results as a private Kaggle dataset, then push
# one or more kernel folders (kaggle/<job>/). The owner is the Kaggle user of ~/.kaggle/kaggle.json unless
# KAGGLE_USER is set; the kernel's metadata must name the same owner.
#   scripts/kaggle_push_job.sh pipeline            (or several: policheck poligraph)
# Results: kaggle kernels output $KAGGLE_USER/dpdp-audit-<job> -p outputs/kaggle/<job> \
#            --file-pattern '(results\.tar\.gz|\.log)$' && tar xzf outputs/kaggle/<job>/results.tar.gz -C .
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KAGGLE="${KAGGLE:-$ROOT/.venv/bin/kaggle}"
KAGGLE_USER="${KAGGLE_USER:-$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['username'])")}"
DATASET="$KAGGLE_USER/dpdp-audit"
STAGE="$ROOT/outputs/kaggle_dataset"
rm -rf "$STAGE" && mkdir -p "$STAGE"
# explicit file list: never secrets (.env) or local scratch (outputs/)
tar czf "$STAGE/repo.tar.gz" -C "$ROOT" pyproject.toml requirements.txt src scripts kaggle \
    data/dpdp data/tools data/splits.json data/benchmark results
cat > "$STAGE/dataset-metadata.json" <<JSON
{"title": "dpdp-audit", "id": "$DATASET", "licenses": [{"name": "other"}]}
JSON
if "$KAGGLE" datasets status "$DATASET" >/dev/null 2>&1; then
  "$KAGGLE" datasets version -p "$STAGE" -m "update code, benchmark and results"
else
  "$KAGGLE" datasets create -p "$STAGE"
fi
echo "waiting for the dataset to be ready..."
until "$KAGGLE" datasets status "$DATASET" 2>/dev/null | grep -qi ready; do sleep 15; done
sleep 240   # the new version takes a few minutes to become the one kernels mount
for JOB in "$@"; do "$KAGGLE" kernels push -p "$ROOT/kaggle/$JOB"; done
