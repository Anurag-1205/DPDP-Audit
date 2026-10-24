# 5. Baselines, existing tools and scoring

## The LLM client (`llm.py`)

One class, `LLM`, talks to two kinds of backend:

| Backend | Set with | Used for |
|---|---|---|
| `openai` | `LLM_BACKEND=openai`, `OPENAI_BASE_URL`, `OPENAI_MODEL` | Qwen2.5-7B-Instruct-AWQ served by vLLM on Kaggle (B1, B2) |
| `gemini` | `GEMINI_API_KEY`, `GEMINI_MODEL` in `.env` | B4 and as a fallback (`gemini-3-flash-preview`; "Gemini 3.5 Flash" is not available to our key) |

Every call is cached in `outputs/cache/llm/`, keyed by backend, model, prompt, seed and temperature, so
re-running costs nothing. Defaults: temperature 0.7, max 2,048 output tokens. Rate limits and timeouts
are retried with back-off. The vLLM backend also returns the answer's token probability, which Stage 4
needs for confidence.

## B1 and B2 (`baselines.py`)

Both send **one prompt** and ask for JSON with two things:
1. a disclosure label for every flow (`clear` / `vague` / `omitted` / `incorrect`);
2. a list of findings (flow, data type, gap type, level, DPDP sections, quoted evidence).

| | B1 | B2 |
|---|---|---|
| Policy text | yes | yes |
| App input | the raw files (`build.gradle`, manifest, `dataflows.json`) | facts parsed by the tools: SDKs found, permissions, flows |
| DPDP text | none | units retrieved from the DPDP index for each flow |
| Gap-type reference | descriptions only | descriptions + usual sections |

B2 gets exactly what the full agent will get, so any later gain of the agent over B2 comes from its
design, not from extra information. Replies are cleaned by `normalise`: unknown gap types are dropped,
and missing labels default to `clear`.

**Runner:** `scripts/run_baselines.py` runs jobs seed by seed (seed 0 of every system first). It skips
runs that already exist, and `--redo-failed` re-runs failed calls. `--shard i/n` splits cases between two
model servers, and `--deadline-min` stops starting new jobs after a time limit. A failed call is saved
with `parse_error: "call failed: ..."`, so one bad case never crashes the run.

## Existing tools

- **PoliCheck (S1)** runs in Docker. `tool_runs.policheck_outputs` converts its labels one to one:
  incorrect/ambiguous → explicit, vague → vague, omitted → omission, clear → no gap. PoliCheck names data
  by ontology terms ("email address") and recipients by entity ("we", "google ads"), so the converter
  maps them back to our flows.
- **PoliGraph (S2)** reads the same `flows.csv` and needs about 32 GB RAM. `scripts/tools/run_poligraph.sh`
  is ready for a bigger machine.
- **PurPliance (S3)** is dropped to related work, because its released code has no flow checker.

Details and the smoke test are in [existing_tools.md](existing_tools.md).

## Scoring (`score.py`, `scripts/score_runs.py`)

**Matching.** A predicted finding is correct when its *data type and gap type* match a key entry. Each
key entry can be matched only once, and the level is not required to match. Findings marked `uncertain`
count as not reported.

**Views.**
- **full:** all five gap types.
- **common:** only collection and sharing, the gap types PoliCheck and PoliGraph can see.
- **common_native:** the common view, but with vague gaps removed from the key and the predictions. This
  is PoliCheck's own reading, where vague counts as fine.

**Metrics.** These are the ones defined in [02_concepts.md](02_concepts.md):
- precision, recall and F1, overall and per gap type and level;
- false-alarm rate on controls;
- unsupported-finding rate;
- citation correctness (accepted sections in `gap_to_section.csv`);
- label macro-F1 over collection/sharing flows.

**Statistics.**
- The table reports the mean over the 3 seeds.
- 95% intervals come from 1,000 bootstrap re-samples of **whole policies**, on seed 0.
- `cluster_bootstrap(..., outs_b=...)` gives a paired difference between two systems on the same
  re-samples.

Example:

```
python scripts/score_runs.py --systems B1 B2
| system | seeds | f1_full | f1_common | f1_common_native | label_macro_f1 | false_alarm_rate | citation_correct |
| B1 | 3 | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.318 |
| B2 | 3 | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |
```

**Reading the results:**
- Both baselines find about a fifth of the gaps: F1 ≈ 0.18.
- B1 flags 97% of compliant apps.
- B2's parsed facts and DPDP text cut false alarms significantly. The paired difference on seed 0 is
  −0.29 [−0.47, −0.12].
- B2 cites the right section 89% of the time, against 32% for B1.
- B2 does not detect more gaps than B1.

More detail: [stage1_results.md](stage1_results.md).

Next: [06_running_and_troubleshooting.md](06_running_and_troubleshooting.md).
