# DPDP-Audit — Mid-submission report (Stage 2)

- **Date:** 27 October 2026 (submission due 30 October)
- **Team:** Anurag Kaushal · Ishaan Giri · Naveen Mishra · Nikhil Patidar
- **Covers:** MS-0 to MS-2 · SPEC-01 to SPEC-06 · plan §7 (must-have package)
- **Reproduce:** every number below is regenerated from committed runs by
  `python scripts/score_runs.py --systems B1 B2 B4 S1 S2 full full_finetuned A1 A2 A3 A5 --paired …`,
  `python scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned` and `python scripts/eval_tagger.py …`
  ([reproduction.md](reproduction.md)).

## 1. Summary

We built a benchmark of 102 app/policy cases with scripted answer keys and a 140-case vagueness
ladder, ran two published checkers (PoliCheck, PoliGraph) and three single-prompt LLM baselines, and
built the evidence-gated DPDP-Audit pipeline. On the main benchmark, with the same 7B model as the
single-prompt baseline B2, DPDP-Audit **nearly doubles F1 (0.343 vs 0.181)** and **cuts the
false-alarm rate on compliant apps from 0.75 to 0.47**. It also beats both published tools on F1 and
false alarms. A much stronger model given B2's prompt (Gemini 3 Flash, B4) reaches F1 0.414 but
flags 97% of compliant apps. Our QLoRA-tuned 3B tagger reads policies far better than prompting
(category macro-F1 0.713 vs 0.311); in the pipeline it lowers the false-alarm rate further, to 0.33.
Three results go against our hypotheses: the verifier's model check costs far more recall than
planned (H3 fails), the fine-tuned tagger does not close half the gap to gold annotations (H6
fails), and purpose mismatches remain largely undetected.

## 2. Problem and benchmark

An app's privacy policy says what it collects, why and who receives it; its code and SDKs may do
otherwise. We measure how well systems find five kinds of **compliance gap** under India's DPDP Act
(undisclosed collection, undisclosed sharing, purpose mismatch, retention mismatch, children's data),
each with the policy's own words and the DPDP section ([getting-started.md](getting-started.md)).

| Benchmark | Cases | Answer source | Status |
|---|---|---|---|
| Main | 102 (34 compliant controls, 68 variants), 118 gold gaps, 433 flows | Fixed rules over expert OPP-115 annotations; no LLM | Done; 20-case spot-check sheet ready, checks pending (AC-01.10) |
| Vagueness ladder | 140 = 35 ladders × 4 rungs (clear, explicit, vague, deleted) | Templated sentence inserted into a base policy | Built and scored; two-person check pending (AC-06.6) |
| Dev split | 33 cases from 12 *training* policies | Same rules | Used only to develop the pipeline |

Cases come from the 35 held-out OPP-115 policies (80/35 split, seed 13); regeneration is
byte-identical. Ladder rungs differ from the deleted rung by exactly one sentence (tested). Details:
[benchmark.md](benchmark.md).

## 3. Systems

| ID | System | Model | Runs |
|---|---|---|---|
| S1 | PoliCheck (authors' code) | rule-based NLP | main, ladder |
| S2 | PoliGraph (authors' released NLP version) | rule-based NLP | main, ladder |
| B1 | One prompt, raw policy and app files | Qwen2.5-7B-Instruct-AWQ | main × 3 seeds |
| B2 | One prompt, parsed app facts + retrieved DPDP text (exactly the pipeline's inputs) | same | main × 3, ladder × 3 |
| B4 | B2's prompt to a stronger model | gemini-3-flash-preview | main seed 0 (seeds 1–2 running) |
| full | **DPDP-Audit**: tagger → tools → mismatch finder → 4 specialist reviewer agents → aggregator → evidence verifier | prompted Qwen2.5-3B tagger, Qwen2.5-7B reviewers | main × 3, ladder × 1 |
| full_finetuned | the same pipeline with our QLoRA-tuned tagger (only the tagger changes) | QLoRA Qwen2.5-3B tagger, Qwen2.5-7B reviewers | main × 3, ladder × 1 |
| A1–A5 | Ablations (verifier off; no retrieval; one generalist reviewer; oracle tagger) | same | main × 1 |

**How the pipeline decides.** The 3B tagger turns each policy paragraph into structured claims; the
deterministic finder proposes every flow the claims do not clearly cover; each reviewer agent copies
the policy sentences that disclose, deny or only generically cover its flows (with up to three tool
calls); a fixed rule derives the gap from the quotes that are verbatim in the policy; the verifier
drops findings with invalid quotes or sections and marks those an LLM check does not support as
*uncertain* (sent to human review, not reported). The design was developed on the dev split only
(four iterations, [pipeline.md](pipeline.md#implementation)) and frozen before any evaluation run.

## 4. Results on the main benchmark

Mean over seeds (B1, B2, full: 3; others: 1). *Common* = collection and sharing only (what the tools
model); *native* = the tools' reading, in which a vague disclosure is not a gap.

| System | F1 | F1 common | F1 common, native | Label macro-F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| S1 PoliCheck | 0.149 | 0.186 | 0.192 | 0.225 | 0.912 | (by construction) |
| S2 PoliGraph | 0.166 | 0.212 | 0.079 | 0.197 | 0.853 | (by construction) |
| B1 | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.325 |
| B2 | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |
| B4 Gemini 3 Flash | 0.414 | 0.295 | 0.150 | 0.276 | 0.971 | 1.000 |
| **full** (prompted tagger) | **0.343** | 0.337 | **0.281** | 0.353 | 0.471 | **1.000** |
| **full_finetuned** (QLoRA tagger) | 0.321 | **0.428** | 0.195 | **0.463** | **0.333** | **1.000** |

Seeds of `full`: F1 0.339 / 0.349 / 0.341; false-alarm rate 0.50 / 0.50 / 0.41.

**Paired differences, seed 0** (95% policy-level cluster bootstrap, 1,000 re-samples):

| Comparison | F1 (full view) | F1 (common) | False-alarm rate |
|---|---|---|---|
| full − B2 | **+0.151 [+0.045, +0.259]** | **+0.130 [+0.015, +0.242]** | −0.176 [−0.412, +0.059] |
| full − B1 | **+0.155 [+0.053, +0.259]** | **+0.135 [+0.024, +0.238]** | **−0.471 [−0.676, −0.265]** |
| full − S1 PoliCheck | **+0.190 [+0.078, +0.300]** | **+0.139 [+0.015, +0.255]** | **−0.412 [−0.588, −0.235]** |
| full − S2 PoliGraph | **+0.173 [+0.064, +0.284]** | +0.113 [−0.006, +0.230] | **−0.353 [−0.529, −0.176]** |
| full − B4 | −0.076 [−0.184, +0.032] | +0.030 [−0.089, +0.155] | **−0.471 [−0.676, −0.265]** |
| full_finetuned − full | −0.048 [−0.173, +0.074] | +0.092 [−0.046, +0.245] | **−0.265 [−0.471, −0.059]** |
| full_finetuned − B2 | **+0.103 [+0.023, +0.193]** | **+0.222 [+0.082, +0.353]** | **−0.441 [−0.676, −0.176]** |
| full_finetuned − S1 PoliCheck | **+0.142 [+0.046, +0.240]** | **+0.231 [+0.088, +0.363]** | **−0.676 [−0.824, −0.529]** |
| full_finetuned − S2 PoliGraph | **+0.125 [+0.025, +0.225]** | **+0.206 [+0.055, +0.348]** | **−0.618 [−0.765, −0.471]** |

Bold: the interval excludes 0.

Precision and recall (mean over seeds):

| System | Precision | Recall | Recall: explicit / vague / omission |
|---|---|---|---|
| B2 | 0.12 | 0.35 | 0.18 / 0.50 / 0.25 |
| B4 | 0.29 | 0.73 | 0.97 / 0.61 / 0.73 |
| full | 0.32 | 0.38 | 0.45 / 0.34 / 0.37 |
| full_finetuned | 0.35 | 0.30 | — |
| A1 (no verifier) | 0.34 | 0.72 | 0.93 / 0.70 / 0.58 |

### Ablations (seed 0)

| Config | Change | F1 | False-alarm rate | full − config, F1 |
|---|---|---|---|---|
| full | — | 0.339 | 0.500 | — |
| A1 | verifier off | 0.459 | 0.794 | **−0.121 [−0.202, −0.050]** |
| A2 | no DPDP retrieval | 0.308 | 0.471 | +0.030 [−0.076, +0.130] |
| A3 | one generalist reviewer, no aggregator | 0.282 | 0.412 | +0.056 [−0.064, +0.180] |
| A5 | oracle tagger (gold annotations) | 0.596 | 0.000 | A5 − full: **+0.258 [+0.108, +0.395]** |

A4 (prompted tagger) is the `full` configuration above; `full_finetuned` is the planned full system.
With the fine-tuned tagger, collection precision rises (0.09 → 0.15) and sharing precision
(0.78 → 0.89), but retention recall falls (0.39 → 0.13), which is why overall F1 does not move.

## 5. Vagueness ladder (RQ2, H4)

Accuracy of the target flow's disclosure label per rung (seed 0; all 140 rungs, since the
two-person check is pending):

| System | clear | explicit | vague | deleted | explicit − vague (McNemar p) |
|---|---|---|---|---|---|
| S1 PoliCheck | 0.20 | 0.77 | 0.40 | 0.74 | +0.37 (p = 0.015) |
| S2 PoliGraph | 0.40 | 0.00 | 0.03 | 0.97 | −0.03 (p = 1.00) |
| B2 (seeds 0–2 identical) | 0.00 | 0.00 | 1.00 | 0.00 | −1.00 |
| full | **1.00** | 0.60 | 0.80 | 0.14 | −0.20 (p = 0.14) |
| full_finetuned | **1.00** | 0.71 | 0.80 | 0.09 | −0.09 (p = 0.45) |

- PoliCheck is the only system for which H4 holds as stated (less accurate on vague than explicit).
- PoliGraph has no contradiction label and ignores the generic sentence, so it reads three rungs out
  of four as "omitted".
- B2 calls every flow "vague" on every rung of every ladder.
- `full` reads the clear rung perfectly and mostly reads the deleted rung as vague (22 of 35): the
  base policies still contain generic statements (flagged on 23 ladders), which is what the human
  check must settle.
- PoliCheck's low clear-rung score comes from the data-type mapping (exact only for Location) and
  from not resolving the Mixpanel domain to an entity.

## 6. Clause tagger (RQ4, SPEC-05)

Held-out OPP-115 paragraphs (1,140), category macro-F1:

| Tagger | Category macro-F1 | Tuple F1 (category, data type, does) | Tuple F1 (…, third party) |
|---|---|---|---|
| S3 PrivBERT (fine-tuned) | 0.779 | — (category classifier) | — |
| B3 prompted Qwen2.5-3B, categories only | 0.388 | — | — |
| Prompted Qwen2.5-3B, claims (pipeline tagger) | 0.311 | 0.179 | 0.053 |
| **QLoRA Qwen2.5-3B (ours)** | **0.713** | **0.479** | **0.288** |

QLoRA: 4-bit Qwen2.5-3B-Instruct, rank 16, 2 epochs fixed in advance, effective batch 16, on 2,426
segments of 72 training policies (8 more report a dev loss: 0.083 → 0.078); 2.8 h on one T4. The
prompt is the prompted tagger's own, so only the weights differ.

**H6** (beats B3; within 5 points of PrivBERT; closes half the A4–A5 gap):
- beats B3: yes (0.713 vs 0.388);
- within 5 points of PrivBERT: no, 6.6 points behind (0.713 vs 0.779);
- closes half the A4–A5 gap: no. On collection/sharing F1 it closes 36% of the gap (0.337 → 0.428,
  oracle 0.588); on the false-alarm rate 29% (0.471 → 0.333, oracle 0.000); on overall F1 none
  (0.343 → 0.321, oracle 0.596).

## 7. Findings so far

1. **Structure beats a single prompt with the same model.** Same inputs, same 7B model: the pipeline
   gains 0.15 F1 (interval excludes 0) and lowers false alarms; against B1 and both published tools
   the false-alarm reduction is also significant.
2. **Evidence-first reviewing was the decisive design step.** On the dev split, asking the 7B model
   "is this a gap?" confirmed almost every candidate (false-alarm rate 0.64–0.91); asking it to copy
   the disclosing sentence and deciding by rule lowered it to 0.36 (pipeline.md, dev iterations).
3. **A stronger model is not safer.** Gemini 3 Flash with B2's prompt finds far more gaps (recall
   0.73) but raises an alarm on 33 of 34 compliant apps.
4. **The verifier is too strict (H3 fails).** Its LLM check marks 115–121 findings per seed (over 102
   cases) uncertain;
   turning it off (A1) raises recall from 0.38 to 0.72 and F1 to 0.46, but the false-alarm rate rises
   from 0.50 to 0.79. H3 allowed at most 5 points of recall loss; the loss is 34 points.
5. **Reading is the main remaining error, and fine-tuning helps only part of the way.** The oracle
   tagger lifts F1 by 0.26. Fine-tuning more than doubles the tagger's macro-F1 and tuple F1, and
   in the pipeline it cuts false alarms significantly (0.47 → 0.33), but most of the gap to gold
   annotations remains.
6. **Agents did not use their tools.** Reviewers may call `search_policy`, `retrieve_dpdp` and
   `lookup_sdk` (tested), but in all 986 pipeline runs (dev, main, ladder) they answered directly from
   the linked paragraphs, with zero tool calls.
   Specialist reviewers (vs A3) and retrieval (vs A2) show no significant effect at this sample size.
7. **Purpose mismatches are hard for every system** (recall 0.00–0.19 except the oracle, 0.57).

## 8. Status against the plan

| Item (plan §7) | Priority | Status |
|---|---|---|
| Benchmark and B1/B2 | Must | Done |
| Vagueness ladder built and checked | Must | Built and scored; **two-person check pending** |
| PoliCheck on main | Must | Done |
| Pipeline v1 with a seed-0 run on main | Must | Done (3 seeds) |
| Comparison table with intervals | Must | Done (§4) |
| Architecture, plan, specifications | Must | Done, updated |
| PoliGraph on main | Should | Done (31/34 policies parsed) |
| Tagger results: B3, QLoRA, PrivBERT | Should | Done; QLoRA also run in the pipeline (`full_finetuned`, WP-3.1 early) |
| B4 seed 0; PoliCheck on ladder | Should | Both done |
| Full system on the ladder | Could | Done (seed 0) |
| Ablations | Won't by 30 Oct | A1, A2, A3, A5 done early; A4 waits for the fine-tuned tagger |

**Deviations.**
- AC-03.4: the PoliCheck authors ship flows but neither policies nor labels, so their result cannot
  be reproduced; a six-policy known-answer check replaces it (running).
- B4 needs 102 requests per seed and the free tier allows 20 per key per day; seeds 1–2 run on
  several team keys over the next days.
- PoliGraph ran on Kaggle instead of the workstation.

## 9. Remaining plan (to 15 Nov)

| Work | When |
|---|---|
| Statement-extraction comparison S4 (PolicyLint, PoliGraph) on tuple F1 | 31 Oct–3 Nov |
| Ladder two-person check, answer-key spot-check; re-score on accepted rungs | 27–29 Oct |
| B4 seeds 1–2 | 27–29 Oct |
| Full system on the ladder, seeds 1–2; PoliCheck/PolicyLint extraction comparison (S4) | 31 Oct–3 Nov |
| Selective accuracy (SPEC-07) from the three seeds | 6–9 Nov |
| Real-flow sample and case study (SPEC-08) | 4–10 Nov |
| Failure analysis, hypothesis verdicts, final report | 11–15 Nov |

Any change to the verifier found necessary by the failure analysis will be developed on the dev split
and reported as a new configuration, not by changing the frozen `full` runs.
