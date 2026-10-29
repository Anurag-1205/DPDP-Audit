# DPDP-Audit — Mid-submission report (Stage 2)

- **Date:** 29 October 2026 (submission due 30 October)
- **Team:** Anurag Kaushal · Ishaan Giri · Naveen Mishra · Nikhil Patidar
- **Covers:** MS-0 to MS-2 · SPEC-01 to SPEC-06 · plan §7 (must-have package)
- **Reproduce:** every number below is regenerated from the committed runs, without a GPU, by
  `bash scripts/score_all.sh` (about 2 minutes; it rewrites `results/scores/` identically)
  ([reproduction.md](reproduction.md)).

## 1. Summary

We built a benchmark of 102 app/policy cases with scripted answer keys and a 140-case vagueness
ladder, ran two published checkers (PoliCheck, PoliGraph) and three single-prompt LLM baselines, and
built the evidence-gated DPDP-Audit pipeline.

**A correction first.** A review of the runs found that the verifier's reply could not be read in
15–40% of pipeline runs (the 7B model writes one JSON object per finding), and the code then kept every
finding unchecked. We fixed the reader and re-ran only the verifier on the saved runs (§4.2); every
reply is now read. **All pipeline numbers below are with the fixed verifier** (`*_rv`) unless marked
"as run"; the as-run numbers are kept for the record.

With the verifier working, the pipeline as frozen before evaluation (**v1**) does **not** beat the
single-prompt baseline B2 on F1 (0.186 vs 0.181, same 7B model and inputs), although it raises far fewer
false alarms on compliant apps (0.24 vs 0.75, significant): its verifier rejects most correct findings.
**v2**, whose changes were found and chosen on development splits of training policies only (§4.1),
reaches **F1 0.705** with our QLoRA-tuned tagger at a false-alarm rate of **0.27**. It is significantly
ahead of every baseline in every view and on every seed (paired differences, seed 0): +0.54 F1 over
B2, +0.31 over a much stronger model given B2's prompt (Gemini 3 Flash, B4: F1 0.421, alarms on 97% of
compliant apps), and +0.57 / +0.56 over PoliCheck / PoliGraph. Our QLoRA tagger reads policies far better than prompting (category macro-F1 0.713 vs
0.311).

Against our hypotheses: the falsifiable claim fails for v1 and holds for v2; the verifier costs more
recall than the 5 points allowed (H3 fails: 61 points in v1, 11 in v2); the gain over B1/B2 is largest
on explicit gaps (second half of H2 fails); the fine-tuned tagger does not close half the gap to gold
annotations (H6 fails); no system is significantly less accurate on vague ladder rungs than on
explicit ones (H4 fails); and v2 reports almost no collection or purpose gaps by itself; its verifier
sends nearly all of them to human review. Two members checked the ladder and 20 answer keys
independently (agreement κ = 0.19 and 0.04), then settled every disagreement together: 110 of 140 rungs
are accepted, and the scripted answer key is wrong on 9 of 87 checked flows (10.3%).

## 2. Problem and benchmark

An app's privacy policy says what it collects, why and who receives it; its code and SDKs may do
otherwise. We measure how well systems find five kinds of **compliance gap** under India's DPDP Act
(undisclosed collection, undisclosed sharing, purpose mismatch, retention mismatch, children's data),
each with the policy's own words and the DPDP section ([getting-started.md](getting-started.md)).

| Benchmark | Cases | Answer source | Status |
|---|---|---|---|
| Main | 102 (34 compliant controls, 68 variants), 118 gold gaps, 433 flows | Fixed rules over expert OPP-115 annotations; no LLM | Done; 20-case spot-check by two members: key wrong on 9 of 87 flows, 10.3% (§5) (AC-01.10) |
| Vagueness ladder | 140 = 35 ladders × 4 rungs (clear, explicit, vague, deleted) | Templated sentence inserted into a base policy | Built, checked by two members (110 of 140 rungs accepted) and scored (AC-06.6) |
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
| `*_rv` | the same runs with only the verifier re-run, using the fixed reply reader (§4.2) | same | as the system it re-checks |

**How the pipeline decides.** The 3B tagger turns each policy paragraph into structured claims; the
deterministic finder proposes every flow the claims do not clearly cover; each reviewer agent copies
the policy sentences that disclose, deny or only generically cover its flows (with up to three tool
calls); a fixed rule derives the gap from the quotes that are verbatim in the policy; the verifier
drops findings with invalid quotes or sections and marks those an LLM check does not support as
*uncertain* (sent to human review, not reported). The design was developed on the dev split only
(four iterations, [pipeline.md](pipeline.md#implementation)) and frozen before any evaluation run.

## 4. Results on the main benchmark

Mean over seeds (B1, B2, B4 and the pipelines: 3; tools: 1). *Common* = collection and sharing only
(what the tools model); *native* = the tools' reading, in which a vague disclosure is not a gap. The
pipeline rows use the fixed verifier (§4.2).

| System | F1 | F1 common | F1 common, native | Label macro-F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| S1 PoliCheck | 0.149 | 0.186 | 0.192 | 0.225 | 0.912 | (by construction) |
| S2 PoliGraph | 0.166 | 0.212 | 0.079 | 0.197 | 0.853 | (by construction) |
| B1 | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.325 |
| B2 | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |
| B4 Gemini 3 Flash | 0.421 | 0.303 | 0.156 | 0.279 | 0.971 | 0.996 |
| v1 `full_rv` (prompted tagger) | 0.186 | 0.156 | 0.114 | 0.353 | **0.235** | 1.000 |
| v1 `full_finetuned_rv` (QLoRA tagger) | 0.168 | 0.219 | 0.042 | 0.463 | 0.275 | 1.000 |
| **v2 `full_v2_rv`** (prompted tagger) | 0.692 | 0.673 | **0.370** | 0.407 | 0.294 | 1.000 |
| **v2 `full_v2_finetuned_rv`** (QLoRA tagger) | **0.705** | **0.686** | 0.364 | **0.495** | 0.265 | 1.000 |

As run (verifier reply unreadable in 15–40% of runs, §4.2), for the record:

| System | F1 | F1 common | F1 common, native | Label macro-F1 | False-alarm rate |
|---|---|---|---|---|---|
| v1 `full` | 0.343 | 0.337 | 0.281 | 0.353 | 0.471 |
| v1 `full_finetuned` | 0.321 | 0.428 | 0.195 | 0.463 | 0.333 |
| v2 `full_v2` | 0.637 | 0.581 | 0.304 | 0.407 | 0.353 |
| v2 `full_v2_finetuned` | 0.655 | 0.626 | 0.335 | 0.495 | 0.343 |

Seeds of `full_v2_finetuned_rv`: F1 0.723 / 0.708 / 0.684; false-alarm rate 0.21 / 0.26 / 0.32.
Label macro-F1 does not depend on the verifier (labels come from the reviewers), so it is the same as
run.

**Paired differences, seed 0** (95% policy-level cluster bootstrap, 1,000 re-samples):

| Comparison | F1 (full view) | F1 (common) | F1 (common, native) | False-alarm rate |
|---|---|---|---|---|
| v2 `full_v2_finetuned_rv` − B2 | **+0.535 [+0.451, +0.607]** | **+0.552 [+0.411, +0.670]** | **+0.168 [+0.039, +0.305]** | **−0.471 [−0.706, −0.235]** |
| v2 `full_v2_finetuned_rv` − B1 | **+0.539 [+0.456, +0.618]** | **+0.557 [+0.412, +0.673]** | **+0.196 [+0.038, +0.400]** | **−0.765 [−0.912, −0.618]** |
| v2 `full_v2_finetuned_rv` − S1 PoliCheck | **+0.574 [+0.498, +0.642]** | **+0.561 [+0.433, +0.666]** | **+0.222 [+0.012, +0.366]** | **−0.706 [−0.853, −0.558]** |
| v2 `full_v2_finetuned_rv` − S2 PoliGraph | **+0.557 [+0.474, +0.629]** | **+0.535 [+0.398, +0.648]** | **+0.334 [+0.088, +0.513]** | **−0.647 [−0.794, −0.499]** |
| v2 `full_v2_finetuned_rv` − B4 | **+0.309 [+0.235, +0.380]** | **+0.452 [+0.285, +0.583]** | **+0.264 [+0.017, +0.449]** | **−0.765 [−0.912, −0.618]** |
| v2 `full_v2_finetuned_rv` − `full_v2_rv` (tagger) | +0.043 [−0.019, +0.100] | **+0.100 [+0.021, +0.184]** | +0.106 [−0.104, +0.353] | −0.118 [−0.294, +0.059] |
| v2 − v1, prompted tagger | **+0.516 [+0.406, +0.617]** | **+0.558 [+0.398, +0.705]** | +0.308 [+0.000, +0.583] | +0.118 [−0.088, +0.324] |
| v2 − v1, QLoRA tagger | **+0.574 [+0.467, +0.667]** | **+0.547 [+0.365, +0.704]** | **+0.414 [+0.105, +0.636]** | −0.029 [−0.176, +0.118] |
| v1 `full_rv` − B2 | −0.024 [−0.136, +0.105] | −0.106 [−0.208, +0.020] | **−0.246 [−0.462, −0.044]** | **−0.471 [−0.676, −0.265]** |
| v1 `full_rv` − B1 | −0.020 [−0.127, +0.103] | −0.100 [−0.192, +0.016] | −0.217 [−0.429, +0.000] | **−0.765 [−0.912, −0.588]** |
| v1 `full_rv` − S1 PoliCheck | +0.016 [−0.101, +0.142] | −0.097 [−0.202, +0.029] | **−0.192 [−0.377, −0.039]** | **−0.706 [−0.853, −0.529]** |
| v1 `full_rv` − S2 PoliGraph | −0.002 [−0.116, +0.127] | −0.122 [−0.230, +0.007] | −0.079 [−0.170, +0.000] | **−0.647 [−0.824, −0.471]** |
| v1 `full_finetuned_rv` − B2 | −0.039 [−0.124, +0.048] | +0.005 [−0.153, +0.170] | **−0.246 [−0.462, −0.044]** | **−0.441 [−0.676, −0.176]** |

Bold: the interval excludes 0. The intervals are not corrected for the number of comparisons; the
headline ones lie far from 0. The v2 comparisons with B2, B4 and both tools are also significant on
seeds 1 and 2 (F1 gain over B2 +0.51 / +0.52, over B4 +0.28 / +0.26, over PoliCheck +0.56 / +0.53),
so they do not depend on seed 0, v2's best seed. As run, v1 `full` − B2 was +0.151 [+0.045, +0.259] on F1 and
−0.176 [−0.412, +0.059] on the false-alarm rate (not significant); that F1 gain came from findings the
broken verifier never checked.

**Falsifiable claim** (beats PoliCheck and PoliGraph on their gap types and B2 on the full benchmark,
in F1 and false-alarm rate): **fails for v1**, whose F1 gain over B2 and the tools is below 5 points
and whose intervals include 0; **holds for v2** in every view, with significantly fewer false alarms.

**H2** (the full system beats B1 and B2 on F1, most on vague and omission gaps). F1 per gap level
(mean over seeds):

| System | explicit | vague | omission |
|---|---|---|---|
| B1 | 0.445 | 0.156 | 0.267 |
| B2 | 0.310 | 0.152 | 0.324 |
| v1 `full_rv` | 0.265 | 0.124 | 0.262 |
| v1 `full_finetuned_rv` | 0.103 | 0.211 | 0.108 |
| v2 `full_v2_rv` | 0.875 | 0.584 | 0.732 |
| v2 `full_v2_finetuned_rv` | 0.845 | 0.597 | 0.772 |

For v1 the first half fails (no F1 gain). For v2 the first half holds; the second half fails, narrowly:
against B2, `full_v2_finetuned_rv` gains +0.54 on explicit, +0.45 on vague and +0.45 on omission.

Precision and recall (mean over seeds):

| System | Precision | Recall | Recall: explicit / vague / omission |
|---|---|---|---|
| B2 | 0.12 | 0.35 | 0.18 / 0.50 / 0.25 |
| B4 | 0.30 | 0.72 | 0.99 / 0.61 / 0.66 |
| v1 `full_rv` | 0.30 | 0.14 | 0.16 / 0.11 / 0.16 |
| A1 (v1, verifier off) | 0.34 | 0.72 | 0.93 / 0.70 / 0.58 |
| v2 `full_v2_rv` | 0.68 | 0.71 | 0.87 / 0.63 / 0.69 |
| v2 `full_v2_finetuned_rv` | 0.73 | 0.68 | 0.87 / 0.60 / 0.67 |
| A1_v2 (v2, verifier off) | 0.50 | 0.80 | 0.93 / 0.79 / 0.70 |

### Ablations of v1 (seed 0, fixed verifier)

| Config | Change | F1 | False-alarm rate | full_rv − config, F1 |
|---|---|---|---|---|
| `full_rv` | — | 0.165 | 0.206 | — |
| A1 | verifier off (unaffected by the fix) | 0.459 | 0.794 | **−0.295 [−0.383, −0.192]** |
| A2_rv | no DPDP retrieval | 0.268 | 0.294 | −0.103 [−0.208, +0.015] |
| A3_rv | one generalist reviewer, no aggregator | 0.186 | 0.176 | −0.021 [−0.180, +0.145] |
| A5_rv | oracle tagger (gold annotations) | 0.273 | 0.000 | A5_rv − full_rv: +0.109 [−0.050, +0.279] |

In v1, turning the verifier off is far better on F1 (but alarms on 79% of compliant apps), and no other
component shows a significant effect.

A4 (prompted tagger) is the prompted-tagger run of each version (`full_rv`, `full_v2_rv`);
`full_v2_finetuned_rv` is the headline system. **A5 is partly circular:** the
answer keys are computed from the same OPP-115 annotations the oracle tagger reads, and the finder
applies the same notion of coverage, so A5 is an upper bound on what the reviewers keep rather than an
independent measurement ([pipeline.md](pipeline.md#implementation)); the A4–A5 gap is the cost of
reading errors.

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
doubt lowered F1 (−0.066 [−0.111, −0.022]) and raised the false-alarm rate (+0.24, borderline). As
run, the chosen v2 gained +0.30 F1 [+0.23, +0.39] over `full` on the pooled dev splits and +0.29 / +0.37 on main (prompted / fine-tuned
tagger), so the dev result carried over; with the fixed verifier the gain on main is +0.52 / +0.57.

The v2 choice does not depend on the verifier bug: re-verified with the fixed reader, the dev ranking
is unchanged (pooled dev F1: `full` 0.19 < `v2_purpose` 0.53 < `v2_read` 0.58 < `v2_gate` 0.59 <
`v2_batch` 0.60 < `full_v2` 0.68).

Per gap type on main (`full_v2_finetuned_rv`, mean of 3 seeds): children's data and retention are found
without error (precision and recall 1.00) and sharing reaches recall 0.97 at precision 0.86. Collection
and purpose findings are almost all sent to human review by the verifier: what is still reported has
precision 0.02 and recall 0.02 for each. Over 3 seeds, 54 of the 91 false findings are purpose gaps and
21 collection gaps; purpose gaps alarm the most compliant apps (15 control runs, 7 for collection).
About 84 findings per seed go to human review.

**Ablations of v2** (seed 0, fixed verifier, each against `full_v2_finetuned_rv`):

| Config | Change | F1 | Recall | False-alarm rate | Citation correct | full_v2_finetuned_rv − config, F1 |
|---|---|---|---|---|---|---|
| `full_v2_finetuned_rv` | — | 0.723 | 0.686 | 0.206 | 1.000 | — |
| A1_v2 | verifier off | 0.612 | 0.797 | 0.618 | 1.000 | **+0.111 [+0.046, +0.170]** |
| A2_v2_rv | no DPDP retrieval | 0.735 | 0.69 | 0.176 | 0.988 | −0.012 [−0.070, +0.047] |
| A3_v2_rv | one generalist reviewer, no aggregator | 0.736 | 0.66 | 0.118 | 0.936 | −0.013 [−0.069, +0.048] |
| A5_v2_rv | oracle tagger | 0.837 | 0.74 | 0.029 | 1.000 | A5_v2_rv − full: **+0.113 [+0.056, +0.172]** |

- **H3 fails for both versions.** In v2 the verifier lowers the false-alarm rate from 0.62 to 0.21
  (−0.412 [−0.559, −0.235]) and raises F1 by 0.11, but costs 11 points of recall (0.797 → 0.686); H3
  allowed 5. In v1 it costs 61 points (0.72 → 0.11).
- **Retrieval and specialist reviewers show no gain**: without retrieval or with one generalist
  reviewer, v2 is as good (slightly ahead on F1, not significant), and the generalist cites a wrong
  section more often (0.936).
- **Reading is still the limit:** with gold annotations (A5_v2_rv) F1 reaches 0.837 and false alarms
  0.03 (partly circular, see above).

### 4.2 The verifier reply bug and its fix

- **What happened.** The verifier asks the 7B model to judge all of a case's checked findings in one
  reply. In 538 of 539 unreadable replies the model wrote one `{"checks": [...]}` object per finding,
  one after the other; the reader took everything from the first `{` to the last `}` and failed. It then
  kept every finding unchecked ("fail open"). Unreadable: 38% of v1 runs (`full`), 25% (`full_finetuned`),
  20% (`full_v2`), 15% (`full_v2_finetuned`); 308 of the 421 findings `full` reported came from such runs.
  The copies never disagree on a finding (0 conflicting verdicts), so reading them together is exact.
- **Fix.** A robust reader (`pipeline/verifier.parse_checks`): normal parsing, then invalid escapes
  removed, then every complete `finding_id`/`supported` pair recovered; the raw reply is stored whenever
  normal parsing fails, and findings that still get no verdict are counted. `scripts/reverify.py`
  re-runs only the verifier on the saved runs (the verifier's input is rebuilt exactly: re-running its
  rule checks changes nothing in any of 2,346 saved runs), so `X` and `X_rv` differ only in the verifier.
- **Result.** 0 unreadable replies and 0 failed calls in 2,346 re-verified runs; 14 findings in total
  got no verdict (cut-off replies). The tagger (0 unreadable of 2,514 + 1,826 paragraphs), the baselines
  B1/B2/B4 and the tools have no such failure; up to 2% of reviewer replies are unreadable, which
  leaves those candidates undecided (no finding, no false alarm).

## 5. Vagueness ladder (RQ2, H4)

**Human check (AC-06.6).** Two members (Naveen Mishra, Anurag Kaushal) checked every rung
independently. They agreed on 107 of 140 rungs (76%, Cohen's κ = 0.19). Most disagreements were on
the deleted rung (Naveen rejected 6, Anurag 24): the guide rejects a deleted rung when even a generic
statement ("may be shared with third-party service providers") covers the flow, and Anurag applied
this strictly. They then settled all 33 disagreements together, re-reading each policy and recording
the deciding sentence (`data/benchmark/ladder/disagreements.csv`): 10 accepted, 23 rejected. A rung is
scored when both accept it: **110 of 140** (clear 34, explicit 30, vague 32, deleted 14); 13 ladders
keep all four rungs. Before the settlement (only rungs both accepted independently, 100 of 140) the
results were the same in direction; the one change is PoliCheck's explicit − vague difference
(+0.38, p = 0.049, before; +0.32, p = 0.064, now).

Accuracy of the target flow's disclosure label per accepted rung (seed 0). Labels do not depend on
the verifier, so the bug of §4.2 does not affect this section.

| System | clear | explicit | vague | deleted | explicit − vague (McNemar p) |
|---|---|---|---|---|---|
| S1 PoliCheck | 0.18 | 0.73 | 0.38 | 0.79 | +0.32 (p = 0.064) |
| S2 PoliGraph | 0.38 | 0.00 | 0.03 | 0.93 | −0.04 (p = 1.00) |
| B2 (seeds 0–2: same scores, outputs differ in 87 of 140 cases) | 0.00 | 0.00 | 1.00 | 0.00 | −1.00 |
| full | **1.00** | 0.53 | 0.84 | 0.14 | −0.29 (p = 0.057) |
| full_finetuned | **1.00** | 0.77 | 0.88 | 0.14 | −0.07 (p = 0.63) |
| full_v2 | **1.00** | 0.63 | 0.84 | 0.14 | −0.18 (p = 0.23) |
| full_v2_finetuned | **1.00** | 0.77 | 0.88 | 0.14 | −0.07 (p = 0.63) |

- **H4** (every system is less accurate on the vague rung than on the explicit rung) fails. Only
  PoliCheck is less accurate on the vague rung, and not significantly (+0.32, p = 0.064); for the
  pipeline the vague rung is read as well as or better than the explicit one.
- **The deleted rung is a real pipeline error.** On the 14 deleted rungs the checkers accept as clean,
  `full_v2_finetuned` is right twice and reads 8 as "vague": the pipeline over-reads generic wording
  even where the checkers found none. PoliCheck reads 11 of the 14 correctly as "omitted".
- PoliGraph has no contradiction label and ignores the generic sentence, so it reads most rungs as
  "omitted".
- B2 calls every flow "vague" on every rung of every ladder.
- PoliCheck's low clear-rung score comes from the data-type mapping (exact only for Location), from not
  resolving the Mixpanel domain to an entity, and from reading a parent company ("Google") as vague.
- On all 140 rungs (before the check) the picture was the same (e.g. `full_v2_finetuned` 1.00 / 0.71 /
  0.80 / 0.09).

### Answer-key spot-check (AC-01.10)

The same two members checked 87 flows of 20 main cases against the policy text. Independently, Naveen
disagreed with the scripted answer on 10 flows (11.5%), Anurag on 14 (16.1%); they agreed with each
other on 77% of flows (κ = 0.04), which bounded the error rate only loosely (2.3–25%). They then
settled the 20 flows they disagreed on together (`data/spot_check/disagreements.csv`): **the answer
key is wrong on 9 of 87 flows (10.3%), in 6 of the 20 cases**. The errors are of three kinds, three
flows each:
- **missed explicit denial** (1264_v1 f4, 962_v2 f3, 962_v2 f4): the policy says it does not do the
  practice ("does not … disclose", "We do not ask for, access or track any location"), so the label
  should be *incorrect*;
- **missed vague gap in a control** (640_control f2, 760_control f5, 995_control f2): the policy only
  covers the flow generically, so these three "compliant" controls in fact contain a vague gap;
- **gap that is not there or at the wrong level** (962_v2 f5, 1618_v2 f4: no purpose gap; 1618_v2 f5:
  purpose gap vague, not omission).

The answer keys are frozen (`specs.md`, constraint 2), so the scores in §4 use them unchanged; the
10.3% estimates the label noise in those scores. The corrected labels are recorded in `agreed_notes` for the
final report.

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
- closes half the A4–A5 gap: no. In v2 (fixed verifier; A5 is seed 0) it closes 9% of the gap on
  F1 (0.692 → 0.705, oracle 0.837), 9% on collection/sharing F1 (0.673 → 0.686, oracle 0.815) and 11%
  on the false-alarm rate (0.294 → 0.265, oracle 0.029).

## 7. Findings so far

1. **Structure helps only when it is wired right.** Same inputs, same 7B model: v1 does not beat B2 on
   F1 (it lowers false alarms, significantly); v2 gains +0.54 F1 and lowers false alarms. The v1-to-v2
   gain changes no model and none of the instructions: it removes a model check where rules already
   decide, shows the reviewer more of the policy, asks one question per call and fixes two decision
   rules.
2. **Evidence-first reviewing was the key design step.** On the dev split, asking the 7B model "is this
   a gap?" confirmed almost every candidate; asking it to copy the disclosing sentence and deciding by
   rule cut false alarms sharply (pipeline.md, dev iterations; measured with the as-run verifier).
3. **A stronger model is not safer.** Gemini 3 Flash with B2's prompt finds far more gaps (recall
   0.72) but raises an alarm on 33 of 34 compliant apps.
4. **The verifier trades recall for safety (H3 fails).** In v1 it rejects most correct findings
   (recall 0.72 → 0.11); in v2, which checks only collection and purpose, it costs 11 points of recall
   and cuts false alarms from 0.62 to 0.21.
5. **Reading is the main remaining error.** With gold annotations F1 rises by 0.11 (v2). Fine-tuning
   more than doubles the tagger's macro-F1, but in the pipeline its gain is small (+0.04 F1, not
   significant; +0.10 on collection/sharing, significant).
6. **The agents did not use their tools.** Reviewers may call `search_policy`, `retrieve_dpdp` and
   `lookup_sdk` (tested), but in all 3,209 pipeline runs (main, ladder and dev splits) they answered directly from the paragraphs
   given, with zero tool calls; a single generalist reviewer (A3) and no retrieval (A2) do as well. In
   practice the reviewers work as single-step evidence extractors, which weakens the "agent" part of
   the design; the gain comes from the pipeline around them.
7. **Collection and purpose gaps are not solved.** Every system misses most purpose mismatches; v2
   reports almost none by itself, because its verifier sends nearly all collection and purpose findings
   to human review.
8. **Silent failures must be counted.** The verifier bug went unnoticed because a failed check kept the
   finding. Every fail-open path is now counted in the run traces and reported (§4.2).

## 8. Status against the plan

| Item (plan §7) | Priority | Status |
|---|---|---|
| Benchmark and B1/B2 | Must | Done |
| Vagueness ladder built and checked | Must | Done: checked by two members, disagreements settled together, scored on the 110 accepted rungs |
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
  be reproduced; a seven-policy known-answer check covering all five PoliCheck labels replaces it,
  and PoliCheck gives the expected label on 7 of 7. A first version used "We share your location with
  Google" for a flow to Google Ads, which PoliCheck reads as *vague* because its entity ontology puts
  "google ads" under "Google"; the same rule lowers its clear-rung score on the ladder (§5).
- B4 needs 102 requests per seed and the free tier allows 20 per key per day; seeds 1–2 ran on
  several team keys (27 Oct), all 306 runs without a failed call.
- v2 of the pipeline (§4.1) was added after the first evaluation runs. It was developed on the dev
  splits only and is reported next to the frozen pipeline, not in place of it.
- The verifier reply bug (§4.2) was found on 28 Oct. The frozen runs are unchanged; the corrected
  numbers come from `*_rv` runs that re-run only the verifier.
- PoliGraph ran on Kaggle instead of the workstation.

## 9. Remaining plan (to 15 Nov)

| Work | When |
|---|---|
| Statement-extraction comparison S4 (PolicyLint, PoliGraph) on tuple F1 | 31 Oct–3 Nov |
| Full system on the ladder, seeds 1–2 | 31 Oct–3 Nov |
| Selective accuracy (SPEC-07) from the three seeds | 6–9 Nov |
| Real-flow sample and case study (SPEC-08) | 4–10 Nov |
| Failure analysis, hypothesis verdicts, final report | 11–15 Nov |

Any further change will follow the v2 rule: developed on the dev splits and reported as a new
configuration, never by changing the frozen runs.
