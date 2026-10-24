# 6. Running everything, and problems we already hit

## Set up a laptop

```
git clone <repo-url> && cd <repo>
git config user.name "<your GitHub username>"; git config user.email "<your email>"
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt && pip install -e .
cp .env.example .env            # add GEMINI_API_KEY if you will use Gemini
pytest -q                       # 35 tests; some skip until the data below is downloaded
```

Needs Python 3.10+, `pdftotext` (poppler-utils) and Docker (for PoliCheck). No GPU is needed locally.
GPU work runs on Kaggle.

## Rebuild everything from scratch

| Step | Command | Time |
|---|---|---|
| Download OPP-115 (99 MB, 12 parallel ranges because the server is slow) | `scripts/download_opp115.sh` | a few minutes |
| DPDP PDFs into `data/raw/dpdp/` (links in `data/dpdp/SOURCES.md`), then split them | `python scripts/build_dpdp_sections.py` | seconds |
| DPDP search index | `python scripts/build_dpdp_index.py` | ~1 min (downloads bge-small) |
| Cell counts | `python scripts/count_cells.py` | seconds |
| Benchmark | `python scripts/generate_cases.py` | seconds |
| PoliCheck export | `python scripts/export_policheck.py --split main` | seconds |
| PoliCheck (once) | `scripts/tools/setup_policheck.sh` | 30–60 min (large downloads) |
| PoliCheck run | `python scripts/tools/run_policheck.py --cases 1028_control 1028_v1` | ~10 min for 2 cases |
| B1/B2 on Kaggle | `scripts/kaggle_push.sh` | ~45 min including setup |
| Scores | `python scripts/score_runs.py --systems B1 B2` | ~1 min |

The split (`data/splits.json`) and benchmark are already in git. Regenerating them with the same seeds
gives the same files.

## Running B1/B2 on Kaggle

You need a Kaggle API token in `~/.kaggle/kaggle.json`. `scripts/kaggle_push.sh` does four things:
1. Packs the code, benchmark and any existing runs, and uploads them as the **private** dataset
   `anuragkaushal183/dpdp-audit`.
2. Waits until Kaggle mounts the new version. It sleeps 4 extra minutes, because without that wait a
   kernel once started on the old version.
3. Pushes `kaggle/b1b2/run.py` as a GPU kernel on T4 ×2.
4. The kernel:
   - installs vLLM;
   - starts one Qwen server per GPU;
   - writes `stage0_model_check.json`;
   - runs B1/B2 in two shards;
   - scores the runs;
   - packs everything into `results.tar.gz`.

Get the results:

```
kaggle kernels output anuragkaushal183/dpdp-audit-b1b2 -p outputs/kaggle --file-pattern '(results\.tar\.gz|\.log)$'
tar xzf outputs/kaggle/results.tar.gz -C .
```

## Problems we hit and how they were solved

| Problem | Cause | Fix (already in the code) |
|---|---|---|
| OPP-115 download crawled at ~1 MB/min | The server limits each connection | Download 12 byte ranges in parallel (`download_opp115.sh`) |
| PoliCheck Docker build failed / took hours | 2020 Dockerfile: `apt-get` on archived Debian mirrors; an 852 MB spaCy model downloads very slowly inside the build | Drop the `apt-get` lines; fetch the spaCy model on the host in parallel ranges and install it from the file (`setup_policheck.sh`) |
| `gdown --fuzzy` error | Newer gdown removed the flag | Pass the Google Drive file id directly |
| PoliCheck output all "omitted" | It reports "email address"/"we", not our tokens/domains | Converter maps its names back (`tool_runs.POLICHECK_DATA_NAMES`) |
| vLLM 0.6.3 would not install on Kaggle | Kaggle moved to Python 3.13 and newer PyTorch | Use a newer vLLM |
| Latest vLLM crashed | It brings a CUDA 13 PyTorch that conflicts with Kaggle's `torchaudio` | Pin a release built for CUDA 12.8 |
| vLLM 0.11 crashed on the tokenizer | Kaggle's `transformers` was too new | Pin `transformers` to match vLLM |
| A 12-hour Kaggle session finished only 291 runs | On T4, vLLM ≥ 0.11 falls back to the slow FlexAttention | Use **vLLM 0.10.2 + V0 engine + xFormers** (`VLLM_USE_V1=0`): 612 runs in ~35 min |
| "Cannot copy out of meta tensor" on some B2 calls | Parallel threads loaded the embedding model at the same time | Load it once behind a lock (`retrieval._model`) |
| Some requests timed out | The client's default timeout was too short for the slow server | `OPENAI_TIMEOUT=1800` and `--redo-failed` |

## Things that are not in git

- `data/raw/`: OPP-115 and the DPDP PDFs.
- `data/external/`: the PoliCheck/PoliGraph/PurPliance repos and models.
- `outputs/cache/`: LLM replies and the FAISS index.
- `outputs/logs/`.
- `.env`: your API key. Never commit it.

Each person re-creates these with the commands above.
