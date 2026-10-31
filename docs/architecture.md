# Architecture overview

DPDP-Audit is a research system with three parts:

1. A **benchmark builder** that creates test cases with known answers.
2. The **systems under test**: existing tools, single-pass LLM baselines and the DPDP-Audit pipeline.
3. An **evaluation layer** that scores every system on the same cases.

This page shows how the parts fit together. Each part has its own page:

| Page | Covers |
|---|---|
| [benchmark.md](benchmark.md) | Case generation, answer-key rules, data model, vagueness ladder, tool export |
| [pipeline.md](pipeline.md) | The six-stage DPDP-Audit pipeline, reviewer agents, evidence verifier, ablations |
| [evaluation.md](evaluation.md) | Systems under test, experiment matrix, scoring views, statistics, selective accuracy |
| [infrastructure.md](infrastructure.md) | Where everything runs: laptops, Docker, Kaggle GPUs, the PoliGraph workstation, Gemini |

## System context

```mermaid
flowchart LR
    team(["Research team<br/>M1–M4"])
    staff(["Course staff"])
    subgraph SYS["DPDP-Audit research system"]
        direction TB
        bench["Benchmark builder"]
        sut["Systems under test"]
        evalx["Evaluation and reporting"]
        bench --> sut --> evalx
    end
    opp[("OPP-115 corpus<br/>115 annotated policies")]
    dpdp[("DPDP Act 2023 and<br/>DPDP Rules 2025")]
    kaggle["Kaggle<br/>2× T4 GPU sessions"]
    gemini["Google Gemini API"]
    tools["PoliCheck and PoliGraph<br/>authors' released code"]
    gh[("GitHub repository")]
    opp -->|policies and annotations| bench
    dpdp -->|citable sections| sut
    team -->|develop and run| SYS
    SYS -->|LLM inference| kaggle
    SYS -->|B4 requests| gemini
    SYS -->|tool baselines| tools
    SYS <-->|code, data, results| gh
    evalx -->|mid and final reports| staff
```

## Containers and components

Components marked `*` are planned (Stage 2 onwards). Everything else is implemented.

```mermaid
flowchart LR
    subgraph SRC["External sources"]
        direction TB
        opp[("OPP-115<br/>annotated policies")]
        gaz[("DPDP Act and Rules<br/>Gazette PDFs")]
    end
    subgraph BUILD["Builders · src/dpdp_audit"]
        direction TB
        b1["opp115 · split"]
        b2["gold_rules · cells"]
        b3["generator · ladder*"]
        b4["dpdp_text"]
    end
    subgraph DATA["Versioned data · data/"]
        direction TB
        d1[("benchmark/<br/>cases, answer keys")]
        d2[("dpdp/<br/>153 units, citation table")]
        d3[("tools/<br/>SDK table, mappings")]
    end
    subgraph SUT["Systems under test"]
        direction TB
        s1["S1 PoliCheck · S2 PoliGraph<br/>export + adapters"]
        s2["B1 · B2 · B4<br/>single-pass baselines"]
        s3["DPDP-Audit pipeline*<br/>full · A1–A5"]
    end
    subgraph SVC["Shared services"]
        direction TB
        v1["llm<br/>Gemini and vLLM client, cache"]
        v2["retrieval<br/>bge-small + FAISS"]
        v3["tools<br/>app readers, policy search"]
    end
    subgraph EVAL["Evaluation · results/"]
        direction TB
        e1[("runs/")] --> e2["score · score_runs"] --> e3[("scores/")]
    end
    opp --> b1 --> b2 --> b3 --> d1
    gaz --> b4 --> d2
    d1 --> SUT
    d3 --> s1
    s2 --> SVC
    s3 --> SVC
    d2 --> v2
    SUT --> e1
```

## Component status

| Component | Module(s) | Status |
|---|---|---|
| OPP-115 loader, policy split | `opp115.py`, `split.py` | Implemented |
| DPDP units, gap-to-section table | `dpdp_text.py`, `gaps.py` | Implemented |
| DPDP retrieval index | `retrieval.py` | Implemented |
| App readers and policy search | `tools/` | Implemented |
| Answer-key rules, cell counts, case generator | `gold_rules.py`, `cells.py`, `generator.py` | Implemented |
| PoliCheck export and adapter | `export_policheck.py`, `tool_runs.py` | Implemented |
| PoliGraph adapter | `scripts/tools/run_poligraph.sh`, `kaggle/poligraph/` | Run on main and the ladder |
| LLM client | `llm.py` | Implemented |
| Single-pass baselines B1, B2, B4 | `baselines.py` | Run (3 seeds each on main; B2 also on the ladder) |
| Scorer | `score.py`, `scripts/score_runs.py` | Implemented |
| DPDP-Audit pipeline and ablations | `pipeline/`, `scripts/run_pipeline.py`, `scripts/reverify.py` | v1 (frozen) and v2 run on main and the ladder; ablations on both (SPEC-04) |
| Clause tagger training and evaluation | `tagger_data.py`, `tagger_eval.py`, `scripts/train_tagger.py` | QLoRA tagger trained and evaluated; S4 extraction comparison done (`s4.py`) (SPEC-05) |
| Vagueness ladder | `ladder.py` | Built, checked by two members and scored (SPEC-06) |
| Selective accuracy | `selective.py` | Planned (SPEC-07) |

## Design principles

1. **Known answers.** Answer keys come from fixed rules over expert annotations, never from an LLM
   ([benchmark.md](benchmark.md#answer-key-rules)).
2. **Same information for every LLM system.** B2 receives exactly the facts and DPDP text the pipeline
   receives, so a gain over B2 comes from the design, not from extra input.
3. **Evidence gating.** The pipeline reports a gap only with a verbatim quote (none for an omission,
   where the policy has nothing to quote) and an existing DPDP section.
4. **Fair tool comparison.** Tools are scored on the gap types they support, under both our reading
   and theirs ([evaluation.md](evaluation.md#fair-comparison)).
5. **Reproducibility.** Fixed seeds, frozen mappings, a cached LLM client, byte-identical regeneration,
   and versioned results ([developer-guide.md](developer-guide.md#conventions)).

## Repository layout

```
DPDP-Audit/
├── README.md · LICENSE · plan.md · specs.md · pyproject.toml · requirements.txt · .env.example
├── src/dpdp_audit/        library code (see the developer guide for each module)
├── scripts/               command-line entry points; scripts/tools/ wraps PoliCheck and PoliGraph
├── kaggle/b1b2/           unattended GPU job (Qwen on vLLM) for the LLM systems
├── notebooks/             interactive Kaggle notebook (same configuration)
├── tests/                 pytest suite and fixtures
├── data/                  versioned inputs: benchmark, DPDP units, mappings, split
├── results/               versioned results: runs, scores, tool outputs, model checks
├── outputs/               local scratch (ignored): caches, logs, Kaggle staging
└── docs/                  proposal (PDF + summary), architecture, guides, report
```
