# DPDP-Audit

Evidence-gated agent and controlled benchmark for checking app privacy compliance under India's DPDP Act.
See `Neural_Nexus_Final.pdf` for the proposal, `plan.md` for the stage-wise plan and `specs.md` for the
specification of the finished Stage 0–1 work and of Stage 2. **New to the project? Start with
[`docs/README.md`](docs/README.md)**, which explains everything from scratch.

## Layout

| Path | Contents |
|---|---|
| `src/dpdp_audit/` | Python package (data, benchmark, tools, baselines, scoring) |
| `scripts/` | Command-line entry points |
| `data/` | Derived data that is small enough to keep in git; raw downloads go to `data/raw/` (ignored) |
| `notebooks/` | Kaggle notebook for GPU runs (Qwen on vLLM) |
| `outputs/` | Model outputs and scores |

## Setup

```
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then add GEMINI_API_KEY
```

## Reproduce Stage 0 and Stage 1

| Step | Command | Output |
|---|---|---|
| OPP-115 | `scripts/download_opp115.sh` | `data/raw/OPP-115/` |
| DPDP text | see `data/dpdp/SOURCES.md`, then `python scripts/build_dpdp_sections.py` | `data/dpdp/sections.jsonl` |
| DPDP index | `python scripts/build_dpdp_index.py` | `outputs/cache/dpdp_index/` |
| Split | `python -c "from dpdp_audit.split import make_split; make_split()"` | `data/splits.json` (80 / 35 policies) |
| Cell counts | `python scripts/count_cells.py` | `data/benchmark/cell_counts.csv` |
| Main benchmark | `python scripts/generate_cases.py` | `data/benchmark/main/` (control + 2 variants per policy) |
| Tool export | `python scripts/export_policheck.py --split main` | `data/benchmark/*/export/policheck/` |
| PoliCheck | `scripts/tools/setup_policheck.sh`, then `python scripts/tools/run_policheck.py --cases <id> <id>` | `outputs/runs/<split>/S1/` |
| PoliGraph | `scripts/tools/run_poligraph.sh data/benchmark/main/export/policheck` (≥32 GB RAM) | `outputs/poligraph/` |
| B1 / B2 | `python scripts/run_baselines.py --systems B1 B2 --seeds 0 1 2` | `outputs/runs/main/B*/` |
| B1 / B2 on Kaggle | `scripts/kaggle_push.sh` (uploads code + benchmark as a private dataset, runs `kaggle/b1b2/run.py` on 2×T4) | `kaggle kernels output anuragkaushal183/dpdp-audit-b1b2` → `results.tar.gz` |
| Scores | `python scripts/score_runs.py --systems B1 B2 S1` | `outputs/scores/main.json` |
| Qwen on GPU | `notebooks/kaggle_qwen_vllm.ipynb` (Kaggle 2×T4) | same runs with `LLM_BACKEND=openai` |

Tests: `pytest -q`.

## Notes

- `docs/README.md`: reading order for the guides `docs/01_…` to `docs/06_…`.
- `docs/answer_key_rules.md`: the scripted answer-key rules and the decision on generic negative statements.
- `docs/existing_tools.md`: what the released PoliCheck, PoliGraph and PurPliance code can do, and the smoke test.
- `docs/stage1_results.md`: Stage 0 and Stage 1 status and baseline results.
