# Reproduction guide

Every result in `results/` can be regenerated with the commands below. Steps that need no GPU run on a
laptop; GPU steps run on Kaggle. Set up the environment first ([developer-guide.md](developer-guide.md)).

## 1. Inputs

| Step | Command | Output | Time |
|---|---|---|---|
| OPP-115 corpus (99 MB, 12 parallel ranges) | `scripts/download_opp115.sh` | `data/raw/OPP-115/` | minutes |
| DPDP Act and Rules PDFs | download the two files listed in `data/dpdp/SOURCES.md` into `data/raw/dpdp/` | `dpdp_act_2023.pdf`, `dpdp_rules_2025.pdf` | seconds |
| DPDP units | `python scripts/build_dpdp_sections.py` | `data/dpdp/sections.jsonl` (153 units) | seconds |
| DPDP index | `python scripts/build_dpdp_index.py` | `outputs/cache/dpdp_index/` | ~1 min |

## 2. Benchmark

| Step | Command | Output |
|---|---|---|
| Split (already committed) | `python -c "from dpdp_audit.split import make_split; make_split()"` | `data/splits.json` |
| Cell counts | `python scripts/count_cells.py` | `data/benchmark/cell_counts.csv` |
| Main benchmark | `python scripts/generate_cases.py` | `data/benchmark/main/` |
| Tool export | `python scripts/export_policheck.py --split main` | `data/benchmark/main/export/policheck/` |
| Vagueness ladder | `python scripts/build_ladder.py && python scripts/export_policheck.py --split ladder` | `data/benchmark/ladder/` |
| Dev split (training policies) | `python scripts/generate_cases.py --split dev --policy-set train --n-policies 12` | `data/benchmark/dev/` |
| Second dev split (v2) | `python scripts/generate_cases.py --split dev2 --policy-set train --n-policies 24 --exclude-splits dev` | `data/benchmark/dev2/` |

`generate_cases.py` deletes the split folder first, so run the export again afterwards.

**Check:** `git status data/` shows no changes. The regeneration is byte-identical.

## 3. Existing tools

**PoliCheck (laptop, Docker):**

```bash
scripts/tools/setup_policheck.sh                         # once: image, spaCy model, NLP model
python scripts/tools/run_policheck.py --split main --cases 1028_control 1028_v1   # smoke test
python scripts/tools/run_policheck.py --split main       # all cases
```

The converted runs go to `results/runs/main/S1/seed0/`, and the raw CSV to
`results/tools/policheck/main/`.

**PoliGraph (Nikhil's workstation, ≥ 32 GB RAM):**

```bash
scripts/tools/run_poligraph.sh data/benchmark/main/export/policheck
```

Output: `results/tools/poligraph/main/poligraph_results.csv`.

## 4. LLM systems on Kaggle

Requires a Kaggle API token in `~/.kaggle/kaggle.json`.

```bash
scripts/kaggle_push.sh        # upload code + benchmark + existing runs, push the GPU kernel
# when the kernel has finished:
kaggle kernels output anuragkaushal183/dpdp-audit-b1b2 -p outputs/kaggle \
       --file-pattern '(results\.tar\.gz|\.log)$'
tar xzf outputs/kaggle/results.tar.gz -C .     # unpacks results/ and outputs/logs/
```

- **Runtime:** about 45 minutes for all 612 B1/B2 runs on 2× T4, including installation and server
  start-up.
- **Stage 0 model check:** recorded in `results/stage0_model_check.json`.
- **Interactive alternative:** `notebooks/kaggle_qwen_vllm.ipynb`.

### Pipeline, tagger and tools on Kaggle (one account)

`scripts/kaggle_push_job.sh <job> [<job> ...]` uploads code, every split and `results/` as the private
dataset `<kaggle user>/dpdp-audit`, then pushes `kaggle/<job>/` (the kernel metadata names the owner).

| Job | What it runs | Output |
|---|---|---|
| `pipeline` | Prompted tagger (Qwen2.5-3B) over every paragraph, then the pipeline (Qwen2.5-7B-AWQ); the phases are the `JOBS` list at the top of `kaggle/pipeline/run.py` | `results/tagger/claims/prompted.jsonl`, `results/pipeline_pilot.json`, `results/runs/<split>/<config>/` |
| `qlora` | QLoRA training (`scripts/train_tagger.py`), merged model served with vLLM, fine-tuned claims | `results/tagger/claims/finetuned.jsonl`, `results/tagger/qlora_training_info.json`, `qlora_adapter.tar.gz` |
| `policheck`, `poligraph` | The tools on `SPLIT` (top of each `run.py`) | raw CSVs in the kernel's `results.tar.gz` |

```bash
kaggle kernels output <user>/dpdp-audit-<job> -p outputs/kaggle/<job> --file-pattern '(results\.tar\.gz|\.log)$'
tar xzf outputs/kaggle/<job>/results.tar.gz -C .                         # pipeline, qlora
python scripts/convert_tool_runs.py --split ladder --tools S1 S2           # after copying the tool CSVs
```

### Re-verifying saved runs (fixed verifier reader)

`*_rv` runs re-run only the verifier on saved pipeline runs (needs the 7B model, e.g. the `reverify`
phase of `kaggle/pipeline/run.py`):

```bash
python scripts/reverify.py --split main --systems full full_finetuned full_v2 full_v2_finetuned --seeds 0 1 2
python scripts/reverify.py --split main --systems A2 A3 A5 A2_v2 A3_v2 A5_v2 --seeds 0
```

## 5. Scores

```bash
python scripts/score_runs.py --systems B1 B2 B4 S1 S2 full full_finetuned A1 A2 A3 A5 full_v2 full_v2_finetuned \
    A1_v2 A2_v2 A3_v2 A5_v2 --paired full_v2-full full_v2_finetuned-full_finetuned full_v2_finetuned-B2 …
python scripts/score_runs.py --split dev --systems full v2_gate v2_read v2_purpose v2_batch   # and --split dev2
python scripts/score_dev_pooled.py            # dev + dev2 pooled: the v2 choice (docs/pipeline.md#v2)
python scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned full_v2 full_v2_finetuned
python scripts/eval_tagger.py --gold results/tagger/heldout.jsonl \
    --pred B3=results/tagger/B3_pred.jsonl S3=results/tagger/S3_pred.jsonl --claims prompted finetuned
```

This writes `results/scores/main.json` and prints the table in
[stage-1-report.md](stage-1-report.md). With 1,000 bootstrap re-samples it
takes about a minute.

## 6. Tests

```bash
pytest -q
```
