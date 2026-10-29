#!/usr/bin/env bash
# Regenerate every score file in results/scores/ from the committed runs (no GPU, about 2 minutes).
# Needs the OPP-115 download (scripts/download_opp115.sh) for the tagger scores.
#   bash scripts/score_all.sh
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONPATH="$PWD/src${PYTHONPATH:+:$PYTHONPATH}"
PY=${PYTHON:-python}

# main benchmark: 27 systems, 59 paired comparisons (seed 0)
$PY scripts/score_runs.py --systems \
    B1 B2 S1 S2 B4 full A1 A2 \
    A3 A5 full_finetuned full_v2 full_v2_finetuned A1_v2 A2_v2 A3_v2 \
    A5_v2 full_rv full_finetuned_rv full_v2_rv full_v2_finetuned_rv A2_rv A3_rv A5_rv \
    A2_v2_rv A3_v2_rv A5_v2_rv \
  --paired \
    B2-B1 B4-B2 full-B2 full-B1 full-S1 full-S2 full-B4 full-A1 \
    full-A2 full-A3 A5-full full_finetuned-full full_finetuned-B2 full_finetuned-S1 full_finetuned-S2 A5-full_finetuned \
    full_v2-full full_v2_finetuned-full_finetuned full_v2_finetuned-full_v2 full_v2-B2 full_v2-B1 full_v2-S1 full_v2-S2 full_v2-B4 \
    full_v2_finetuned-B2 full_v2_finetuned-B1 full_v2_finetuned-S1 full_v2_finetuned-S2 full_v2_finetuned-B4 full_v2_finetuned-A1_v2 full_v2_finetuned-A2_v2 full_v2_finetuned-A3_v2 \
    A5_v2-full_v2_finetuned full_rv-full full_rv-B2 full_rv-B1 full_rv-S1 full_rv-S2 full_rv-A1 full_finetuned_rv-B2 \
    full_v2_rv-full_rv full_v2_finetuned_rv-full_finetuned_rv full_v2_finetuned_rv-full_v2_finetuned full_v2_finetuned_rv-full_v2_rv full_v2_finetuned_rv-B2 full_v2_finetuned_rv-B1 full_v2_finetuned_rv-S1 full_v2_finetuned_rv-S2 \
    full_v2_finetuned_rv-B4 full_v2_finetuned_rv-A1_v2 full_v2_finetuned_rv-A2_v2_rv full_v2_finetuned_rv-A3_v2_rv A5_v2_rv-full_v2_finetuned_rv full_rv-A2_rv full_rv-A3_rv A5_rv-full_rv \
    full_finetuned_rv-S1 full_finetuned_rv-S2 full_finetuned_rv-full_rv

# dev splits (training policies) and the pooled v2 choice
for split in dev dev2; do
  $PY scripts/score_runs.py --split "$split" --systems full v2_gate v2_read v2_purpose v2_batch full_rv v2_gate_rv v2_read_rv v2_purpose_rv v2_batch_rv
done
$PY scripts/score_dev_pooled.py

# vagueness ladder (accepted rungs only), clause tagger, answer-key spot-check
$PY scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned full_v2 full_v2_finetuned
$PY scripts/eval_tagger.py --gold results/tagger/heldout.jsonl \
    --pred B3=results/tagger/B3_pred.jsonl S3=results/tagger/S3_pred.jsonl --claims prompted finetuned
$PY scripts/spot_check.py score
