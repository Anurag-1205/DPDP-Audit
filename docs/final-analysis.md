# Final analysis: hypothesis verdicts, costs and failures (WP-5.1)

- **Status:** complete (11 Nov 2026); every number checked against `results/scores/` and the saved runs
- **Owner:** Anurag Kaushal
- **Specification:** SPEC-09, AC-09.6 (verdicts) and AC-09.7 (failure analysis and cost table)
- **Sources:** [mid-submission-report.md](mid-submission-report.md) (§4–§6), [stage-4-report.md](stage-4-report.md)
- **Reproduce:** `python scripts/cost_table.py` → `results/scores/cost_main.json`;
  `python scripts/error_tally.py` → `results/scores/errors.json` (both from the committed runs, no GPU)

The headline system is v2 of the pipeline with the QLoRA tagger and the fixed verifier,
`full_v2_finetuned_rv`. Every difference below is the paired policy-level bootstrap on seed 0 with
its 95% interval; **bold** means the interval excludes 0.

## 1. Hypothesis verdicts (AC-09.6)

| Claim | Verdict | Deciding evidence | Real flows and case study |
|---|---|---|---|
| **Falsifiable claim**: beats PoliCheck and PoliGraph on their gap types and B2 on the full benchmark, in F1 and false-alarm rate | **Fails for v1, holds for v2** | v2 − B2: F1 **+0.535 [+0.451, +0.607]**, false alarms **−0.471 [−0.706, −0.235]**; v2 − PoliCheck / PoliGraph: common F1 **+0.561** / **+0.535**, false alarms **−0.706** / **−0.647**. v1 `full_rv` − B2: F1 −0.024 [−0.136, +0.105] | Real flows: label accuracy vs the tools **+0.38** / **+0.59**, vs B2 +0.07 [−0.10, +0.20]; the headline system flags 14% of clear flows, every baseline and tool flags all of them |
| **H1**: the full system beats PoliCheck and PoliGraph on collection and sharing | **Holds for v2, fails for v1** | v2, common view: **+0.561** and **+0.535**; tools' native reading: **+0.222** and **+0.334**; label macro-F1 0.495 vs 0.225 and 0.197. v1: −0.097 (common) and **−0.192** (native) vs PoliCheck | Real flows: F1 does not separate the systems (77% of flows have a gap; −0.05 [−0.16, +0.06] vs both tools), but label accuracy and gap/no gap accuracy do (**+0.18**) |
| **H2**: the full system beats B1 and B2 on the full benchmark, most on vague and omission gaps | **First half holds for v2; second half fails** | v2 − B2: **+0.535**, v2 − B1: **+0.539**. Gain over B2 by level: explicit +0.54, vague +0.45, omission +0.45, so the gain is largest on explicit gaps. v1 has no F1 gain | Case study: 7 of 13 flows correct against 0 of 9 for B2 |
| **H3**: the verifier lowers false alarms and costs at most 5 points of recall | **Fails** | v2: false alarms 0.62 → 0.21 (**−0.412**), but recall 0.797 → 0.686, 11 points. v1: recall 0.72 → 0.11, 61 points | — |
| **H4**: every system is less accurate on vague than on explicit ladder rungs | **Fails** | Only PoliCheck is lower on vague, and not significantly (+0.32, McNemar p = 0.064); the pipeline reads vague rungs as well as or better than explicit ones (0.88 vs 0.77) | — |
| **H5**: the full system needs less review than B2 for 95% accuracy, and is less confident on vague rungs | **Partly supported** | Main: R@95 0.21 vs 1.00, **−0.79 [−0.89, −0.70]**. Ladder: R@95 1.00, 0.00 [−0.63, +0.01], from three confident rule errors. Vague − explicit confidence: −0.012 [−0.083, +0.071] (agreement) | Case study: the pipeline gave the same answer on all three seeds for every flow, wrong answers included |
| **H6**: the fine-tuned tagger beats B3, is within 5 points of PrivBERT and closes half the gap between the prompted tagger (A4) and gold annotations (A5) | **Fails (one of three parts holds)** | Beats B3: yes (macro-F1 0.713 vs 0.388). Within 5 points of PrivBERT: no (0.779, 6.6 points). Half the A4–A5 gap: no, 9% on F1 (0.692 → 0.705, oracle 0.837) | Real flows: the fine-tuned tagger is ahead on every label measure, label accuracy +0.13 [0.00, +0.28] |

**In one line:** v2 beats every baseline and both tools on the benchmark and on real flows; H3, H4
and H6 fail, H5 holds only on main, and the claimed advantage on vague gaps (H2, second half) is not
there.

## 2. Cost per case (AC-09.7)

Main benchmark, 102 cases, mean per case over every seed (`results/scores/cost_main.json`). Qwen runs
were on Kaggle T4 GPUs; seconds are the wall-clock time recorded in each run trace.

| System | Model | Model calls | Prompt tokens | Output tokens | Thinking tokens | Seconds (mean / median) |
|---|---|---|---|---|---|---|
| B1 | Qwen2.5-7B | 1.0 | 3,621 | 343 | — | not recorded |
| B2 | Qwen2.5-7B | 1.0 | 5,055 | 420 | — | not recorded |
| B4 | Gemini 3 Flash | 1.0 | 5,167 | 334 | 4,795 | not recorded |
| B5 | Qwen2.5-7B | 1.8 | 4,837 | 1,839 | — | 167 / 145 |
| R0 (rules only) | none | 0 | 0 | 0 | — | 0.2 |
| v1 `full` | Qwen2.5-7B | 2.9 | 4,879 | 849 | — | 101 / 95 |
| v1 `full_finetuned` | Qwen2.5-7B | 2.7 | 3,690 | 645 | — | 68 / 63 |
| v2 `full_v2` | Qwen2.5-7B | 5.2 | 7,773 | 911 | — | 108 / 101 |
| **v2 `full_v2_finetuned`** | Qwen2.5-7B | **3.7** | **4,639** | **639** | — | **67 / 65** |

- **The headline system costs about as much as one B2 call in tokens** (5,278 against 5,475 per
  case), spread over 3.7 calls, and about 67 seconds per case on a T4.
- **B4 spends most of its tokens thinking:** 4,795 thinking tokens per case on top of 5,501 in and out.
- **The fine-tuned tagger makes the pipeline cheaper,** not only better: v2 needs 3.7 calls and 67 s
  with it, 5.2 calls and 108 s with the prompted tagger, because the finder passes fewer flows to the
  reviewers (3.0 candidates per case against 4.4; v2 reviews one candidate per call).
- **B5 is the slowest** (167 s), because one call writes evidence for every flow of the app.

Not in the table:
- **Tagging** ran once over every policy paragraph before the runs (34 paragraphs per case on
  average). It is shared by every pipeline configuration and is not recorded per case.
- **The re-run verifier** (`*_rv`) added 499 prompt and 92 output tokens per case for the headline
  system. A deployed system would make this call instead of the frozen verifier's, not in addition.
- **PoliCheck and PoliGraph** ran on CPU and record no per-case time.

## 3. Where the headline system goes wrong (AC-09.7)

`results/scores/errors.json`; each error cell lists example cases.

### Findings on main (seeds 0–2 summed)

| Gap type | Gold | Reported right | Reported wrong | of which on controls | Missed | Sent to review | Review was a real gap |
|---|---|---|---|---|---|---|---|
| Children's data | 54 | 54 | 0 | 0 | 0 | 0 | 0 |
| Retention mismatch | 93 | 93 | 0 | 0 | 0 | 0 | 0 |
| Undisclosed sharing | 96 | 93 | 16 | 5 | 3 | 0 | 0 |
| Undisclosed collection | 48 | 1 | 21 | 7 | 47 | 130 | 28 |
| Purpose mismatch | 63 | 1 | 54 | 15 | 62 | 122 | 16 |

- **Three gap types are solved**: children's data and retention have no errors, and sharing misses
  3 of 96.
- **Collection and purpose are not solved.** Nearly every real gap of these types is missed, and they
  make up 75 of the 91 wrong findings.
- **Most findings sent to human review were wrong.** Only 28 of 130 collection findings and 16 of 122
  purpose findings held back by the verifier were real gaps, so holding them back was mostly right.
  Releasing them would add 44 correct findings and 208 false ones.

### Disclosure labels (majority label over three seeds)

| Data | Flows | Accuracy | Most frequent errors (gold → predicted) |
|---|---|---|---|
| Main | 433 | 0.852 | clear → vague 32, clear → incorrect 11, vague → clear 5 |
| Ladder (accepted rungs) | 110 | 0.782 | omitted → vague 10, incorrect → vague 4, incorrect → clear 3 |
| Real flows | 61 | 0.754 | vague → incorrect 6, omitted → vague 4, clear → vague 2 |

The real-flow accuracy here (0.754) is for the majority label; the Stage 4 report's 0.705 is the
mean over seeds. Two of the 61 real flows got three different labels on the three seeds; the tally
counts them as the first label in the order clear, vague, omitted, incorrect.

Reading the reviewer's own quote and rationale for the error cells (seed 0) gives five patterns:
1. **The disclosing sentence never reaches the reviewer.** The reviewer sees only the paragraphs the
   finder passes it, and the sentence that discloses the flow is often not among them, so it quotes a
   generic one. `1259_control f2` and `1028_control f2` (worked cases A and B) both miss a sentence
   that names the data type outright. Of the 32 clear flows on main labelled *vague*, a strict word
   check also finds 13 whose policy never names the data type at all: there *vague* is probably right
   and the answer key wrong (one of them, `640_control f2`, is a confirmed key error from the
   spot-check).
2. **"Not mentioned" is read as "denied".** All 13 wrong *incorrect* labels on main (clear → incorrect
   11, vague → incorrect 2) quote a sentence with no negation at all, and the rationale says only that
   the policy "does not explicitly state" the flow. The 6 vague → incorrect real flows are the same:
   for example `com.medisafe.android.client` f1 quotes *"we collect certain technical information …
   such as your IP address"* and calls the AppsFlyer flow contradicted.
3. **A denial is found but not applied.** On incorrect ladder rungs the reviewer often quotes the
   denial and says so, yet outputs *vague*: `L1637_r2` quotes *"We do not share your device and
   browser information with third parties"*, its rationale says the policy explicitly states this,
   and the label is *vague*. The same happens on `L1028_r2` and `L1468_r2`. In the case study the
   Aarogya Setu denial is missed for a different reason: the quoted paragraph (P9) is not the denial
   (P25).
4. **A sentence about another practice counts as cover.** Deleted rungs are read as *vague*
   (omitted → vague: 10 on the ladder, 4 on real flows) from a sentence about first-party logging,
   e.g. `L1468_r4` quotes *"The Company may also keep track of IP addresses"* for a flow to AdMob.
5. **A tagger error becomes a confident rule decision.** All three wrong rule-decided ladder flows,
   which rank as most confident, are rungs of one ladder (`L82_r2`, `L82_r3`, `L82_r4`, worked case
   E). One misread paragraph is therefore why R@95 is 1.0 on the ladder (H5).

Some "errors" are answer-key errors. On `L1028_r4` (gold *omitted*) the system answers *incorrect*
on seed 0, quoting *"These companies may use information (not including your name, address, email
address or telephone number)"*. That sentence was left in the base policy, so the system is right and
the rung's key is not. Both checkers accepted this rung; the 10.3% key error found in the spot-check
(mid-submission report §5) is the scale of this noise on main.

**Limits of the ground truth.** The answer keys are computed by rules from OPP-115 annotations, and
the human checks measure their noise (10.3% of spot-checked flows; κ 0.19 on the ladder, 0.04 on the
spot-check). Two departures from the project's "no LLM in ground truth" rule are recorded in the
reports: the settled verdicts for the ladder and spot-check disagreements, and one of the two
real-flow label sheets, were drafted with an LLM assistant and then reviewed by the members. The
real-flow κ of 0.728 is therefore between one human labeller and one human-reviewed draft.

## 4. Worked hard cases

One case per pattern, plus one answer-key error. The quotes are verbatim from the policy and from the
reviewer's saved reply on seed 0; the labels are the majority over the three seeds.

**A. The disclosing sentence is not shown (`1259_control f2`, IP address and device IDs, collected
by the app's company; gold *clear*, predicted *vague* on all three seeds).**
- The policy says in P5: *"We collect IP addresses for site security and to help us understand how
  people use our sites so that we can improve our sites and our users' respective experiences."*
- The finder passed the reviewer P3, P8, P9, P17 and P39, not P5. The reviewer quoted *"The Motley
  Fool collects information about our readers … We ask for your name, email address, and other
  personal information"* and reasoned that this *"could include these data types"*.
- Why it matters: the decision rule worked as designed on the evidence it got. The loss is in
  retrieval, which is the error the oracle tagger (A5) removes (+0.11 F1).

**B. "Not mentioned" read as "denied" (`1028_control f2`, IP address and device IDs, collected by the
app's company; gold *clear*, predicted *incorrect* on all three seeds).**
- The policy says in P12: *"This includes internet protocol (IP) addresses, browser type, internet
  service provider (ISP) …"* (about its log files). P12 was not shown.
- The reviewer quoted a sentence about contact details and unique identifiers *"such as, username
  and password"*, reasoned that the policy *"does not explicitly state that the company collects IP
  addresses"*, and still labelled the flow *incorrect*, a contradiction.
- Why it matters: *incorrect* is the most serious label. All 13 wrong *incorrect* labels on main
  quote no denial, so the system's contradictions cannot be trusted without the quote.

**C. A denial found but not applied (`L1637_r2`, computer information shared with Google AdMob;
gold *incorrect*, predicted *vague* on all three seeds).**
- The rung inserts *"We do not share your device and browser information with third parties."* The
  reviewer quoted exactly that sentence and reasoned that *"the policy explicitly states that device
  and browser information is not shared with third parties"*.
- It then answered *vague*. The label does not follow the reviewer's own evidence; a rule that checks
  the quote for a negation would have caught it.

**D. Another practice counts as cover (`L1468_r4`, IP address and device IDs shared with Google
AdMob; gold *omitted*, predicted *vague* on two of three seeds).**
- The base policy says nothing about sharing these identifiers. The reviewer quoted *"The Company may
  also keep track of IP addresses used to access its Online Services for various reasons"*, which is
  about the company's own logging, and reasoned that the policy *"does not explicitly state that the
  IP address and device IDs are shared with Google AdMob, nor does it deny sharing them"*.
- Why it matters: this is the deleted-rung over-reading of the ladder (deleted-rung accuracy 0.14).
  R0, which has no LLM reviewer, reads 64% of deleted rungs correctly, so the error is added by the
  review step.

**E. A tagger error becomes a confident rule decision (`L82_r2` to `L82_r4`, location collected by the
app's company; gold *incorrect*, *vague* and *omitted*, predicted *clear* on every seed).**
- The QLoRA tagger reads P4 of the base policy, *"Log file information is automatically reported by
  your browser … our servers automatically record certain information that your web browser sends"*,
  as a collection of Location.
- The finder therefore treats the flow as clearly disclosed and only raises a purpose question, so no
  reviewer ever reads the rung's sentence, including the inserted denial *"We do not collect your
  precise location."* on r2.
- Why it matters: a rule decision has no token probability, so selective review treats it as certain
  and reviews it last. These three flows alone make R@95 1.0 on the ladder.

**F. The answer key is wrong, not the system (`L1028_r4`, contact details shared with Google AdMob;
gold *omitted*).**
- The script that built the base policy left in: *"These companies may use information (not
  including your name, address, email address or telephone number) about your visits to this and
  other Web sites in order to provide advertisements"*.
- On seed 0 the system answered *incorrect* and quoted that sentence; seeds 1–2 answered *vague*.
  The sentence contradicts the flow, so *incorrect* is right and the rung should not count.
- Why it matters: both checkers accepted this rung. With the spot-check's 10.3% key error on
  main, part of every system's measured error is answer-key noise.

## 5. What this means for the final system

- **Check the label against the quote.** A rule that requires a negation in the quote for *incorrect*
  (case B) and returns *incorrect* when the quote is a denial (case C) addresses patterns 2 and 3
  without a new model.
- **Show the reviewer more of the policy.** Cases A and E are retrieval and reading errors; the
  oracle tagger's +0.11 F1 is the size of this gap.
- **Calibrate rule decisions.** Giving rule-decided flows their observed accuracy on the dev splits
  as confidence would stop case E from breaking selective review.
- **Collection and purpose need different evidence.** They account for 75 of 91 wrong findings, and
  the verifier rightly holds most of them back.

Any of these would be a new configuration, chosen on the dev splits only, as v2 was.
