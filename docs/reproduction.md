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

## 5. Scores

```bash
python scripts/score_runs.py --systems B1 B2 S1
```

This writes `results/scores/main.json` and prints the table in
[stage-1-report.md](stage-1-report.md). With 1,000 bootstrap re-samples it
takes about a minute.

## 6. Tests

```bash
pytest -q
```
