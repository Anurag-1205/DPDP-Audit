# DPDP-Audit — Mid-submission report (Stage 2)

- **Date:** 27 October 2026 (submission due 30 October)
- **Team:** Anurag Kaushal · Ishaan Giri · Naveen Mishra · Nikhil Patidar
- **Covers:** MS-0 to MS-2 · SPEC-01 to SPEC-06 · plan §7 (must-have package)
- **Reproduce:** every number below is regenerated from committed runs by
  `python scripts/score_runs.py --systems B1 B2 B4 S1 S2 full full_finetuned A1 A2 A3 A5 full_v2 full_v2_finetuned --paired …`,
  `python scripts/score_ladder.py --systems S1 S2 B2 full full_finetuned full_v2 full_v2_finetuned` and
  `python scripts/eval_tagger.py …`
  ([reproduction.md](reproduction.md)).

## 1. Summary

We built a benchmark of 102 app/policy cases with scripted answer keys and a 140-case vagueness
ladder, ran two published checkers (PoliCheck, PoliGraph) and three single-prompt LLM baselines, and
built the evidence-gated DPDP-Audit pipeline. On the main benchmark, with the same 7B model as the
single-prompt baseline B2, the pipeline as frozen before evaluation (`full`) **nearly doubles F1
(0.343 vs 0.181)** and **cuts the false-alarm rate on compliant apps from 0.75 to 0.47**. It also
beats both published tools on F1 and false alarms. A much stronger model given B2's prompt (Gemini 3
Flash, B4) reaches F1 0.421 but flags 97% of compliant apps. Our QLoRA-tuned 3B tagger reads policies
far better than prompting (category macro-F1 0.713 vs 0.311); in the pipeline it lowers the
false-alarm rate further, to 0.33.

The first runs showed where the pipeline loses findings. We fixed it **on development splits of
training policies only** and froze the result as **v2** before running it once on the evaluation
splits (§4.1). With the fine-tuned tagger, v2 reaches **F1 0.655** (frozen: 0.321) at a false-alarm
rate of 0.34, ahead of B4 by +0.25 F1 with 0.68 fewer false alarms. Its gain over every baseline is
significant in all three views, including the tools' own reading of vague disclosure.

Results that go against our hypotheses (frozen pipeline): the gain over B1 and B2 is largest on explicit gaps, not on
vague and omission gaps (second half of H2 fails), the verifier's model check costs far more recall
than planned (H3 fails), the fine-tuned tagger does not close half the gap to gold annotations (H6
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
| Dev splits | `dev` 33 cases + `dev2` 69 cases, from 34 *training* policies | Same rules | Used only to develop the pipeline |

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
| B4 | B2's prompt to a stronger model | gemini-3-flash-preview | main × 3 |
| full | **DPDP-Audit**: tagger → tools → mismatch finder → 4 specialist reviewer agents → aggregator → evidence verifier | prompted Qwen2.5-3B tagger, Qwen2.5-7B reviewers | main × 3, ladder × 1 |
| full_finetuned | the same pipeline with our QLoRA-tuned tagger (only the tagger changes) | QLoRA Qwen2.5-3B tagger, Qwen2.5-7B reviewers | main × 3, ladder × 1 |
| A1–A5 | Ablations (verifier off; no retrieval; one generalist reviewer; oracle tagger) | same | main × 1 |
| full_v2, full_v2_finetuned | v2 of the pipeline, chosen on the dev splits (§4.1), with the prompted / QLoRA tagger | same | main × 3, ladder × 1 |

**How the pipeline decides.** The 3B tagger turns each policy paragraph into structured claims; the
deterministic finder proposes every flow the claims do not clearly cover; each reviewer agent copies
the policy sentences that disclose, deny or only generically cover its flows (with up to three tool
calls); a fixed rule derives the gap from the quotes that are verbatim in the policy; the verifier
drops findings with invalid quotes or sections and marks those an LLM check does not support as
*uncertain* (sent to human review, not reported). The design was developed on the dev split only
(four iterations, [pipeline.md](pipeline.md#implementation)) and frozen before any evaluation run.

## 4. Results on the main benchmark

Mean over seeds (B1, B2, B4, full, full_finetuned and v2: 3; others: 1). *Common* = collection and sharing only (what the tools
model); *native* = the tools' reading, in which a vague disclosure is not a gap.

| System | F1 | F1 common | F1 common, native | Label macro-F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| S1 PoliCheck | 0.149 | 0.186 | 0.192 | 0.225 | 0.912 | (by construction) |
| S2 PoliGraph | 0.166 | 0.212 | 0.079 | 0.197 | 0.853 | (by construction) |
| B1 | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.325 |
| B2 | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |
| B4 Gemini 3 Flash | 0.421 | 0.303 | 0.156 | 0.279 | 0.971 | 0.996 |
| full (prompted tagger, frozen) | 0.343 | 0.337 | 0.281 | 0.353 | 0.471 | 1.000 |
| full_finetuned (QLoRA tagger, frozen) | 0.321 | 0.428 | 0.195 | 0.463 | 0.333 | 1.000 |
| **full_v2** (prompted tagger) | 0.637 | 0.581 | 0.304 | 0.407 | 0.353 | 1.000 |
| **full_v2_finetuned** (QLoRA tagger) | **0.655** | **0.626** | **0.335** | **0.495** | 0.343 | **1.000** |

Seeds of `full`: F1 0.339 / 0.349 / 0.341; false-alarm rate 0.50 / 0.50 / 0.41. Seeds of
`full_v2_finetuned`: F1 0.661 / 0.656 / 0.649; false-alarm rate 0.29 / 0.35 / 0.38.

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
| full_v2 − full | **+0.287 [+0.182, +0.394]** | **+0.226 [+0.098, +0.362]** | −0.118 [−0.324, +0.118] |
| full_v2_finetuned − full_finetuned | **+0.370 [+0.258, +0.479]** | **+0.249 [+0.086, +0.415]** | +0.059 [−0.118, +0.235] |
| full_v2_finetuned − full_v2 | +0.036 [−0.045, +0.110] | +0.115 [−0.015, +0.234] | −0.088 [−0.265, +0.089] |
| full_v2_finetuned − B2 | **+0.473 [+0.382, +0.556]** | **+0.472 [+0.327, +0.609]** | **−0.382 [−0.618, −0.147]** |
| full_v2_finetuned − B1 | **+0.477 [+0.388, +0.564]** | **+0.477 [+0.338, +0.609]** | **−0.676 [−0.824, −0.500]** |
| full_v2_finetuned − S1 PoliCheck | **+0.512 [+0.423, +0.595]** | **+0.480 [+0.345, +0.609]** | **−0.618 [−0.794, −0.441]** |
| full_v2_finetuned − S2 PoliGraph | **+0.495 [+0.403, +0.583]** | **+0.455 [+0.315, +0.589]** | **−0.559 [−0.735, −0.382]** |
| full_v2_finetuned − B4 | **+0.247 [+0.167, +0.333]** | **+0.372 [+0.213, +0.524]** | **−0.676 [−0.824, −0.500]** |

Bold: the interval excludes 0. On the tools' native reading (vague disclosure is not a gap),
`full_v2_finetuned` is also significantly ahead of every baseline (vs PoliCheck +0.208
[+0.004, +0.356], vs PoliGraph +0.321 [+0.081, +0.500], vs B2 +0.154 [+0.026, +0.298]); the frozen
pipeline was not.

**H2** (the full system beats B1 and B2 on F1, most on vague and omission gaps): the first half holds,
since both F1 intervals exclude 0. The second half fails. F1 per gap level (mean over seeds):

| System | explicit | vague | omission |
|---|---|---|---|
| B1 | 0.445 | 0.156 | 0.267 |
| B2 | 0.310 | 0.152 | 0.324 |
| full | 0.565 | 0.282 | 0.316 |
| full_finetuned | 0.416 | 0.319 | 0.261 |
| full_v2 | 0.868 | 0.533 | 0.649 |
| full_v2_finetuned | 0.843 | 0.556 | 0.670 |

Against B2, `full` gains +0.26 on explicit, +0.13 on vague and nothing on omission (−0.01);
`full_finetuned` is below B2 on omission (0.26 vs 0.32). v2 gains on every level (`full_v2` vs B2:
+0.56, +0.38, +0.33), but still most on explicit gaps, so the second half of H2 fails for v2 too.

Precision and recall (mean over seeds):

| System | Precision | Recall | Recall: explicit / vague / omission |
|---|---|---|---|
| B2 | 0.12 | 0.35 | 0.18 / 0.50 / 0.25 |
| B4 | 0.30 | 0.72 | 0.99 / 0.61 / 0.66 |
| full | 0.32 | 0.38 | 0.45 / 0.34 / 0.37 |
| full_finetuned | 0.35 | 0.30 | — |
| A1 (no verifier) | 0.34 | 0.72 | 0.93 / 0.70 / 0.58 |
| full_v2 | 0.56 | 0.75 | 0.91 / 0.68 / 0.73 |
| full_v2_finetuned | 0.60 | 0.72 | 0.90 / 0.63 / 0.71 |

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

### 4.1 v2: changes chosen on the dev splits

Rule: no tuning on evaluation cases. Every v2 change was found and chosen on the dev splits (102 cases
from 34 *training* policies; a second dev split, `dev2`, was added so that the choice does not rest on
33 cases), with the prompted tagger, and frozen before the single v2 run on main and the ladder. The
frozen `full` runs are kept unchanged above. Details and all dev numbers: [pipeline.md](pipeline.md#v2).

| Problem found on dev | Change in v2 |
|---|---|
| The verifier's LLM check rejected every correct children's-data and retention finding | The check is applied only to collection and purpose findings; the others keep the deterministic checks (verbatim quote, valid section) |
| A purpose quote like "this information is used to ..." was rejected because the sentence does not name the data | It counts when its paragraph names the data type |
| 17 of 47 false collection findings: the disclosing paragraph was cut by an 8-paragraph limit | Up to 16 paragraphs per reviewer (within the same prompt budget); purpose searches use the purpose's everyday words |
| A reviewer answering several candidates at once often quoted nothing | One candidate per reviewer call |
| The retention reviewer echoes the app's "Indefinitely" and quotes an unrelated sentence, which cleared real gaps | A retention quote must be about keeping data, and "indefinitely" must be in it |

One more change was tried and rejected on dev: checking the purpose of every flow whose notice is in
doubt raised the false-alarm rate (+0.24, significant). On the pooled dev splits the chosen v2 gained
+0.30 F1 [+0.23, +0.39] over `full`; on main it gains +0.29 [+0.18, +0.39] (prompted tagger) and +0.37
[+0.26, +0.48] (fine-tuned tagger), so the dev result carried over.

Per gap type on main (`full_v2_finetuned`, mean of 3 seeds): children's data and retention are now
found without error (precision and recall 1.00; frozen: recall 0.31 and 0.13), sharing reaches recall
0.97 at precision 0.86. Collection (precision 0.11) and purpose (precision 0.07, recall 0.11) remain
the weak points: over 3 seeds, 91 of the 167 false findings are purpose gaps and 60 collection gaps,
and purpose gaps alarm the most compliant apps (21 control runs, against 14 for collection).
**Ablations of v2** (seed 0, each against `full_v2_finetuned`; A4 on v2 is `full_v2`):

| Config | Change | F1 | Recall | False-alarm rate | Citation correct | full_v2_finetuned − config, F1 |
|---|---|---|---|---|---|---|
| full_v2_finetuned | — | 0.661 | 0.720 | 0.294 | 1.000 | — |
| A1_v2 | verifier off | 0.612 | 0.797 | 0.618 | 1.000 | +0.049 [+0.000, +0.098] |
| A2_v2 | no DPDP retrieval | 0.654 | 0.754 | 0.294 | 0.989 | +0.007 [−0.048, +0.067] |
| A3_v2 | one generalist reviewer, no aggregator | 0.687 | 0.678 | 0.176 | 0.925 | −0.025 [−0.097, +0.055] |
| A5_v2 | oracle tagger | 0.853 | 0.763 | 0.029 | 1.000 | A5_v2 − full: **+0.192 [+0.122, +0.264]** |

- **H3 on v2 still fails, narrowly.** The verifier halves the false-alarm rate (−0.324
  [−0.471, −0.176]) but costs 7.7 points of recall; H3 allowed 5 (v1: 34 points).
- **Retrieval and specialist reviewers show no gain** on v2 either. The generalist (A3_v2) is even
  slightly ahead on F1 and false alarms (not significant), but cites a wrong section more often (0.925).
- **Reading is still the limit:** with gold annotations (A5_v2) F1 reaches 0.853 and false alarms 0.03.

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
| full_v2 | **1.00** | 0.69 | 0.80 | 0.11 | −0.11 (p = 0.42) |
| full_v2_finetuned | **1.00** | 0.71 | 0.80 | 0.09 | −0.09 (p = 0.45) |

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
   from 0.50 to 0.79. H3 allowed at most 5 points of recall loss; the loss is 34 points. In v2 the
   check sees only collection and purpose findings (§4.1): the recall cost falls to 7.7 points, still
   above the 5 allowed, while false alarms halve (0.62 → 0.29).
5. **Reading is the main remaining error, and fine-tuning helps only part of the way.** The oracle
   tagger lifts F1 by 0.26. Fine-tuning more than doubles the tagger's macro-F1 and tuple F1, and
   in the pipeline it cuts false alarms significantly (0.47 → 0.33), but most of the gap to gold
   annotations remains.
6. **Agents did not use their tools.** Reviewers may call `search_policy`, `retrieve_dpdp` and
   `lookup_sdk` (tested), but in all 1,432 pipeline runs (dev, main, ladder) they answered directly from
   the linked paragraphs, with zero tool calls.
   Specialist reviewers (vs A3) and retrieval (vs A2) show no significant effect at this sample size,
   on v1 or v2.
7. **Purpose mismatches are hard for every system** (recall 0.00–0.25, v2 included; only the oracle
   tagger reaches 0.57).
8. **The gain from v1 to v2 comes from how the pipeline is wired, not from the model.** v2 changes no
   model and none of the instructions: it removes a model check where rules already decide, shows the
   reviewer more of the policy, asks one question per call and fixes two decision rules. With the same
   7B model this nearly doubles F1.

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
| B4 seed 0; PoliCheck on ladder | Should | Both done (B4 also seeds 1–2) |
| Full system on the ladder | Could | Done (seed 0) |
| Ablations | Won't by 30 Oct | A1, A2, A3, A5 done early on v1, and repeated on v2 (A4 = the prompted-tagger run of each version) |

**Deviations.**
- AC-03.4: the PoliCheck authors ship flows but neither policies nor labels, so their result cannot
  be reproduced; a six-policy known-answer check replaces it. PoliCheck gives the expected label on
  5 of 6. It reads "We share your location with Google" as *vague* for a flow to Google Ads, because
  its entity ontology puts "google ads" under "Google"; the same rule lowers its clear-rung score on
  the ladder (§5).
- B4 needs 102 requests per seed and the free tier allows 20 per key per day; seeds 1–2 ran on
  several team keys (27 Oct), all 306 runs without a failed call.
- v2 of the pipeline (§4.1) was added after the first evaluation runs. It was developed on the dev
  splits only and is reported next to the frozen pipeline, not in place of it.
- PoliGraph ran on Kaggle instead of the workstation.

## 9. Remaining plan (to 15 Nov)

| Work | When |
|---|---|
| Statement-extraction comparison S4 (PolicyLint, PoliGraph) on tuple F1 | 31 Oct–3 Nov |
| Ladder two-person check, answer-key spot-check; re-score on accepted rungs | 27–29 Oct |
| Full system on the ladder, seeds 1–2; PoliCheck/PolicyLint extraction comparison (S4) | 31 Oct–3 Nov |
| Selective accuracy (SPEC-07) from the three seeds | 6–9 Nov |
| Real-flow sample and case study (SPEC-08) | 4–10 Nov |
| Failure analysis, hypothesis verdicts, final report | 11–15 Nov |

Any further change will follow the v2 rule: developed on the dev splits and reported as a new
configuration, never by changing the frozen runs.
