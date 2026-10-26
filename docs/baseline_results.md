# Baseline results: PoliCheck, PoliGraph, B1, B2, PrivBERT, B3

All must and needed baselines have run. The best main baseline reaches F1 0.21 (PoliGraph on
collection and sharing), and every system raises false alarms on 75–97% of compliant controls.
The tagger bar is PrivBERT at 0.779 category macro-F1; the untrained prompted tagger reaches 0.388.

Runs: Kaggle account `nikpatidar333`, 26 October 2026. B1/B2 are the Stage 1 runs
(`docs/stage1_results.md`); they were not re-run.

## Main benchmark (102 cases, 34 controls)

Mean over seeds (B1, B2: 3 seeds; tools: 1 deterministic run). Source: `outputs/scores/main.json`.

| System | F1 (full) | F1 (collection/sharing) | same, vague = consistent | Label macro-F1 | False-alarm rate |
|---|---|---|---|---|---|
| B1 single prompt, raw inputs | 0.182 | 0.183 | 0.246 | 0.177 | 0.971 |
| B2 single prompt, parsed facts + DPDP text | 0.181 | 0.176 | 0.206 | 0.107 | 0.745 |
| S1 PoliCheck | 0.149 | 0.186 | 0.192 | 0.225 | 0.912 |
| S2 PoliGraph | 0.166 | 0.212 | 0.079 | 0.197 | 0.853 |

Citation correctness is not reported for S1/S2: tools get their sections from the fixed
gap-to-section table, so their 1.000 is by construction. F1 (full) is lower for the tools because
they cannot detect purpose, retention or children's-data gaps.

95% policy-level bootstrap intervals (seed 0):

| System | F1 (full) | F1 (collection/sharing) | False-alarm rate |
|---|---|---|---|
| B1 | 0.184 [0.145, 0.224] | 0.190 [0.155, 0.229] | 0.971 [0.912, 1.000] |
| B2 | 0.188 [0.145, 0.233] | 0.195 [0.144, 0.251] | 0.676 [0.529, 0.824] |
| S1 | 0.149 [0.106, 0.201] | 0.186 [0.130, 0.248] | 0.912 [0.794, 1.000] |
| S2 | 0.166 [0.119, 0.218] | 0.212 [0.151, 0.278] | 0.853 [0.735, 0.941] |

B2's seed 0 is one of its better seeds (false-alarm rate 0.68, 0.65, 0.91 over seeds 0–2); the
final report should give intervals over all three seeds.

### Collection/sharing detail

| System | Precision | Recall | Gold-clear flows read as clear / vague / omitted |
|---|---|---|---|
| S1 PoliCheck | 0.113 | 0.542 | 49 / 164 / 32 |
| S2 PoliGraph | 0.130 | 0.562 | 74 / 63 / 117 |

PoliCheck mostly reads clear flows as vague; part of this comes from the lossy data-type mapping
(e.g. Contact → email address). PoliGraph mostly reads them as omitted: its graph misses
statements. The "vague = consistent" reading leaves few gold findings, so S2's 0.079 there rests on
very few cases.

### Tool coverage

- Exported flows: 282 of 433 (65%; 12% exact) — only collection/sharing flows with a PoliCheck data
  type. Unexported flows give the tools no finding.
- PoliCheck: all 282 exported flows matched a result row.
- PoliGraph: 31 of 34 policies parsed; PoliGraph's own crawler check rejected 1582, 642 and 760
  ("Not like a privacy policy"), kept as the tool's native behaviour. 258 of 282 flows matched; their
  flows count as omitted, the same rule as for PoliCheck. PoliGraph found purposes for 74 flows
  (kept in `outputs/runs/main/S2/`, usable for a purpose baseline).
- PurPliance: not run; its public release has only the statement extractor (`docs/existing_tools.md`).

## Tagger (1,140 held-out segments from 35 policies)

Category F1, multi-label over the 10 OPP-115 categories. Training: 2,426 segments from 72 training
policies; 225 segments from 8 further training policies pick the epoch. Source:
`outputs/scores/tagger.json`.

| Category | B3 prompted Qwen2.5-3B | S4 PrivBERT |
|---|---|---|
| First Party Collection/Use | 0.702 | 0.866 |
| Third Party Sharing/Collection | 0.660 | 0.897 |
| User Choice/Control | 0.444 | 0.661 |
| User Access, Edit and Deletion | 0.497 | 0.758 |
| Data Retention | 0.219 | 0.400 |
| Data Security | 0.316 | 0.755 |
| Policy Change | 0.225 | 0.796 |
| Do Not Track | 0.200 | 1.000 |
| International and Specific Audiences | 0.189 | 0.883 |
| Other | 0.423 | 0.778 |
| **Macro-F1** | **0.388** | **0.779** |
| Micro-F1 | 0.512 | 0.808 |

- B3 (zero-shot, greedy) gives no category for 96 of 1,140 segments and 2.0 categories per segment
  against 1.7 in the gold labels.
- PrivBERT (`mukund/privbert`, lr 2e-5, batch 16, 6 epochs fixed in advance) was still improving at
  the last epoch (dev macro-F1 0.398 → 0.795).
- H6 target for the QLoRA tagger: above 0.388 (B3) and at least 0.729 (within 5 points of PrivBERT).

## How to reproduce

| Step | Command |
|---|---|
| Upload code + benchmark and run a tool kernel | `scripts/kaggle_push_tool.sh policheck` (or `poligraph`, `tagger`) |
| Convert tool output | `tool_runs.policheck_outputs` / `tool_runs.poligraph_outputs` → `outputs/runs/main/S1`, `S2` |
| Score main systems | `python scripts/score_runs.py --systems B1 B2 S1 S2` |
| Score taggers | `python scripts/eval_tagger.py --gold outputs/tagger/heldout.jsonl --pred B3=outputs/tagger/B3_pred.jsonl S4=outputs/tagger/S4_pred.jsonl` |

Kaggle notes:
- **PoliCheck** (`kaggle/policheck/`): CPU only, about 28 min. It rebuilds the Docker image as a
  micromamba Python 2.7 environment.
- **PoliGraph** (`kaggle/poligraph/`): about 13 min on CPU, because cupy did not load.
  - It needs a uv-managed Python 3.10, with Kaggle's `UV_*` variables cleared.
  - Install Firefox libraries by their Ubuntu 24.04 names.
  - Pin `lxml==4.9.2`.
  - Patch `html_crawler` to download readability.js without requests-cache, whose serializer fails
    with `NameError: RequestsCookieJar`.
- **Tagger** (`kaggle/tagger/`): one T4, about 11 min.

`scripts/tools/run_poligraph.sh` has two bugs that `kaggle/poligraph/run.py` avoids:
- It names policy folders by package. The flow check looks them up by blake2s of the policy URL,
  so it finds no policy.
- It passes `flows.csv` with its header row. The converter reads it with fixed field names, so
  the header becomes a data row and fails.
