# DPDP-Audit: final plan, stage by stage

This plan matches the final proposal (`Neural_Nexus_Final.pdf`). Each stage lists the goal, the tasks per member, what must exist at the end, and the check that decides whether we move on. Members 1–4 follow the proposal's work split:

- **M1 — Anurag Kaushal:** data and benchmark
- **M2 — Ishaan Giri:** tools and existing systems
- **M3 — Naveen Mishra:** agent pipeline
- **M4 — Nikhil Patidar:** fine-tuning and evaluation

---

## Stage 0: Before Week 1 (setup, 2–3 days)

**Goal:** remove everything that can block us later.

| Who | Task |
|---|---|
| All | Agree roles; create a shared repo, a shared drive for data, and one results sheet. Confirm the proposal page limit with the TA. |
| M1 | **Send data requests today:** the OVRseen dataset form and PoliCheck's public dataset (policies + traffic). Download OPP-115 (consolidated annotations). |
| M2 | Pull the PoliCheck/PolicyLint repo and build its Docker image. Clone PoliGraph and PurPliance. Find a machine with about 32 GB RAM for PoliGraph. |
| M3 | Check that vLLM serves Qwen2.5-7B-Instruct (quantised) on Kaggle and returns token log-probabilities. Get a Gemini free-tier key. |
| M4 | Set up a QLoRA notebook for Qwen2.5-3B and download `mukund/privbert`. |

**Exit check:** data requests sent; Docker image builds; vLLM answers a test prompt with log-probs.

---

## Stage 1: Week 1 (benchmark and baselines run end to end)

**Goal:** a first version of the benchmark exists, and the simplest systems run on it.

| Who | Task | Output |
|---|---|---|
| M1 | Split OPP-115 by policy (~80 train / ~35 held-out). **Count usable cases per gap type × level.** Write the case generator and answer-key script. Give every flow a gold label (clear / vague / omitted / incorrect). Write the PoliCheck-format export. | `splits.json`, `cell_counts.csv`, `cases/`, `answer_keys/`, `export/` |
| M2 | Write the app parsers (`parse_deps`, `parse_perms`, `get_flows`) and the ~20-SDK table. Run PoliCheck, PoliGraph and PurPliance on **2 cases each**. Reproduce one published PoliCheck result on its own example data. | `tools/`, `sdk_table.csv`, tool smoke-test log |
| M3 | Build the DPDP Act + Rules section index (bge-small + FAISS) and the gap-to-section table. Implement the B1 and B2 single-pass baselines. | `dpdp_index/`, `gap_to_section.csv`, B1/B2 outputs on all cases |
| M4 | Write the scorer: finding-level P/R/F1, false-alarm rate, disclosure-label macro-F1, and a bootstrap that **resamples whole policies**. | `score.py` |

**Exit check (go / no-go):**
- B1 and B2 produce scores on all ~105 cases.
- If any gap type × level cell has **fewer than 10 cases**, merge it with its neighbouring level and mark it "exploratory".
- If a tool does not run after a full day, it becomes **related work only** and we note the limitation. Do not lose more time on it.

---

## Stage 2: Week 2 (full pipeline, fine-tuning, ladder)

**Goal:** the full system passes a 5-case pilot, and the ladder cases exist and are checked.

| Who | Task | Output |
|---|---|---|
| M1 | Build the **vagueness ladder**. For each held-out policy, pick one collection/sharing flow and delete every sentence the annotations mark as covering it (the base policy). Then insert one templated sentence at the same spot: clear, explicit or vague (or nothing for the deleted rung). Have **two members check every rung** against the level rules. No LLM writes or judges the rewrites. | `ladder/` (35 ladders × 4 rungs = 140 cases), check sheet |
| M2 | Write the ontology mapping table (OPP-115 terms → tool terms) and report the share mapped without loss. Export ladder cases for the tools. | `mapping.csv`, coverage number |
| M3 | Build the specialist reviewers, aggregator and evidence verifier. The verifier outputs a **confidence per flow**: seed agreement first, token probability as tie-break. Run the 5-case pilot and time it. | pipeline code, pilot timings |
| M4 | Fine-tune the QLoRA tagger (prompted tagger as a stand-in until it is ready) and PrivBERT on the same split. Set up the PolicyLint extraction comparison. | tagger checkpoints, tagger macro-F1 table |

**Exit check:** the pilot runs end to end on 5 cases. The time per run times about 2,600 runs fits the GPU budget; if not, cut ablation cases first and use Gemini as the fallback. All 140 ladder rungs are checked.

---

## Stage 3: Week 3 (all runs)

**Goal:** every result table has numbers.

| Who | Task |
|---|---|
| M3 | Main runs: full system, B1, B2 and B4 with **3 seeds**; A1–A5 with **1 seed**. Ladder runs: full system and B2 with 3 seeds. |
| M2 | Run PoliCheck, PoliGraph and PurPliance once on all their cases (main + ladder). |
| M4 | Score everything: common subset and full benchmark, per gap type and level, false alarms, citations. Score the tools both ways (one-to-one conversion and native reading). |
| M1 | Answer-key spot-check: 20 cases against the policy text, and report the error rate. |

**Run budget:** main ≈ 105 × (4 × 3 + 5 × 1) ≈ 1,800; ladder ≈ 140 × 2 × 3 ≈ 840; total about 2,600 LLM runs.

**Exit check:** all tables in §6.2 of the proposal are filled. Stretch goals start only after this point.

---

## Stage 4: Week 4 (review cost and real data)

**Goal:** selective-accuracy results, plus a check on real data.

| Who | Task |
|---|---|
| M4 | **Selective accuracy**, with flows as the unit:<br>• Sort by confidence, lowest first; a reviewed flow takes its gold label.<br>• Plot the accuracy of the unreviewed flows against the share reviewed.<br>• Report the curve area, **R@95** and the review needed to match the best tool. Tools are a single point.<br>• On the ladder, test whether confidence drops from the explicit to the vague rung. |
| M1 + M2 | **Real flows** (if data arrived): sample about 25 apps and 60–80 flows; both label them independently and report Cohen's κ. Run all systems. |
| M3 | **Open-source case study:** 3–5 repos with their own privacy policy. Write the data-flow configs from the code, run the pipeline and check every finding by hand. |
| M4 | **Ladder analysis:** label accuracy per rung, McNemar tests between rungs, and which neighbouring labels get confused (e.g. vague read as clear). |

**Exit check:** review-cost curves exist, real-data results come with κ, and case-study findings are checked. If no real-flow data arrived by the end of Week 2, the case study is the real-data result. Say so in the report.

---

## Stage 5: Week 5 (analysis and write-up, all members)

- Failure analysis: where the tools fail and where the LLM systems fail, with worked hard cases.
- Error attribution: tagging versus reasoning (A4 vs. A5).
- Check every hypothesis (H1–H6) and the falsifiable claim honestly, including the ones that fail.
- Release: generator code, answer keys, ladder templates, mapping table and PoliCheck export.
- Final report and slides.

---

## Rules we keep throughout

1. **No LLM decides what is right.** Answer keys and ladder rewrites come from scripts and templates, checked by people.
2. **Fixed before testing.** The mapping table, templates and thresholds are frozen before any test run. No system is tuned on evaluation cases.
3. **Vague counts two ways.** Report both our DPDP reading (vague = gap) and the tools' native reading (vague = consistent).
4. **Statistics by policy.** Cases from the same policy are not independent, so the bootstrap resamples policies.
5. **Scope.** Anything not in this plan is a stretch goal and starts only after Week 3.

## Still to confirm

- [ ] Page limit for the proposal (currently 10 pages).
- [x] Wording of DPDP Rule 3 in the official Gazette: confirmed, Rule 3(b)(i) "an itemised description of such personal data" (G.S.R. 846(E)).
- [x] Whether released PoliGraph code includes PoliGrapher-LM: it does not (NLP version only).
- [x] Whether PurPliance runs on our inputs: no. The release has only the statement extractor, not the flow-consistency checker (see docs/existing_tools.md). Team to decide: related work, or purpose-extraction component baseline.
- [ ] Whether ref [14] (arXiv:2607.17075) covers PoliCheck. Read the full text before writing about it.
