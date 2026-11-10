# Report: Stage 4 — evaluation extensions (MS-4)

- **Period:** 2026-10-31 to 2026-11-10
- **Status:** complete
- **Specifications:** SPEC-07 (selective accuracy), SPEC-08 (real flows and case study), AC-02.9, SPEC-03 on real flows
- **Plan:** `docs/stage-4-plan.md`

## Summary

Stage 4 tested whether the results on the generated benchmark hold up in three ways: under human
review, on real app traffic and on real open-source apps.

**1. Selective accuracy (H5 partly supported).**
- **Main benchmark:** the headline system `full_v2_finetuned_rv` reaches 95% accuracy after about 21%
  of flows are reviewed. Every single-prompt baseline needs everything reviewed.
- **Vagueness ladder:** the headline system also needs full review, because three rule-decided flows
  rank as fully confident but are wrong.
- **Vague vs explicit rungs:** its confidence is not lower on vague rungs.

**2. Real flows (61 flows from 33 real apps, κ = 0.728 between two labellers).**
- Both published tools and both single-prompt baselines flag every flow, including all 14 that the
  labellers settled as clear. Their agreement with the labellers is at chance level.
- The headline system flags 14% of clear flows and is right on gap/no gap for 95% of flows. Its label
  accuracy is 0.705, and its κ with the labellers is 0.34 and 0.45.
- It is clearly better than every baseline, but still about half as consistent with a human as the
  two humans are with each other.

**3. Case study (Aarogya Setu, Wikipedia, DuckDuckGo; 13 flows, checked by hand).**
- The pipeline is correct on 7 flows, partly correct on 3 and wrong on 3, with no reported false
  alarm. B2 is correct on none of its 9 flows and cannot run on Wikipedia's long policy.
- The pipeline finds the most serious real gap: Aarogya Setu's policy denies any third-party transfer,
  yet the app sends usage events and crash reports to Google. It labels that gap *vague* instead of
  *incorrect*.

| Part | Plan step | Result |
|---|---|---|
| A. Real-flow sample | AC-08.1 | 33 apps, 61 flows (target 60–80; ~25 apps) |
| B. Two-person labels | AC-08.2 | κ 0.728, 9 disagreements settled |
| C. Runs and scores | AC-08.3, AC-02.9 | S1, S2, B1, B2, `full_v2_rv`, `full_v2_finetuned_rv`; 0 failed calls |
| D. Case study | AC-08.4 | 3 apps, 13 flows, every finding checked by hand |
| E. Selective accuracy | SPEC-07 | main and ladder, R@95 intervals, H5 verdict |

**Reproduce:**
- Scores: `bash scripts/score_all.sh` regenerates every Stage 4 score from the committed runs.
- Runs: the Kaggle jobs are `kaggle/pipeline` (real-flow JOBS), `kaggle/policheck`,
  `kaggle/poligraph`, `kaggle/real_flows_finetuned` and `kaggle/case_study`.

## 1. Selective accuracy (SPEC-07, H5)

**Question.** How much human review does a checker need before its remaining labels can be
trusted? The unit is the flow:
- Each flow gets the majority label over three seeds and a confidence (share of seeds agreeing,
  then token probability).
- Flows are reviewed from least to most confident, and a reviewed flow takes its gold label.
- **R@95** is the share that must be reviewed before the unreviewed flows are 95% accurate.
- Tools have no confidence, so they appear as points at 0% review.

`python scripts/selective_accuracy.py --split {main,ladder}` →
`results/scores/selective_{main,ladder}.json`, `results/figures/selective_{main,ladder}.png`.

### Main benchmark (433 flows; best tool S2, accuracy 0.492)

| System | Accuracy | AUC | R@95 [95% CI] | R@95 − B2 [95% CI] | Review to match best tool |
|---|---|---|---|---|---|
| B1 | 0.139 | 0.142 | 0.988 [0.97, 1.00] | −0.01 [−0.03, 0.00] | 0.977 |
| B2 | 0.074 | 0.053 | 1.000 [1.00, 1.00] | — | 1.000 |
| B4 (Gemini 3 Flash) | 0.520 | 0.547 | 1.000 [1.00, 1.00] | 0.00 [0.00, 0.00] | 0 |
| v1 `full` | 0.663 | 0.864 | 0.561 [0.45, 1.00] | −0.44 [−0.55, 0.00] | 0 |
| v1 `full_finetuned` | 0.852 | 0.971 | 0.212 [0.12, 0.31] | −0.79 [−0.88, −0.69] | 0 |
| v2 `full_v2` | 0.755 | 0.895 | 0.559 [0.41, 1.00] | −0.44 [−0.59, 0.00] | 0 |
| **v2 `full_v2_finetuned`** | **0.852** | **0.972** | **0.212 [0.11, 0.30]** | **−0.79 [−0.89, −0.70]** | 0 |

The headline system needs about **one flow in five** reviewed (21%) to reach 95% accuracy on the
rest. B2 needs every flow reviewed. B4 is more accurate than any tool, but its confidence does not
order its errors: it also needs full review for 95%.

### Vagueness ladder (110 accepted rungs; best tool S1, accuracy 0.464)

| System | Accuracy | AUC | R@95 [95% CI] | R@95 − B2 [95% CI] |
|---|---|---|---|---|
| B2 | 0.291 | 0.305 | 1.000 [0.98, 1.00] | — |
| v1 `full` | 0.745 | 0.873 | 0.618 [0.53, 1.00] | −0.38 [−0.46, 0.00] |
| v1 `full_finetuned` | 0.782 | 0.882 | 1.000 [0.37, 1.00] | 0.00 [−0.63, +0.01] |
| v2 `full_v2` | 0.773 | 0.902 | 0.600 [0.50, 0.67] | −0.40 [−0.50, −0.33] |
| **v2 `full_v2_finetuned`** | **0.782** | 0.882 | **1.000 [0.37, 1.00]** | **0.00 [−0.63, +0.01]** |

**Why the fine-tuned systems need full review on the ladder.**
- With the QLoRA tagger, 32 of the 110 ladder flows are decided by the pipeline's rules, with the same
  label on all three seeds. A rule decision has no token probability, so these flows rank as the
  *most* confident and are reviewed last.
- Three of the 32 are wrong. Each is labelled *clear* when the gold label is *incorrect*, *vague* or
  *omitted*; the three are on an explicit, a vague and a deleted rung.
- That last group is only 29/32 = 90.6% accurate, so the unreviewed flows cannot reach 95% until
  everything is reviewed.
- The prompted-tagger systems have 24 such flows and none wrong, which is why `full_v2` reaches 95%
  at 60%.

The cause is a confidence-ordering choice, not low accuracy: the fine-tuned system is the most
accurate on the ladder (0.782). The review order treats a rule decision as certain. Three confident
rule errors are enough to break that assumption on a 110-flow set.

### Confidence on vague vs explicit rungs (paired over 28 ladders)

| System | Agreement: vague − explicit [95% CI] | Token probability: vague − explicit [95% CI] |
|---|---|---|
| B2 | +0.036 [0.000, +0.071] | +0.0030 [−0.0044, +0.0113] |
| v2 `full_v2` | +0.024 [−0.036, +0.095] | **−0.0088 [−0.0169, −0.0004]** |
| v2 `full_v2_finetuned` | −0.012 [−0.083, +0.071] | −0.0027 [−0.0089, +0.0038] |

Only `full_v2` (prompted tagger) is less confident on vague rungs, on token probability, and the
difference is small (under one percentage point). No system is reliably less confident on vague
rungs by seed agreement.

### H5 verdict

> H5: the full system needs less review than B2 for 95% accuracy, and its confidence is lower on vague
> than on explicit rungs.

- **Main benchmark: holds.** `full_v2_finetuned` needs 21% review against 100% for B2. The difference
  is −0.79 [−0.89, −0.70], and the interval excludes 0. The v1 and v2 prompted-tagger systems also
  need less review (−0.44), but their intervals reach 0.
- **Ladder: does not hold for the headline system.** Three confident rule errors make R@95 = 1.0 (the
  difference with B2 is 0.00 [−0.63, +0.01]). `full_v2` with the prompted tagger does hold:
  −0.40 [−0.50, −0.33].
- **Vague-rung confidence: does not hold** for the headline system. It holds weakly for `full_v2`, on
  token probability only.

**Overall: H5 is partly supported.** The selective-review claim holds on main. It is fragile on the
ladder because rule decisions are treated as certain. A fix for the final system would be a calibrated
confidence for rule decisions, for example their observed accuracy on the dev splits. Such a fix
would have to be chosen on dev, not on the ladder.

## 2. Real flows (SPEC-08, AC-08.1–08.3; AC-02.9)

**Sample.** 61 real network flows from 33 apps:
- **Flows:** PoliCheck's released traffic, captured 2017–2019.
- **Policies:** the Wayback Machine copy closest to Feb 2019.
- **Yield:** 149 apps tried and 39 usable policies (26%). The failure rule (fewer than 20 apps) was not
  triggered.
- **Mix:** 52 device-ID flows, 7 location and 2 contact; 45 sharing and 16 first-party collection.

Details are in `data/real_flows/README.md`. Real traffic has no purpose or retention, so these flows
test **collection and sharing disclosure only**.

**Labels.** Two members (Naveen, Anurag) labelled every flow independently, without seeing any
system output. They agreed on 52 of 61 flows, **Cohen's κ = 0.728**, and settled all 9
disagreements together. The settled labels are 40 vague, 14 clear, 5 omitted and 2 incorrect.

**Runs.** Every configuration ran as frozen on Kaggle, 0 failed calls:

| System | Seeds | Run by |
|---|---|---|
| S1 PoliCheck | 1 | Nikhil (51 of 61 flows matched a tool row) |
| S2 PoliGraph | 1 | Nikhil (47 of 61 matched; 2 of 33 policies failed to crawl) |
| B1, B2, `full_v2_rv` | 3 each | Nikhil |
| `full_v2_finetuned_rv` | 3 | Ishaan (the 29 Oct QLoRA adapter, not retrained) |

**Two infrastructure fixes, with the analysis unchanged:**
- **PoliCheck** is Python 2 and crashed on the curly quotes in real policies, first in `print`, then
  in its CSV writer. Its input is now converted to ASCII: quotes and dashes become ASCII and accents
  are dropped. This affected 31 of 33 policies (`kaggle/policheck/run.py`, `ascii_policies`).
- **PoliGraph** now treats each real-flow app as its own policy, because package names contain `_`.

`python scripts/score_real_flows.py` → `results/scores/real_flows.json` (mean over seeds; 95% app-level
bootstrap on seed 0):

| System | Label accuracy | Label macro-F1 | Gap / no gap accuracy | Clear flows flagged | F1 (collection/sharing) | κ with Naveen | κ with Anurag |
|---|---|---|---|---|---|---|---|
| S1 PoliCheck | 0.344 | 0.195 | 0.770 | 1.000 | 0.796 | 0.112 | 0.046 |
| S2 PoliGraph | 0.131 | 0.077 | 0.770 | 1.000 | 0.796 | −0.040 | −0.079 |
| B1 | 0.645 | 0.196 | 0.770 | 1.000 | 0.747 | −0.012 | −0.012 |
| B2 | 0.650 | 0.224 | 0.770 | 1.000 | 0.380 | 0.017 | −0.017 |
| `full_v2_rv` (prompted tagger) | 0.596 | 0.382 | 0.913 | 0.310 | 0.775 | 0.209 | 0.298 |
| **`full_v2_finetuned_rv`** | **0.705** | **0.438** | **0.951** | **0.143** | 0.744 | **0.341** | **0.450** |
| *Humans: Naveen vs Anurag* | *0.852* | | | | | *0.728* | |

Paired differences on seed 0, headline system minus the other system, with 95% intervals:

| vs | Label accuracy | Gap / no gap accuracy | Clear flows flagged | F1 (collection/sharing) |
|---|---|---|---|---|
| S1 | **+0.38 [+0.12, +0.62]** | **+0.18 [+0.07, +0.28]** | **−0.86 [−1.00, −0.64]** | −0.05 [−0.16, +0.06] |
| S2 | **+0.59 [+0.44, +0.73]** | **+0.18 [+0.07, +0.28]** | **−0.86 [−1.00, −0.64]** | −0.05 [−0.16, +0.06] |
| B1 | +0.08 [−0.09, +0.22] | **+0.18 [+0.07, +0.28]** | **−0.86 [−1.00, −0.64]** | +0.01 [−0.09, +0.13] |
| B2 | +0.07 [−0.10, +0.20] | **+0.18 [+0.07, +0.28]** | **−0.86 [−1.00, −0.64]** | **+0.37 [+0.22, +0.55]** |
| `full_v2_rv` | +0.13 [0.00, +0.28] | +0.03 [−0.03, +0.09] | −0.14 [−0.33, 0.00] | −0.05 [−0.10, 0.00] |

**Reading the results**
- **Every baseline and tool flags every flow.** All four flag all 14 flows the labellers settled as
  *clear*, so they are right on gap/no gap exactly as often as there are gaps (47/61 = 0.770).
  - On F1 this costs them little, since 77% of real flows have a gap. That is why F1 does not separate
    the systems here.
  - B1 and B2's label accuracy (0.65) is close to labelling every flow *vague* (40/61 = 0.656).
  - Their κ with the labellers is about 0, which is chance agreement.
- **Only the pipeline tells clear flows apart.** The headline system flags 2 of the 14 (14%) and is
  right on gap/no gap for 95% of flows; the prompted-tagger version flags 31%. Its κ with the labellers is 0.34 and 0.45, against about 0
  for every baseline and tool.
- **It is still far from a second human.** Its κ is about half the labellers' 0.728, and its
  label macro-F1 is 0.44: it often confuses *omitted* and *incorrect* with *vague*.
- **The fine-tuned tagger helps here too.** It does better than the prompted tagger on every label
  measure. Label accuracy is +0.13 [0.00, +0.28], and only 14% of clear flows are flagged against
  31%. The intervals touch 0.
- **The tools' native reading (vague = consistent) scores F1 0.22 (PoliCheck) and 0.07 (PoliGraph).**
  Almost every real gap here is a vague disclosure, which their reading treats as consistent.

**Labeller-agreement check (AC-08.2).** The labellers' κ of 0.728 is well above the ladder check's 0.19
and the spot-check's 0.04. The guide and practice round did their job, and the settled labels are a
usable ground truth.


## 3. Open-source case study (SPEC-08, AC-08.4)

**Apps:** Aarogya Setu (Government of India; code of June 2020 and its policy of July 2020),
Wikipedia and DuckDuckGo (code and policies of 2026).

**Data flows:** 13 in total, written by hand from the code, each with a file:line citation
(`data/case_study/apps.json`).

**Runs:** `full_v2_finetuned_rv`, with the same QLoRA adapter as on main, and B2. Both run as frozen on
seeds 0–2, with 0 failed calls for the pipeline.

**Hand check:** every output is checked against the policy (`data/case_study/findings.csv`). The case
study is qualitative and has no statistics.

| | `full_v2_finetuned_rv` (13 flows) | B2 (9 flows) |
|---|---|---|
| Correct | 7 | 0 |
| Partly correct (gap found, wrong level or held back as uncertain) | 3 | 4 |
| Wrong | 3 | 5 |
| Not run | — | Wikipedia: the 7,447-word policy needs 10,938 input tokens, which with 2,048 output tokens exceeds the 12,288-token context |

The pipeline gave the same answer on all three seeds for every flow, its wrong answers included.
Here, seed agreement does not separate right answers from wrong ones.

**What the pipeline got right**
- **Aarogya Setu's sharing with Google.** The policy says (P25) that *no personal information
  collected by the App will be disclosed or transferred to any third party*. The code sends:
  - usage events and user properties to Firebase Analytics (`AnalyticsUtils.kt:62-86`);
  - crash reports to Crashlytics (`CoronaApplication.java:46`).

  The pipeline reports undisclosed sharing for both flows on every seed and cites DPDP Sec. 5(1)
  (notice). This is the finding with the most weight for the DPDP Act: a Government of India app
  whose notice denies the transfer.
- **Explicitly disclosed flows are left alone.** These are labelled *clear* with no finding:
  - Aarogya Setu: the phone number (P3) and location (P3, P5, P6);
  - Wikipedia: usage analytics, location for Nearby, and email;
  - DuckDuckGo: anonymous usage pixels and broken-site URLs.

  B2 raised a gap on every one of these.

**What it got partly right**
- **Aarogya Setu's sharing with Google is labelled *vague*, not *incorrect*.** The verifier quoted a
  paragraph about how the DiD is used (P9), not the denial in P25. The contradiction is the more
  serious gap, and it is missed. The ladder shows a similar weakness: the headline system misses 8
  of the 30 *incorrect* rungs, 4 of them labelled *vague* (`results/confidence/ladder.json`).
- **Aarogya Setu's device identifiers** (Bluetooth MAC address and name, FCM token;
  `CorUtility.kt:136-139`) are not mentioned in the policy. The pipeline finds the gap on every seed,
  but labels it *vague* and holds it back as *uncertain*, so it is not reported.

**What it got wrong**
- **DuckDuckGo's Email Protection address** is labelled *incorrect*. The flow is disclosed in P19
  (*Email Protection is an optional feature that requires your email address*). The pipeline quoted
  P29 instead, about handing an email address to authorities. The finding was held back as uncertain,
  so it is not reported, but the label is wrong.
- **Two vague disclosures are labelled clear.** One is Wikipedia's per-install analytics id (P114
  mentions device ids only for beta app versions). The other is DuckDuckGo's device model in
  broken-site reports. Both calls are debatable.

**DPDP angle.** Real flows from 2019 cannot test purpose, retention or an Indian context; the case
study is where those come in. It finds no purpose or retention gap: the code shows no server-side
retention, and every purpose matches a stated one. The main DPDP finding is a notice (Sec. 5) gap in
Aarogya Setu. The pipeline finds this gap but understates its level.

