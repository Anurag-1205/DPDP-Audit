#!/usr/bin/env bash
# Upload code + benchmark as a private Kaggle dataset and run one tool kernel (kaggle/<tool>/).
#   scripts/kaggle_push_tool.sh poligraph
# Results: kaggle kernels output $KAGGLE_USER/dpdp-audit-<tool> -p outputs/kaggle/<tool>
set -euo pipefail
TOOL="$1"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KAGGLE="${KAGGLE:-kaggle}"
KAGGLE_USER="${KAGGLE_USER:-$(python3 -c "import json,os;print(json.load(open(os.path.expanduser('~/.kaggle/kaggle.json')))['username'])")}"
DATASET="$KAGGLE_USER/dpdp-audit"
STAGE="$ROOT/outputs/kaggle_dataset"
rm -rf "$STAGE" && mkdir -p "$STAGE"
EXTRA=""; [ -d "$ROOT/data/real_flows" ] && EXTRA="data/real_flows"   # real-flow sample (SPEC-08)
tar czf "$STAGE/repo.tar.gz" -C "$ROOT" pyproject.toml requirements.txt src scripts data/dpdp data/tools data/splits.json data/benchmark/main $EXTRA
cat > "$STAGE/dataset-metadata.json" <<JSON
{"title": "dpdp-audit", "id": "$DATASET", "licenses": [{"name": "other"}]}
JSON
if "$KAGGLE" datasets status "$DATASET" >/dev/null 2>&1; then
  "$KAGGLE" datasets version -p "$STAGE" -m "update code and benchmark"
else
  "$KAGGLE" datasets create -p "$STAGE"
fi
echo "waiting for the dataset to be ready..."
until "$KAGGLE" datasets status "$DATASET" 2>/dev/null | grep -qi ready; do sleep 15; done
sleep 240   # the new version takes a few minutes to become the one kernels mount
"$KAGGLE" kernels push -p "$ROOT/kaggle/$TOOL"
