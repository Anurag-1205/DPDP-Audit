# 1. Project overview

## The problem in one example

A mobile app's privacy policy says:

> "We do not share your location with third parties."

But the app's code includes the Google AdMob SDK and sends the user's location to it for advertising.
The policy and the app disagree. Under India's **Digital Personal Data Protection (DPDP) Act, 2023**,
an app must tell users what personal data it processes and why, and get consent for that purpose. So
this mismatch is a **compliance gap**.

Checking this by hand is slow: someone must read a long policy, list everything the app collects and
where it sends it, and match each mismatch to a section of the Act. The project asks: **how well can
automated systems find these gaps, and what kind of system does it best?**

We report *compliance gaps*, not legal violations. Most DPDP obligations only apply from May 2027, and
deciding what is illegal is a lawyer's job.

## What the proposal promises

The proposal (`Neural_Nexus_Final.pdf`) has two halves:

1. **A controlled benchmark.** Test cases where the right answer is already known: a privacy policy, a
   small app, and an answer key listing every gap. The answer keys are computed by script from expert
   annotations (the OPP-115 corpus), so no LLM and no team member decides what is right.
2. **DPDP-Audit, an evidence-gated agent.** A multi-step LLM pipeline (clause tagger, tools that read
   app files, specialist reviewer agents, an aggregator and an evidence verifier). It only reports a gap
   when it can quote the policy and cite the DPDP section.

It is compared with:
- **Existing tools:** PoliCheck, PoliGraph and PurPliance. These are older, rule-based research tools
  that check app data flows against policies.
- **Single-pass LLM baselines:** one prompt to the same model. B1 gets the raw files; B2 gets the
  same parsed facts and DPDP text the agent gets.
- **Ablations:** the agent with one component removed at a time.

### The two novelties

- **Vagueness ladder.** We take one policy and one app and change only one sentence:
  - **Clear:** the sentence states the sharing exactly.
  - **Explicit:** it contradicts the app ("we do not share...").
  - **Vague:** it is generic ("we may share information with partners").
  - **Deleted:** there is no sentence.

  Because nothing else changes, this shows how much vague wording alone confuses each system.
- **Selective accuracy.** Each system gives a confidence for each data flow, and a human reviews the
  least confident ones first. We measure how much human review a system needs before the rest of its
  output is 95% accurate.

## The team

| Role | Person | Responsible for |
|---|---|---|
| M1 | Anurag Kaushal (`Anurag-1205`) | Data and benchmark |
| M2 | Ishaan Giri (`Ishaan-Giri`) | Tools and existing systems |
| M3 | Naveen Mishra (`mveen3`) | Agent pipeline |
| M4 | Nikhil Patidar (`Nikhil3028`) | Fine-tuning and evaluation |

## The plan and where we are

`plan.md` splits the work into stages:

| Stage | Goal | Status |
|---|---|---|
| 0 | Setup: roles, repo, tools running, model running on Kaggle | **Done** (one item open: the OVRseen data request) |
| 1 | Benchmark + simplest baselines (B1, B2) scored on every case | **Done** |
| 2 | Full agent pipeline, fine-tuned tagger, vagueness ladder | Next |
| 3 | All runs and ablations | — |
| 4 | Selective accuracy, real data, open-source case study | — |
| 5 | Analysis and write-up | — |

What Stage 0 and Stage 1 produced, in one paragraph: 35 held-out OPP-115 policies were turned into
**102 test cases**: 34 compliant apps plus 68 apps with planted gaps, holding 118 known gaps and 433
labelled data flows. PoliCheck runs in Docker. A DPDP search index was built from the official Gazette
text. The single-pass baselines B1 and B2 were run on all 102 cases with Qwen2.5-7B (3 runs each, 612
in total) and scored. The headline result is that a single prompt flags almost every compliant app as
non-compliant: B1's false-alarm rate is 0.97. Details are in [stage1_results.md](stage1_results.md).

Next: [02_concepts.md](02_concepts.md).
