# Documentation

## Reading paths

| If you are… | Read, in order |
|---|---|
| New to the project | [getting-started.md](getting-started.md) → [architecture.md](architecture.md) → [stage-1-report.md](stage-1-report.md) |
| Contributing code | [developer-guide.md](developer-guide.md) → the page for your area below → your spec in [`specs.md`](../specs.md) |
| Re-running results | [reproduction.md](reproduction.md) → [troubleshooting.md](troubleshooting.md) |
| Reviewing the project | [proposal.md](proposal.md) → [`plan.md`](../plan.md) → [`specs.md`](../specs.md) → [stage-1-report.md](stage-1-report.md) |

## Contents

| Area | Document | Purpose |
|---|---|---|
| Proposal | [Neural_Nexus_Final.pdf](Neural_Nexus_Final.pdf) | Submitted proposal (unchanged) |
| | [proposal.md](proposal.md) | Summary and changes since submission |
| Architecture | [architecture.md](architecture.md) | System context, components and status, design principles, repository layout |
| | [benchmark.md](benchmark.md) | Case generation, answer-key rules, design notes, data model, vagueness ladder, tool export |
| | [pipeline.md](pipeline.md) | DPDP-Audit pipeline, reviewer agents, evidence verifier, confidence, ablations |
| | [evaluation.md](evaluation.md) | Systems under test, experiment matrix, metrics, fair comparison, statistics, selective accuracy, RQs |
| | [infrastructure.md](infrastructure.md) | Deployment, Kaggle job, tool adapters, compute budget, configuration |
| Guides | [getting-started.md](getting-started.md) | The problem and every concept, from zero |
| | [developer-guide.md](developer-guide.md) | Setup, modules, data formats, conventions, workflow |
| | [reproduction.md](reproduction.md) | Commands to regenerate every result |
| | [troubleshooting.md](troubleshooting.md) | Known problems and fixes |
| Reports | [stage-1-report.md](stage-1-report.md) | Stage 0–1 status and baseline results |
| | [baseline-report.md](baseline-report.md) | PoliCheck, PoliGraph, PrivBERT and B3 on the full benchmark |
| Plan and specs | [`plan.md`](../plan.md) | Milestones, schedule, work breakdown, RACI, compute, risks |
| | [`specs.md`](../specs.md) | Specifications SPEC-01 … SPEC-09 with acceptance criteria |

## Conventions

- **Diagrams:** written in Mermaid inside the Markdown, so they render on GitHub and stay
  version-controlled.
- **Status labels:** **Done** (acceptance criteria met with evidence) · **In progress** · **Planned**.
- **Identifiers:** systems S1–S4, B1–B4, `full`, A1–A5 · specs SPEC-NN · questions RQ1–RQ4 ·
  hypotheses H1–H6 · risks R-NN · work packages WP-N.N.
- **Updates:** design changes update the architecture pages; scope or schedule changes update
  `specs.md` or `plan.md`; new results get a report page.
