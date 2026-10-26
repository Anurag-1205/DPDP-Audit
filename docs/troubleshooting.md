# Troubleshooting

Problems already met in this project and their fixes. All fixes are in the code.

| Symptom | Cause | Fix |
|---|---|---|
| OPP-115 download runs at ~1 MB/min | The server throttles each connection | `scripts/download_opp115.sh` downloads 12 byte ranges in parallel |
| PoliCheck Docker build fails at `apt-get` | The 2020 Dockerfile uses archived Debian mirrors | `setup_policheck.sh` removes the `apt-get` lines |
| PoliCheck Docker build stalls for hours | The 852 MB spaCy model downloads slowly inside the build | Download it on the host (`data/external/models/`); the script installs it from the file |
| `gdown: unrecognized arguments: --fuzzy` | Newer gdown removed the flag | Pass the Google Drive file id directly |
| Every PoliCheck flow converted as "omitted" | PoliCheck reports ontology terms ("email address") and entities ("we"), not our tokens and domains | `tool_runs.POLICHECK_DATA_NAMES` maps them back |
| vLLM 0.6.3 does not install on Kaggle | Kaggle moved to Python 3.13 and PyTorch ≥ 2.5 | Use vLLM 0.10.2 ([infrastructure.md](infrastructure.md#why-vllm-0102)) |
| Latest vLLM crashes on import (`torchaudio` CUDA mismatch) | It installs a CUDA 13 PyTorch that conflicts with Kaggle's `torchaudio` | Pin vLLM 0.10.2 (PyTorch 2.8, CUDA 12.8) |
| `Qwen2Tokenizer has no attribute all_special_tokens_extended` | Kaggle's `transformers` is newer than vLLM supports | Pin `transformers==4.56.2` in both install steps |
| A 12-hour Kaggle session finishes only half the runs | On T4 the V1 engine falls back to FlexAttention (~10× slower) | `VLLM_USE_V1=0 VLLM_ATTENTION_BACKEND=XFORMERS` |
| `Cannot copy out of meta tensor` on the first B2 calls | Parallel threads loaded the embedding model at the same time | The model loads once behind a lock (`retrieval._model`) |
| `call failed: Request timed out` | The client's default timeout is too short for a busy server | `OPENAI_TIMEOUT=1800`; re-run with `--redo-failed` |
| Kernel runs the old code after an upload | The new dataset version takes minutes to become the mounted one | `kaggle_push.sh` waits 4 minutes after the upload |
| `repo.tar.gz` not found inside the kernel | Kaggle unpacks uploaded archives | The kernel accepts both forms (`find_repo`) |
| Kernel logs are empty while it runs | Kaggle shows logs only after the run ends | Watch `kaggle kernels status`; the job always packs partial results |
