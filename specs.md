# Specifications

This file holds two specifications in the same format:

- **Part A (done):** Stage 0–1, the benchmark and single-pass baselines. Its acceptance criteria are
  ticked against what exists in the repository.
- **Part B (next):** Stage 2, the full pipeline, the vagueness ladder and the tagger. Its criteria are
  open.

Background for both: `docs/README.md` (reading order), `plan.md` (stages and owners) and
`Neural_Nexus_Final.pdf` (the proposal).

---

# Feature Specification: Stage 0–1 — Controlled benchmark and single-pass baselines

## 1. Context
- **Problem:** We need to measure how well systems find gaps between an app's privacy policy and what the
  app does, under India's DPDP Act. That needs test cases whose correct answers are known without an
  LLM or a team member deciding them.
- **Current Behavior:** Before this work the repository held only the proposal and the plan. There was
  no data, no test cases, no baselines and no way to score them.
- **Affected Systems:**
  - Python package `src/dpdp_audit/` and scripts `scripts/`.
  - Data `data/`: the OPP-115 corpus and the DPDP Act/Rules Gazette PDFs (downloaded, not in git).
  - PoliCheck (Docker image `benandow/pol-analysis`).
  - Kaggle (private dataset `anuragkaushal183/dpdp-audit`, kernel `anuragkaushal183/dpdp-audit-b1b2`).

## 2. Goal
- A scripted benchmark built from the 35 held-out OPP-115 policies (a compliant control and 2 variants
  per policy, each with an answer key), scored for the single-pass baselines B1 and B2 on every case.
  This is the Stage 1 exit check in `plan.md`.

## 3. Scope
- **Allowed Write Paths:**
  - `src/dpdp_audit/`, `scripts/`, `tests/`, `kaggle/`, `notebooks/`, `docs/`;
  - `data/splits.json`, `data/dpdp/`, `data/tools/`, `data/benchmark/`;
  - `outputs/runs/`, `outputs/scores/`, `outputs/tools/`, `outputs/stage0_model_check.json`;
  - `README.md`, `plan.md` (member names and open items only), `.gitignore`, `.env.example`,
    `requirements.txt`, `pyproject.toml`.
- **Read-Only Context:**
  - `Neural_Nexus_Final.pdf`;
  - `data/raw/OPP-115/` (corpus), `data/raw/dpdp/` (Gazette PDFs);
  - `data/external/` (authors' repositories of PoliCheck, PoliGraph, PurPliance).

## 4. Non-Goals
- The DPDP-Audit agent pipeline, the fine-tuned tagger and PrivBERT (Stage 2).
- The vagueness ladder and selective accuracy (Stage 2 / Stage 4).
- B4 (Gemini), ablations A1–A5, full runs of PoliCheck/PoliGraph (Stage 3).
- Real-flow data and the open-source case study (Stage 4).
- Any legal judgement: we report compliance gaps, not violations.

## 5. Acceptance Criteria
- [x] **Split:** OPP-115 split by policy into 80 train / 35 held-out (`data/splits.json`, seed 13).
- [x] **Cell counts:** usable cases counted per gap type × level (`data/benchmark/cell_counts.csv`).
  Cells with fewer than 10 policies are marked exploratory.
- [x] **Cases:** 102 generated (34 compliant controls, 68 variants), 118 gold findings, 433 flows with
  gold disclosure labels.
- [x] **Rule-based answer keys:** computed by fixed rules over expert annotations
  (`docs/answer_key_rules.md`). No LLM is involved, and case folders do not leak the answer.
- [x] **Controls are compliant:** every control has zero findings under the rules, and every variant has
  at least one.
- [x] **Edge case, no control possible:** a policy with no clearly covered flow is skipped, not given a
  wrong control (1 of 35).
- [x] **Edge case, hedged negatives:** generic "we do not share" statements are not treated as explicit
  contradictions. The decision is documented.
- [x] **App readers:** dependencies (gradle/npm/pip) to SDKs, Android permissions to data types, data-flow
  config, policy search, SDK table of 20 entries.
- [x] **DPDP text:** Act and Rules split into 153 citable units from the official Gazette; a gap-to-section
  table; a bge-small + FAISS index.
- [x] **PoliCheck export:** every case exported in PoliCheck format, with mapping coverage reported
  (65% exportable, 12% exact).
- [x] **PoliCheck:** builds and runs in Docker; smoke test on 2 cases; output converted back to our format.
- [x] **PoliGraph:** setup and run script written (needs ≥32 GB RAM).
- [x] **PurPliance:** dropped to related work with the reason documented (failure state: the tool cannot
  run).
- [x] **B1 and B2:** run on all 102 cases × 3 seeds on Qwen2.5-7B-Instruct (612 runs, 0 failed,
  0 unparseable).
- [x] **Failure handling, network:** a failed model call (timeout, context overflow) is saved as a failed
  run instead of crashing; `--redo-failed` re-runs it. Rate limits and transient errors are retried with
  back-off.
- [x] **Failure handling, Kaggle time limit:** jobs run seed-first; `--deadline-min` stops new work before
  the 12 h limit; results are always packed even on error.
- [x] **Scorer:** precision/recall/F1, false-alarm rate, citation correctness, label macro-F1, the common
  subset and the tools' native reading, and 95% intervals re-sampling whole policies.
- [x] **Stage 0 model check:** Qwen answers a test prompt with log-probabilities on Kaggle.
- [ ] **Stage 0 data request:** the OVRseen request form is not sent (see Open Questions).

## 6. Evidence & Validation
- `pytest -q` → 35 passed. Covers:
  - DPDP sections, gap table, retrieval (including parallel loading), app readers;
  - answer-key rules, benchmark integrity, PoliCheck export and output conversion;
  - LLM reply parsing, baselines, scorer.
- Regenerating the benchmark (`count_cells.py`, `generate_cases.py`, `export_policheck.py`) reproduces the
  files in git byte for byte.
- `outputs/stage0_model_check.json`: model reply "OK" with log-probabilities.
- `outputs/scores/main.json` and `docs/stage1_results.md` (mean of 3 seeds):

  | System | F1 | False alarms | Citation correct |
  |---|---|---|---|
  | B1 | 0.182 | 0.971 | 0.318 |
  | B2 | 0.181 | 0.745 | 0.894 |

  Paired B2 − B1 false alarms (seed 0): −0.29 [−0.47, −0.12].
- `outputs/tools/policheck/main/policheck_results.csv`: PoliCheck smoke-test output.

## 7. Open Questions
- **OVRseen data request:** someone must fill the form (it needs a person's name and agreement to the
  licence). It may be unnecessary, because PoliCheck's repository already has ~186k real flows with
  policy URLs.
- **B4 model:** the proposal names "Gemini 3.5 Flash", which our key cannot use. Confirm
  `gemini-3-flash-preview` and update the PDF.
- **PurPliance:** keep as related work only, or use its statement extractor as a purpose-extraction
  component baseline?
- **Proposal page limit:** the proposal is 10 pages; the earlier limit was 6–7. Confirm with the TA.

---

# Feature Specification: Stage 2 — Full pipeline, vagueness ladder and fine-tuned tagger

## 1. Context
- **Problem:** Stage 1 shows that single-pass LLM review over-flags compliant apps (false-alarm rate
  0.75–0.97) and finds about a fifth of the gaps. The proposal's evidence-gated pipeline and its two
  evaluation novelties do not exist yet. OPP-115 also lacks enough explicit and omitted
  collection/sharing cases, so those cells are exploratory.
- **Current Behavior:** Only B1/B2 and the scorer run. There is no clause tagger, no reviewer agents, no
  verifier, no per-flow confidence and no ladder cases.
- **Affected Systems:**
  - Package `src/dpdp_audit/`: new `pipeline/`, `ladder.py`, tagger modules.
  - `data/benchmark/ladder/`.
  - Kaggle GPU kernels for Qwen inference, QLoRA training and PrivBERT.

## 2. Goal
- The full DPDP-Audit pipeline passes a 5-case pilot end to end, with timing that fits the ~2,600-run
  budget.
- The vagueness ladder (35 ladders × 4 rungs = 140 cases) is generated and checked by two members.
- The QLoRA tagger and PrivBERT are trained and scored on the same OPP-115 split.

## 3. Scope
- **Allowed Write Paths:**
  - `src/dpdp_audit/pipeline/` (tagger, mismatch finder, reviewers, aggregator, verifier),
    `src/dpdp_audit/ladder.py`, `src/dpdp_audit/tagger_data.py`, `src/dpdp_audit/tagger_eval.py`;
  - new scripts in `scripts/`, new tests in `tests/`, new kernels and notebooks in `kaggle/` and
    `notebooks/`;
  - `data/benchmark/ladder/`, `data/tagger/`;
  - `outputs/runs/`, `outputs/scores/`, `outputs/tagger/`;
  - `docs/`.
- **Read-Only Context:**
  - `data/benchmark/main/` (frozen; do not regenerate or edit answer keys);
  - `src/dpdp_audit/gold_rules.py`, `score.py`, `baselines.py` (change only through a reviewed PR);
  - `data/dpdp/`, `data/tools/` mapping tables (frozen before test runs);
  - `Neural_Nexus_Final.pdf`, `plan.md`.

## 4. Non-Goals
- Full runs of all systems and ablations (Stage 3).
- Selective-accuracy curves and real-flow evaluation (Stage 4). Only the per-flow confidence needed for
  them is built now.
- Changing the main benchmark, its answer keys or the scorer's metric definitions.
- Any LLM writing or judging answer keys or ladder sentences.

## 5. Acceptance Criteria
- [ ] **Ladder (M1):** for each held-out policy, one collection or sharing flow is chosen. Every sentence
  the annotations mark as covering it (including generic data) is removed, and one templated sentence is
  inserted at the same place. Four rungs result: clear, explicit, vague, deleted. The app is identical
  across rungs.
- [ ] **Ladder check:** the rungs differ only by the inserted sentence (automated test). Base-policy
  sentences that still mention the data type are flagged. Two members fill the check sheet, and only
  rungs both mark "ok" are used.
- [ ] **Mapping (M2):** the ontology mapping is frozen, its coverage is reported, and the ladder cases are
  exported for PoliCheck/PoliGraph.
- [ ] **Pipeline (M3):** tagger → mismatch finder → 4 specialist reviewers (tool calls: `search_policy`,
  `retrieve_dpdp`, `lookup_sdk`) → aggregator → evidence verifier. A finding survives only if its quote
  appears in the policy and its cited section exists.
- [ ] **Confidence:** per-flow confidence from agreement across 3 seeds, with token probability as a
  tie-break.
- [ ] **Ablation switches:** A1 (no verifier), A2 (no RAG), A3 (one generalist reviewer, no aggregator),
  A4 (prompted tagger), A5 (oracle tagger) are configuration flags, not copies of code.
- [ ] **Edge cases:** empty candidate lists, a reviewer reply that is not JSON, a tool call to an unknown
  tool, a quote not found in the policy, a section that does not exist, a prompt longer than the context
  window.
- [ ] **Failure handling:** a failed model call is saved as a failed run; runs resume; Kaggle jobs stop
  before the time limit and save results.
- [ ] **Tagger (M4):** QLoRA Qwen2.5-3B and PrivBERT trained on the 80 training policies and evaluated on
  the 35 held-out ones. The prompted 3B tagger (B3) is evaluated the same way.
- [ ] **Pilot:** the full pipeline runs on 5 cases; time per run × ~2,600 runs fits the GPU budget. If not,
  cut ablation cases first.

## 6. Evidence & Validation
- Unit tests:
  - ladder rungs are a pure insertion over the deleted rung;
  - tagger output cleaning;
  - mismatch-finder candidates;
  - reviewer tool loop and verifier, using a scripted fake LLM (no API needed);
  - section-name normalisation;
  - per-seed confidence.
- `pytest -q` passes, and the existing 35 tests still pass.
- Pilot log: seconds and LLM calls per run (`outputs/logs/pipeline_timing_main.jsonl`).
- Tagger table: category macro-F1 (10 OPP-115 categories) and tuple F1 for B3, QLoRA and PrivBERT
  (`scripts/eval_tagger.py`).
- Filled ladder check sheet (`data/benchmark/ladder/check_sheet.csv`).

## 7. Open Questions
- **Which ladder flows?** Proposed: two sharing ladders for every collection ladder, using data types
  PoliCheck can express.
- **Fine-tuned tagger in the pipeline:** serve it as a LoRA adapter on vLLM next to Qwen-7B, or tag every
  policy offline once and cache the output?
- **Kaggle budget:** with ~30 GPU-hours per week per account, how do we spread pilot, training and Stage 3
  runs across the team's accounts?
- **PoliGraph:** who has access to a ≥32 GB RAM machine?
