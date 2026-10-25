# DPDP-Audit pipeline

**Status:** planned (SPEC-04). The shared services it uses (app tools, DPDP retrieval, LLM client) are
implemented.

The pipeline takes a privacy policy and an application, and returns findings. Each finding has a gap
type, a level, a verbatim quote from the policy and a DPDP section. A finding without evidence is
never reported. Uncertain findings go to human review.

## End-to-end flow

```mermaid
flowchart TB
    pol["Privacy policy<br/>policy.txt"]
    app["Application<br/>build.gradle · AndroidManifest.xml · dataflows.json"]
    subgraph PIPE["DPDP-Audit pipeline"]
        direction TB
        t1["1 · Clause tagger<br/>QLoRA Qwen2.5-3B<br/>policy paragraphs → structured claims"]
        t2["2 · Tools<br/>parse_deps · parse_perms · lookup_sdk<br/>get_flows · search_policy → app facts"]
        t3["3 · Mismatch finder<br/>claims × facts → candidate gaps<br/>recall-oriented"]
        subgraph REV["4 · Specialist reviewers (agents)"]
            direction LR
            r1["Notice and<br/>consent"]
            r2["Purpose<br/>limitation"]
            r3["Retention"]
            r4["Children's<br/>data"]
        end
        t5["5 · Aggregator<br/>merge duplicates · resolve conflicts"]
        t6["6 · Evidence verifier<br/>quote in inputs · section exists<br/>section supports the finding"]
    end
    rag[("DPDP index<br/>Act + Rules, 153 units")]
    out1["Findings report<br/>gap · level · quote · DPDP section"]
    out2["Human review queue<br/>uncertain findings<br/>low-confidence flows"]
    pol --> t1 --> t3
    app --> t2 --> t3
    t3 --> REV
    rag -. retrieval .-> REV
    t2 -. tool calls .-> REV
    REV --> t5 --> t6
    t6 -->|supported| out1
    t6 -->|uncertain| out2
```

## Stages and data contracts

| # | Stage | Input | Output | Course capability |
|---|---|---|---|---|
| 1 | Clause tagger | Policy paragraphs | Claims: `{paragraph, category, data_type, does, third_party, third_party_text, purpose, retention, audience}` | Fine-tuning |
| 2 | Tools | App folder | Facts: SDKs found, permissions → data types, `child_directed`, flows | Tool calling |
| 3 | Mismatch finder | Claims + facts | Candidates: `{candidate_id, flow_id, data_type, recipient, purpose, retention, gap_type, reason}` | Reasoning |
| 4 | Specialist reviewers | Candidates of their gap types, linked paragraphs, retrieved DPDP units | Decisions: `{candidate_id, is_gap, level, label, sections, evidence, rationale}` | Agents + RAG |
| 5 | Aggregator | All decisions | Findings (one per data type × gap type) + one disclosure label per flow | Agents |
| 6 | Evidence verifier | Findings + policy text | Findings with `supported`, `uncertain`; a confidence per flow | Reasoning |

Reviewer responsibilities:

| Reviewer | Gap types | DPDP focus |
|---|---|---|
| Notice and consent | undisclosed collection, undisclosed sharing | Sec. 5, Sec. 6, Rule 3 |
| Purpose limitation | purpose mismatch | Sec. 5(1), Sec. 6(1) |
| Retention | retention mismatch | Sec. 8(7), Rule 8, Third Schedule |
| Children's data | children's data | Sec. 9, Rule 10 |

Every model call goes through the cached LLM client: Qwen2.5-7B-Instruct served by vLLM on Kaggle, or
Gemini for B4 only. The pipeline and the single-pass baselines B1/B2 use **the same model**.

## Reviewer agent loop

```mermaid
sequenceDiagram
    autonumber
    participant MF as Mismatch finder
    participant RV as Reviewer agent
    participant RG as DPDP index (RAG)
    participant TL as Tools
    participant AG as Aggregator
    MF->>RV: candidates, app facts, linked policy paragraphs
    RV->>RG: retrieve sections for each candidate
    RG-->>RV: top-k DPDP units
    loop up to 3 tool calls
        RV->>TL: {"action": "tool", "tool": "search_policy", "query": "..."}
        TL-->>RV: tool result
    end
    RV->>AG: {"action": "final", "decisions": [...]}
    Note over RV,AG: decision = is_gap, level, label, sections, quoted evidence, rationale
```

Rules for the loop:
- Only `search_policy`, `retrieve_dpdp` and `lookup_sdk` exist.
- Unknown tools return an error message.
- A reply that is not JSON ends the loop with no decisions.
- Tool-call validity is logged for the tool-calling evaluation.

## Evidence verifier

```mermaid
flowchart TD
    f["Aggregated finding"] --> q1{"Quote appears word for word<br/>in the inputs?<br/>empty quote allowed only for omission"}
    q1 -- no --> drop["Drop<br/>unsupported"]
    q1 -- yes --> q2{"At least one cited section<br/>exists in the DPDP units?"}
    q2 -- no --> drop
    q2 -- yes --> q3{"LLM check: does the cited text<br/>support calling this a gap?"}
    q3 -- no --> unc["Keep, mark uncertain<br/>send to human review"]
    q3 -- yes --> keep["Report finding"]
```

Section names are normalised before the check. For example, "Section 8(7)" becomes `Sec. 8(7)`, and
"Article 6 GDPR" is rejected.

## Confidence per flow

Each LLM system runs with seeds 0, 1 and 2. For each flow:
- **label:** the majority label over the three seeds;
- **confidence:** the share of seeds that agree, with the mean token probability of the final answer
  (from vLLM log-probabilities) as a tie-break.

This orders the human-review queue and drives selective accuracy
([evaluation.md](evaluation.md#selective-accuracy)).

## Ablations

Each ablation is a configuration switch, not a copy of the code.

| ID | Change | Question it answers |
|---|---|---|
| full | Fine-tuned tagger, 4 reviewers, aggregator, RAG, verifier | — |
| A1 | Verifier off | How much does evidence gating cut false alarms? |
| A2 | No DPDP retrieval | How much does legal grounding help citations? |
| A3 | One generalist reviewer, no aggregator | Do specialist agents and aggregation help? |
| A4 | Prompted 3B tagger instead of fine-tuned | What does fine-tuning add end to end? |
| A5 | Oracle tagger (gold OPP-115 annotations) | How much error is reading the policy vs legal reasoning? |

The full system uses the prompted tagger until the fine-tuned tagger passes its acceptance criteria
(SPEC-05). The oracle tagger only applies to unmodified OPP-115 policies, so it is not used on the
ladder.
