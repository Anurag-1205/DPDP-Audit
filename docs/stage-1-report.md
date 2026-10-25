# Report: Stage 0–1 — benchmark and single-pass baselines

- **Period:** 2026-10-15 to 2026-10-24
- **Status:** complete
- **Specifications:** SPEC-01, SPEC-02 (B1/B2), SPEC-03 (PoliCheck smoke test)

## Summary

The main benchmark (102 cases, 118 gold findings, 433 labelled flows) is built from the 35 held-out
OPP-115 policies, with scripted answer keys. The single-pass baselines B1 and B2 ran on every case
with three seeds each on Qwen2.5-7B-Instruct: 612 runs, with no failed calls and no unparseable
replies. PoliCheck builds and runs; a two-case smoke test passed. The headline finding: **a single
prompt to a 7B model flags almost every compliant app**.

## Stage 0 checklist

| Item | Result |
|---|---|
| Roles | M1 Anurag Kaushal · M2 Ishaan Giri · M3 Naveen Mishra · M4 Nikhil Patidar |
| Repository | Shared repository with versioned results |
| PoliCheck | Docker image builds; runs on the benchmark export |
| Model on Kaggle | Qwen2.5-7B-Instruct-AWQ answers "OK" with log-probabilities (`results/stage0_model_check.json`) |

## Baseline results

Mean over three seeds (`results/scores/main.json`):

| System | F1 (full) | F1 (collection/sharing) | same, vague = consistent | Label macro-F1 | False-alarm rate | Citation correct |
|---|---|---|---|---|---|---|
| B1 · single prompt, raw inputs | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 | 0.318 |
| B2 · single prompt, parsed facts + DPDP text | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 | 0.894 |

Seed 0 with 95% policy-level bootstrap intervals:

| Measure | B1 | B2 | B2 − B1 (paired) |
|---|---|---|---|
| F1 (full) | 0.184 [0.145, 0.224] | 0.188 [0.145, 0.233] | +0.004 [−0.027, 0.035] |
| False-alarm rate | 0.971 [0.912, 1.000] | 0.676 [0.529, 0.824] | −0.294 [−0.471, −0.118] |

Recall by level (seed 0):

| System | explicit | vague | omission |
|---|---|---|---|
| B1 | 0.24 | 0.68 | 0.15 |
| B2 | 0.21 | 0.50 | 0.27 |

## Interpretation

1. **Over-flagging is the main failure.** B1 reports a gap in 97% of compliant apps.
2. **Better inputs help safety and grounding, not detection.** Parsed facts and DPDP text cut false
   alarms by about 0.29 (significant) and raise citation correctness from 0.32 to 0.89. F1 is
   unchanged.
3. **Explicit contradictions are found least often,** even though they are the easiest for a human
   reader.

These results motivate the evidence-gated design (the verifier should target false alarms) and the
vagueness ladder (it supplies controlled explicit cases).

## PoliCheck smoke test

| Case | Flow | PoliCheck | Gold |
|---|---|---|---|
| `1028_control` | 3 compliant first-party flows | vague | clear |
| `1028_v1` | planted `serial number → Google Ads` | ambiguous (cites "We DO NOT Share Personal Information with Third Parties") | vague |

The approximate data-type mapping is one cause of PoliCheck's vague labels on compliant flows: Contact
maps to "email address", so the policy's "contact information" is only a broader term. Raw output is
in `results/tools/policheck/main/policheck_results.csv`.

## Known limitations

- Explicit and omitted collection/sharing gaps exist in only 2–3 held-out policies each (exploratory
  cells; see [benchmark.md](benchmark.md#generic-negative-statements)).
- The export can express 65% of benchmark flows in PoliCheck's vocabulary, and only 12% exactly.
- OPP-115 policies are US websites from about 2015; generated apps are cleaner than real code.
