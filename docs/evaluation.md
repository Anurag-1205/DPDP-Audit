# Evaluation

## Systems under test

```mermaid
flowchart LR
    root(("Systems<br/>under test"))
    root --> e2e["End-to-end<br/>policy + app → findings"]
    root --> comp["Component<br/>policy → claims"]
    e2e --> tools["Existing tools<br/>S1 PoliCheck · S2 PoliGraph"]
    e2e --> single["Single-pass LLM<br/>B1 raw inputs · B2 facts + DPDP<br/>B4 Gemini"]
    e2e --> ours["DPDP-Audit<br/>full · A1–A5"]
    comp --> c1["S3 PrivBERT"]
    comp --> c2["S4 PolicyLint and<br/>PoliGraph extraction"]
    comp --> c3["B3 prompted 3B tagger<br/>QLoRA 3B tagger (ours)"]
```

| ID | System | Model / implementation | Gap types | Seeds |
|---|---|---|---|---|
| S1 | PoliCheck | Authors' code in Docker | collection, sharing | 1 (deterministic) |
| S2 | PoliGraph | Authors' released code (NLP) | collection, sharing | 1 (deterministic) |
| B1 | Single pass, raw inputs | Qwen2.5-7B-Instruct-AWQ | all | 3 |
| B2 | Single pass, parsed facts + DPDP text | Qwen2.5-7B-Instruct-AWQ | all | 3 |
| B4 | B2's prompt, stronger model | `gemini-3-flash-preview` | all | 3 |
| full | DPDP-Audit | Qwen2.5-7B + tagger | all | 3 |
| A1–A5 | Ablations | as full, one change each | all | 1 |
| S3 | PrivBERT | `mukund/privbert`, fine-tuned on our split | tagging only | 1 |
| S4 | PolicyLint and PoliGraph extraction | Authors' code | statement extraction | 1 |
| B3 | Prompted 3B tagger | Qwen2.5-3B-Instruct, zero-shot | tagging only | 1 |

Purpose, retention and children's-data gaps have no existing-tool baseline. For those types, the
comparison is with the LLM systems only, and coverage is reported next to F1.

## Experiment matrix

| System | Main (102) | Ladder (140) | Real flows | Status |
|---|---|---|---|---|
| S1 PoliCheck | ✓ | ✓ | ✓ | Main and ladder done |
| S2 PoliGraph | ✓ | ✓ | ✓ | Main and ladder done |
| B1 | ✓ | — | ✓ | Done (306 runs) |
| B2 | ✓ | ✓ | ✓ | Main and ladder done (3 seeds each) |
| B4 | ✓ | — | — | Seed 0 done; seeds 1–2 running (free-tier quota) |
| full | ✓ | ✓ | ✓ | Main 3 seeds, ladder seed 0 |
| A1–A5 | ✓ | — | — | A1, A2, A3, A5 done; A4 waits for the fine-tuned tagger |

## Run and scoring flow

```mermaid
flowchart LR
    cases[("Benchmark cases")] --> sys["System under test"]
    sys --> runs[("results/runs/{split}/{system}/seed{k}/*.json")]
    keys[("Answer keys")] --> m["match_case<br/>one-to-one on<br/>data type + gap type"]
    runs --> m
    m --> v1["full view<br/>all five gap types"]
    m --> v2["common view<br/>collection + sharing"]
    v2 --> v3["common_native view<br/>vague = consistent"]
    v1 --> met["metrics<br/>P/R/F1 · false alarms<br/>citations · label macro-F1"]
    v2 --> met
    v3 --> met
    met --> bs["cluster bootstrap<br/>re-sample whole policies"]
    bs --> sc[("results/scores/{split}.json")]
```

### Matching

A predicted finding is a **true positive** when its data type and gap type match an answer-key entry
of the same case. Each entry can be matched once, and the level does not need to match. Findings
marked `uncertain` count as not reported and are listed separately.

### Metrics

| Group | Metric | Definition |
|---|---|---|
| Detection | Precision, recall, F1 | Over findings, overall and per gap type and level |
| Detection | Label macro-F1, accuracy | Disclosure labels of collection and sharing flows |
| Safety | False-alarm rate | Share of compliant controls with any reported finding |
| Safety | Unsupported-finding rate | Share of findings whose evidence fails the verifier (target 0) |
| Grounding | Citation correctness | Share of true positives citing an accepted section |
| Wording | Accuracy per rung, paired rung differences (McNemar), confusion matrix | Ladder only |
| Review cost | Selective-accuracy curve, area, R@95 | See below |
| Components | Category macro-F1 (10 OPP-115 categories), tuple F1 | Tagger systems |
| Real flows | Agreement with human labels, Cohen's κ | Real-flow sample |
| Cost | Tokens, GPU or CPU time per case | All systems |

### Fair comparison

1. Tools are scored on the gap types they support (the common subset); LLM systems on both the common
   subset and the full benchmark.
2. PoliCheck and PoliGraph count a vague disclosure as consistent, while our keys count it as a gap
   (DPDP Rule 3 asks for "an itemised description" of the data). Tool labels therefore convert one to
   one (incorrect/ambiguous → explicit, vague → vague, omitted → omission, clear → no gap), and every
   comparison is also reported under their native reading (`common_native`).
3. Tool findings take citations from the fixed gap-to-section table; citation correctness is reported
   for LLM systems only.
4. Mappings and rules are frozen before test runs, and no system is tuned on evaluation cases.
5. Coverage (the share of gap types a system can detect) is reported next to F1.

### Statistics

- **Seeds:** 3 for the headline LLM systems (B1, B2, B4, full), 1 for the ablations; the deterministic
  tools run once.
- **Point estimates:** the mean over seeds.
- **Intervals:** 95% cluster-bootstrap intervals on seed 0, re-sampling whole policies, 1,000 times. Cases built from the same policy share its text, so
  re-sampling single cases would give intervals that are too narrow.
- **Paired comparisons:** they use the same re-samples for both systems.

## Selective accuracy

**Status:** planned (SPEC-07). This measures how much human review each system needs before the rest
of its output can be trusted.

```mermaid
flowchart TD
    a["Three seeds of a system on a split"] --> b["Per flow: majority label<br/>confidence = share of seeds agreeing<br/>token probability breaks ties"]
    b --> c["Sort flows by confidence<br/>lowest first"]
    c --> d["Simulated reviewer corrects the<br/>first k% (takes the gold label)"]
    d --> e["Accuracy of the flows<br/>not reviewed"]
    e --> f["Curve over k = 0 to 100%"]
    f --> g["Report: area under the curve · R@95<br/>review needed to match the best tool"]
```

- **R@95:** the smallest share of flows a human must review for the rest to be 95% accurate.
- **Unit:** the flow, not the finding, so missed gaps (a gap labelled clear) can also be caught by
  review.
- **Tools:** they give no confidence, so each appears as a single point at 0% review.
- **On the ladder:** we also test whether confidence drops from the explicit rung to the vague rung.

## Research questions and hypotheses

| ID | Question / hypothesis | Evidence |
|---|---|---|
| RQ1 | Does DPDP-Audit find more planted gaps with fewer false alarms than PoliCheck, PoliGraph and single-pass review by the same model? | Main benchmark, all views |
| RQ2 | When only one sentence changes, how does each system's verdict on the same flow change? | Ladder |
| RQ3 | How much human review does each system need to reach 95% accuracy, and does confidence fall as wording gets vaguer? | Selective accuracy |
| RQ4 | How much error comes from reading the policy vs legal reasoning, and how close is the fine-tuned 3B tagger to PrivBERT? | A4, A5, tagger metrics |
| H1 | On collection and sharing, the full system beats PoliCheck and PoliGraph on F1 and label macro-F1 | common views |
| H2 | On the full benchmark, the full system beats B1 and B2 on F1, most on vague and omission | full view per level |
| H3 | The verifier lowers the false-alarm rate (full vs A1) while losing at most 5 points of recall | safety, detection |
| H4 | Every system is less accurate on the vague rung than on the explicit rung | ladder, paired |
| H5 | The full system needs less review than B2 to reach 95%, and its confidence is lower on vague rungs | selective accuracy |
| H6 | The fine-tuned tagger beats B3, comes within 5 points of PrivBERT, and closes at least half the A4–A5 gap | tagger metrics, A4/A5 |

**Falsifiable claim.** DPDP-Audit beats PoliCheck and PoliGraph on the gap types they support, and B2
on the full benchmark, in F1 and false-alarm rate. The claim is falsified if any of these holds:
- the F1 gain is below 5 points;
- the 95% interval of the gain includes 0;
- the false-alarm rate is significantly higher (its interval lies above 0).
