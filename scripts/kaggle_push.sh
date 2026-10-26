#!/usr/bin/env bash
# Upload the repository (code + benchmark) as a private Kaggle dataset and run the B1/B2 kernel.
#   scripts/kaggle_push.sh            create or update the dataset, then push and run the kernel
# Results: kaggle kernels output anuragkaushal183/dpdp-audit-b1b2 -p outputs/kaggle \
#            --file-pattern '(results\.tar\.gz|\.log)$'  &&  tar xzf outputs/kaggle/results.tar.gz -C .
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KAGGLE="${KAGGLE:-$ROOT/.venv/bin/kaggle}"
STAGE="$ROOT/outputs/kaggle_dataset"
rm -rf "$STAGE" && mkdir -p "$STAGE"
RUNS=""; [ -d "$ROOT/results/runs" ] && RUNS="results/runs"   # resume from runs already done
tar czf "$STAGE/repo.tar.gz" -C "$ROOT" pyproject.toml requirements.txt src scripts data/dpdp data/tools data/splits.json data/benchmark/main $RUNS
cat > "$STAGE/dataset-metadata.json" <<JSON
{"title": "dpdp-audit", "id": "anuragkaushal183/dpdp-audit", "licenses": [{"name": "other"}]}
JSON
if "$KAGGLE" datasets status anuragkaushal183/dpdp-audit >/dev/null 2>&1; then
  "$KAGGLE" datasets version -p "$STAGE" -m "update code and benchmark"
else
  "$KAGGLE" datasets create -p "$STAGE"
fi
echo "waiting for the dataset to be ready..."
until "$KAGGLE" datasets status anuragkaushal183/dpdp-audit 2>/dev/null | grep -qi ready; do sleep 15; done
sleep 240   # the new version takes a few minutes to become the one kernels mount
"$KAGGLE" kernels push -p "$ROOT/kaggle/b1b2"
