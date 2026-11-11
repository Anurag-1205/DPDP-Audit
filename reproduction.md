# Reproduction guide

Every result in `results/` can be regenerated with the commands below. Steps that need no GPU run on a
laptop; GPU steps run on Kaggle. Set up the environment first ([developer-guide.md](docs/developer-guide.md)).

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

## 5. Stage 4: real flows and the open-source case study

These inputs are committed, so the scores in §6 need none of the steps below. They are listed to
rebuild the data or re-run a system.

**Real-flow sample** (SPEC-08, AC-08.1; [stage-4-plan.md](docs/stage-4-plan.md) §2–3):

```bash
git clone --depth 1 https://github.com/benandow/PrivacyPolicyAnalysis.git data/external/PrivacyPolicyAnalysis
python scripts/sample_real_flows.py --n 30 --max-tried 150   # Wayback copies of 2019 policies (rate-limited)
python scripts/build_real_flows.py                           # data/real_flows/sample.csv + data/benchmark/real_flows/cases/
```

`scripts/kaggle_push_job.sh real_flows` runs the sampler on Kaggle instead, from another IP address.

**Two-person labels** (AC-08.2; [real-flow-labelling.md](docs/real-flow-labelling.md)):

```bash
python scripts/real_flow_labels.py pack                       # reading packs in outputs/review/
python scripts/real_flow_labels.py copies <name>              # one private sheet per labeller
python scripts/real_flow_labels.py merge naveen anurag        # agreement and Cohen's kappa
python scripts/real_flow_labels.py disagreements naveen anurag
python scripts/real_flow_labels.py settle && python scripts/real_flow_labels.py keys   # answer keys
```

**Runs** (AC-08.3, AC-08.4), all as frozen:

```bash
scripts/kaggle_push_job.sh policheck poligraph   # S1, S2 on the real flows
scripts/kaggle_push_job.sh pipeline              # B1, B2, full_v2_rv on the real flows (JOBS in run.py)
scripts/kaggle_push_job.sh real_flows_finetuned  # full_v2_finetuned_rv with the 29 Oct QLoRA adapter
python scripts/build_case_study.py               # data/case_study/ -> data/benchmark/case_study/cases/
scripts/kaggle_push_job.sh case_study            # full_v2_finetuned_rv and B2, seeds 0-2
```

Each job's output unpacks onto the repository root (see the header of `scripts/kaggle_push_job.sh`).
The case study has no answer keys: every finding is checked by hand in `data/case_study/findings.csv`.

## 6. Scores

```bash
bash scripts/score_all.sh     # every file in results/scores/, from the committed runs; no GPU, ~2 min
```

The script lists the exact commands: `score_runs.py` on main (27 systems, 59 paired comparisons) and on
`dev` / `dev2`, `score_dev_pooled.py` (the v2 choice, [pipeline.md](docs/pipeline.md#v2)), `score_ladder.py`
(accepted rungs only), `score_ablations.py` (v2 ablations per seed), `eval_tagger.py --s4` (taggers and S4;
needs the OPP-115 download), `spot_check.py score`, `export_confidence.py` (per-flow confidence), the real flows (`convert_tool_runs.py --split real_flows`, `score_real_flows.py`), `selective_accuracy.py` (SPEC-07) and the failure analysis (`cost_table.py`, `error_tally.py`).
`python scripts/interval_tables.py` prints the report's interval tables (Appendix A). Run
on a fresh clone it rewrites `results/scores/` byte for byte (checked 29 Oct and again on 11 Nov),
so `git status` stays clean; only the two PNG figures in `results/figures/` may differ in pixels
with another matplotlib version. Bootstrap intervals use 1,000 re-samples with seed 0.

## 7. Tests

```bash
pytest -q
```
