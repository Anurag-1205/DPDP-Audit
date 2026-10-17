#!/usr/bin/env bash
# Run PoliGraph-er and its flow-consistency check on exported benchmark cases.
# Needs ~32 GB RAM (GPU optional); run it on a larger machine than a laptop.
#
#   scripts/tools/run_poligraph.sh data/benchmark/main/export/policheck
#
# The export directory is the one written by scripts/export_policheck.py:
#   plaintext_policies/<package>.txt   and   flows.csv (PoliCheck format)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
EXPORT="$(cd "$1" && pwd)"
REPO="$ROOT/data/external/PoliGraph"
WORK="$ROOT/outputs/poligraph"

if [ ! -d "$REPO" ]; then
  git clone --depth 1 https://github.com/UCI-Networking-Group/PoliGraph.git "$REPO"
fi
cd "$REPO"
if ! conda env list | grep -q '^poligraph '; then
  conda env create -n poligraph -f environment.yml
fi
# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate poligraph
pip install -q --editable .
playwright install chromium
if [ ! -d poligrapher/extra-data ] || [ -z "$(ls -A poligrapher/extra-data 2>/dev/null)" ]; then
  pip install -q gdown
  gdown 1qHifRx93EfTkg2x1e2W_lgQAgk7HcXhP -O /tmp/poligrapher-extra-data.tar.gz
  mkdir -p poligrapher/extra-data && tar xf /tmp/poligrapher-extra-data.tar.gz -C poligrapher/extra-data
fi

mkdir -p "$WORK/policies"
for txt in "$EXPORT"/plaintext_policies/*.txt; do
  pkg="$(basename "$txt" .txt)"
  html="$WORK/policies/$pkg.html"
  { echo "<html><body>"; sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/^$/<\/p><p>/' "$txt"; echo "</body></html>"; } > "$html"
  python -m poligrapher.scripts.html_crawler "file://$html" "$WORK/policies/$pkg"
done
python -m poligrapher.scripts.init_document "$WORK"/policies/*/
python -m poligrapher.scripts.run_annotators "$WORK"/policies/*/
python -m poligrapher.scripts.build_graph "$WORK"/policies/*/

python analyses/flow-consistency/convert_flow_csv.py "$EXPORT/flows.csv" "$WORK/flows.json"
python analyses/flow-consistency/check-policheck-flow-consistency.py "$WORK/flows.json" "$WORK/poligraph_results.csv" -p "$WORK/policies"
echo "Results: $WORK/poligraph_results.csv"
