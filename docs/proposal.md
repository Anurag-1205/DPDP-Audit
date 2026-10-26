# Project proposal

[`Neural_Nexus_Final.pdf`](Neural_Nexus_Final.pdf) is the submitted proposal: *DPDP-Audit: An
Evidence-Gated Agent for Checking App Privacy Compliance under India's DPDP Act* (Anurag Kaushal,
Ishaan Giri, Naveen Mishra, Nikhil Patidar).

## Summary

- **Problem:** privacy policies often contradict what an application collects and shares.
  Single-pass LLM review misses subtle gaps and over-flags; rule-based checkers miss what their
  patterns do not cover.
- **Approach:** a multi-stage, evidence-gated agent with five parts:
  - a fine-tuned clause tagger;
  - tool-based app parsing;
  - specialist reviewers with DPDP retrieval;
  - an aggregator;
  - an evidence verifier.
- **Benchmark:** OPP-115-based applications with answer keys produced by script from expert
  annotations, plus a vagueness ladder, a real-flow sample and an open-source case study.
- **Novelty:** two evaluation methods:
  - the **vagueness ladder**, which isolates the effect of wording by changing one sentence;
  - **selective accuracy**, which measures how much human review a system needs to reach 95%
    accuracy.
- **Evaluation:** F1, false-alarm rate and disclosure-label accuracy against existing flow-to-policy
  tools, single-pass LLM review and per-component baselines, split by difficulty, with an ablation for
  every component.

## Changes since the proposal

The PDF is kept unchanged as submitted. The current specification is [`specs.md`](../specs.md) and the
current schedule is [`plan.md`](../plan.md). Differences:

| Topic | Proposal | Current | Reference |
|---|---|---|---|
| End-to-end tool baselines | S1–S3 | S1 PoliCheck and S2 PoliGraph | [evaluation.md](evaluation.md#systems-under-test) |
| Component baseline IDs | S4 PrivBERT, S5 PolicyLint/PoliGraph extraction | S3 PrivBERT, S4 PolicyLint/PoliGraph extraction | [evaluation.md](evaluation.md#systems-under-test) |
| B4 model | Gemini 3.5 Flash | `gemini-3-flash-preview` (3.5 not available to our key) | [infrastructure.md](infrastructure.md#deployment-view) |
| PoliGraph variant | PoliGrapher-LM if released | Released NLP version (the LLM variant is not in the repository) | [infrastructure.md](infrastructure.md) |
| Benchmark size | about 105 cases | 102 cases (one policy has no clearly disclosed flow for a control) | [benchmark.md](benchmark.md) |
| Rare difficulty cells | merged when under 10 | kept with true labels, reported as exploratory; covered by the ladder | [benchmark.md](benchmark.md#generic-negative-statements) |
| LLM serving | vLLM on Kaggle | vLLM 0.10.2, V0 engine + xFormers on 2× T4 | [infrastructure.md](infrastructure.md#why-vllm-0102) |
| Timeline | five relative weeks | dated plan: mid-submission 30 Oct 2026, final 15 Nov 2026 | [plan.md](../plan.md) |
