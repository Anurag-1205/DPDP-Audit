# DPDP-Audit pipeline

**Status:** v1 implemented (SPEC-04) in `src/dpdp_audit/pipeline/`, with unit tests on a scripted fake
LLM (`tests/test_pipeline.py`). Runs: `scripts/run_pipeline.py` locally or `kaggle/pipeline/` on Kaggle.

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

## Implementation

| Stage | Module | Notes |
|---|---|---|
| 1 Tagger | `pipeline/claims.py`, `scripts/tag_policies.py` | Taggers run offline, once per distinct paragraph (keyed by a hash of its text), and write `results/tagger/claims/<tagger>.jsonl`. `oracle` is built from the OPP-115 annotations. |
| 2 Tools | `baselines.app_facts`, `tools/` | The same parsed facts B2 receives |
| 3 Mismatch finder | `pipeline/finder.py` | Deterministic. A flow is a candidate unless the claims cover it explicitly and specifically; each candidate carries a suggested level, a reason and linked paragraph numbers |
| 4 Reviewers | `pipeline/reviewers.py`, `pipeline/decide.py`, `pipeline/vocab.py` | One LLM agent per reviewer with candidates; it copies the policy sentences that disclose, deny or generically cover each flow, and `decide.py` derives the decision from the quotes that are in the policy. Tool loop of at most 3 calls; prompts fill a 30,000-character budget (≈ 8.5k tokens) so a reply always fits the 12,288-token context |
| 5 Aggregator | `pipeline/aggregator.py` | Normalises citations, drops a purpose finding when the same flow has a notice gap, merges findings per (data type, gap type); an undecided candidate keeps the finder's label |
| 6 Verifier | `pipeline/verifier.py` | Deterministic quote and section checks, then one LLM support check per case (temperature 0); a reply that cannot be parsed leaves the findings as they are (logged) |
| Configurations | `pipeline/config.py` | `full`, `A1`–`A5`, `full_finetuned` |

Every run stores a `trace`: paragraphs and claims, candidates, reviewer decisions, tool calls with their
validity, undecided candidates, LLM calls and seconds. Dropped findings are kept under `dropped` with
the reason.

**What the oracle ablation measures.** The answer keys are computed from the same annotations the
oracle tagger reads, and the finder applies the same notion of coverage. With oracle claims the
finder's candidates reproduce the keys (checked on the dev split: 35 of 35 gold gaps found at the right
level, no candidate on a control). A5 is therefore an upper bound on what the reviewers keep, not an
independent measurement; the A4–A5 gap is the cost of reading errors.

**Development split.** Prompts were developed on `data/benchmark/dev/` (33 cases, 11 controls, from
12 *training* policies; `scripts/generate_cases.py --split dev --policy-set train --n-policies 12`),
never on the evaluation cases. Four iterations, seed 0, prompted tagger (runs kept under
`results/runs/dev/full_dev1…3` and `full`):

| Run | Change | F1 | False-alarm rate |
|---|---|---|---|
| dev1 | first version: reviewers decide `is_gap` | 0.195 | 0.64 |
| dev2 | glossary of OPP-115 data types and purposes; everyday words in searches; near-verbatim quotes snapped | 0.241 | 0.91 |
| dev3 | reviewers extract quotes, `pipeline/decide.py` derives the decision; finder's suggested level hidden | 0.372 | 0.36 |
| dev4 | a positive quote naming the data type counts as disclosure in any slot | 0.361 | 0.36 |

The prompts and rules were frozen after dev4 (26 Oct) and only then run on the main benchmark and
the ladder. What dev showed: a 7B reviewer asked "is this a gap?" agrees with almost every
candidate; asked to copy the sentence that discloses the flow, it is far more reliable, and a
deterministic rule over verified quotes makes the decision. Purpose mismatches stayed undetected
on dev (0 of 8).

### Decision rules (`pipeline/decide.py`)

| Gap type | No gap | explicit | vague | omission |
|---|---|---|---|---|
| Collection / sharing | a verified positive quote naming the data type (sharing: and the SDK or its company) | a verified denial naming the data type, with no positive quote | a verified generic quote, or a sharing quote without the recipient | nothing verified |
| Purpose | a verified quote giving the app's purpose for the data type | — | the data type appears only without a purpose (verified quote) | otherwise |
| Retention | the policy keeps data indefinitely | a stated period or limit | retention mentioned without a period | nothing about retention |
| Children | — (always a gap for a child-directed app sending data to an ad/tracking SDK) | a verified children statement | — | no children statement |

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
