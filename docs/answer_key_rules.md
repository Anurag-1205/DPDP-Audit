# Answer-key rules

Answer keys are computed by `src/dpdp_audit/gold_rules.py` from OPP-115 consolidated annotations
(threshold 0.75). Every flow of an application is checked; nothing depends on what was planted.

| Gap | explicit | vague | omission |
|---|---|---|---|
| Undisclosed collection (first party) | a "Does Not" first-party practice for that data type | only generic data types (Generic personal information / Unspecified / Other) are collected | no first-party practice mentions the type or a generic type |
| Undisclosed sharing (to an SDK) | a "Does Not" sharing practice for that data type, and no positive one | the type is shared only with unnamed parties or for unspecified purposes, or only generic data is shared | no sharing practice mentions the type or a generic type |
| Purpose mismatch | – (no case in the held-out set) | the type is collected only for "Unspecified"/"Other" purposes | the stated purposes for the type do not include the app's purpose |
| Retention mismatch (app keeps data indefinitely) | a "Stated Period" or "Limited" retention practice | only "Unspecified" retention practices | no retention practice |
| Children's data (child-directed app sends data to an ad/tracking SDK) | the policy has a Children audience practice | – | no Children audience practice |

A flow is **clear** (no gap) when a first-party practice names its data type, or a sharing practice
names its data type, names the SDK's vendor (e.g. "Google" for AdMob) and states a specific purpose.
Purpose gaps are only checked on clear flows. The gold citation for each gap type comes from
`data/dpdp/gap_to_section.csv`.

## Decision: generic negative statements are not explicit contradictions

23 of the 35 held-out policies contain a negative sharing statement about generic data, e.g.
"we do not sell your personal information", "except as described in this policy", "for their own
marketing purposes". Read in context these are qualified, so treating them as contradictions would put
wrong answers in the key. Only negative statements that name the data type count as explicit.

Consequence (see `data/benchmark/cell_counts.csv`): explicit and omitted collection/sharing gaps are rare
in OPP-115 (2–3 policies each). Following the plan, cells with fewer than 10 policies keep their true
labels but are reported as exploratory. The vagueness ladder (Stage 2) is planned to supply controlled
explicit and omitted cases for collection and sharing on every held-out policy.
