# Stage 0 and Stage 1: status and results

## Stage 0 (setup)

| Item | Status |
|---|---|
| Roles | M1 Anurag Kaushal (data and benchmark), M2 Ishaan Giri (tools), M3 Naveen Mishra (agent pipeline), M4 Nikhil Patidar (fine-tuning and evaluation) |
| Shared repo | this repository; results in `outputs/` |
| Dataset requests | OVRseen request form **not sent** (needs a team member's name and agreement to the licence). Not needed before Stage 4; PoliCheck's repository already ships ~186k real flows with policy URLs. |
| PoliCheck in Docker | builds and runs (`scripts/tools/setup_policheck.sh`) |
| Qwen on Kaggle | Qwen2.5-7B-Instruct-AWQ served with vLLM 0.10.2 (V0 engine, xFormers attention) on 2×T4; answers a test prompt with log-probabilities (`outputs/stage0_model_check.json`) |

## Stage 1 (benchmark and simplest baselines)

**Benchmark (M1).** 35 held-out OPP-115 policies (80 train / 35 held out) → 102 cases: 34 compliant
controls and 68 variants with 1–2 planted flows; 118 gold findings, 433 flows with gold disclosure labels
(`data/benchmark/main/`). Answer keys come from fixed rules over the expert annotations
(`docs/answer_key_rules.md`). One policy has no clearly disclosed flow and gives no control.

**Cells (M1).** `data/benchmark/cell_counts.csv`. Explicit and omitted collection/sharing gaps exist in only
2–3 held-out policies each, children's omission in 8, purpose explicit in none: these cells are kept with
their true labels and reported as exploratory (plan rule: cells under 10).

**Tools (M2).** App readers, SDK table and policy search in `src/dpdp_audit/tools/`. PoliCheck runs (smoke test
on `1028_control`, `1028_v1`); PoliGraph needs ~32 GB RAM and has a ready script; PurPliance is dropped to
related work because its public code has no flow checker. Details: `docs/existing_tools.md`.
The PoliCheck export can express 65% of benchmark flows (12% exactly) in PoliCheck's data vocabulary.

**Retrieval and baselines (M3).** DPDP Act and Rules split into 153 citable units from the Gazette texts;
bge-small + FAISS index. B1 (raw inputs) and B2 (parsed app facts + retrieved DPDP sections) run on all
102 cases with 3 seeds each on Qwen2.5-7B-Instruct (612 runs, 0 failed, 0 unparseable).

**Scoring (M4).** `scripts/score_runs.py`: finding-level P/R/F1, false-alarm rate, citation correctness,
disclosure-label macro-F1, the common subset and the tools' native reading of vague disclosures, and 95%
intervals that resample whole policies.

### Baseline results (mean over 3 seeds; `outputs/scores/main.json`)

| System | F1 (full) | F1 (collection/sharing) | same, vague = consistent | Label macro-F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| B1 single prompt, raw inputs | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.318 |
| B2 single prompt, parsed facts + DPDP text | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |

Seed 0 with 95% policy-level bootstrap intervals: F1 B1 0.184 [0.145, 0.224], B2 0.188 [0.145, 0.233];
false-alarm rate B1 0.971 [0.912, 1.000], B2 0.676 [0.529, 0.824]. Paired B2 − B1 (seed 0):
F1 +0.004 [−0.027, 0.035], false alarms −0.294 [−0.471, −0.118].

Recall by level (seed 0): B1 explicit 0.24 / vague 0.68 / omission 0.15; B2 explicit 0.21 / vague 0.50 / omission 0.27.

**Reading.** A single prompt to a 7B model flags almost every compliant app (B1 false-alarm rate 0.97).
Giving it parsed facts and DPDP text (B2) cuts false alarms by about a third and makes citations mostly
correct, but does not improve detection F1. Explicit contradictions are found least often.

### PoliCheck smoke test

On `1028_control` PoliCheck labels the three compliant flows *vague* (gold: clear); on `1028_v1` it labels the
planted `serial number -> Google Ads` flow *ambiguous* (gold: vague). Raw output:
`outputs/tools/policheck/main/policheck_results.csv`.

## Notes for the next stage

- "Gemini 3.5 Flash" (proposal, B4) is not available to the team's API key; `gemini-3-flash-preview` works and
  is the default (`.env`, `GEMINI_MODEL`).
- On Kaggle T4s, vLLM ≥ 0.11 falls back to FlexAttention, which ran ~10× slower (one 12 h session for 291
  runs); vLLM 0.10.2 with the V0 engine and xFormers runs all 612 runs in ~35 min on two T4s
  (`kaggle/b1b2/run.py`, `scripts/kaggle_push.sh`).
