"""Pipeline configurations: the full system and ablations A1-A5 are switches of one implementation."""
from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class Config:
    name: str = "full"
    tagger: str = "prompted"        # prompted | finetuned | oracle
    verifier: bool = True           # A1 turns the evidence verifier off
    retrieval: bool = True          # A2 removes DPDP retrieval (context and the retrieve_dpdp tool)
    specialists: bool = True        # A3: one generalist reviewer and no aggregator
    max_tool_calls: int = 3
    dpdp_k: int = 3                 # DPDP units retrieved per candidate
    max_paragraphs: int = 8         # linked policy paragraphs shown to a reviewer
    prompt_char_budget: int = 30000  # ~8.5k tokens; the served context is 12,288 tokens
    reviewer_temperature: float = 0.7
    verifier_temperature: float = 0.0
    # v2 switches (developed on the dev splits after the 26 Oct freeze; off in the frozen configs)
    llm_check_gaps: tuple[str, ...] | None = None  # gap types the verifier's LLM check sees (None = all)
    purpose_paragraph: bool = False  # a purpose quote counts if its paragraph names the data type
    purpose_search: bool = False     # purpose searches use the purpose's everyday words, 4 hits
    purpose_always: bool = False     # also check the purpose of flows whose notice is in doubt
    review_batch: int = 0            # max candidates per reviewer call (0 = all in one call)
    retention_check: bool = False    # a retention quote must be about keeping data
    robust_verifier: bool = False    # read the verifier's reply robustly (the *_rv configurations)
    verifier_max_tokens: int = 2048


# Until the fine-tuned tagger passes SPEC-05, "full" uses the prompted tagger (the A4 setting);
# WP-3.1 switches it with full_finetuned.
FULL = Config()
CONFIGS = {
    "full": FULL,
    "full_finetuned": replace(FULL, name="full_finetuned", tagger="finetuned"),
    "A1": replace(FULL, name="A1", verifier=False),
    "A2": replace(FULL, name="A2", retrieval=False),
    "A3": replace(FULL, name="A3", specialists=False),
    "A4": replace(FULL, name="A4", tagger="prompted"),
    "A5": replace(FULL, name="A5", tagger="oracle"),
}

# v2: the LLM check is kept only where the decision rests on reading paraphrase (collection,
# purpose); retention, children's data and sharing are decided by rules over verified quotes.
V2_GATE = replace(FULL, name="v2_gate", llm_check_gaps=("undisclosed_collection", "purpose_mismatch"),
                  purpose_paragraph=True)
V2_READ = replace(V2_GATE, name="v2_read", max_paragraphs=16, purpose_search=True)
V2_PURPOSE = replace(V2_READ, name="v2_purpose", purpose_always=True)
V2_BATCH = replace(V2_READ, name="v2_batch", review_batch=1)
# Chosen on the pooled dev splits (dev + dev2, 102 cases from 34 training policies) and frozen
# on 27 Oct before any v2 run on main or the ladder (docs/pipeline.md#v2). v2_purpose was rejected
# (more false alarms); the retention check fixes a decision-rule bug found in the v2_read runs.
FULL_V2 = replace(V2_BATCH, name="full_v2", retention_check=True)
FULL_V2_FINETUNED = replace(FULL_V2, name="full_v2_finetuned", tagger="finetuned")
# Ablations of v2 against its headline configuration (fine-tuned tagger); A4 on v2 is full_v2.
V2_ABLATIONS = [replace(FULL_V2_FINETUNED, name="A1_v2", verifier=False),
                replace(FULL_V2_FINETUNED, name="A2_v2", retrieval=False),
                replace(FULL_V2_FINETUNED, name="A3_v2", specialists=False),
                replace(FULL_V2_FINETUNED, name="A5_v2", tagger="oracle")]
for _c in (V2_GATE, V2_READ, V2_PURPOSE, V2_BATCH, FULL_V2, FULL_V2_FINETUNED, *V2_ABLATIONS):
    CONFIGS[_c.name] = _c


# *_rv: the same configuration with the robust verifier reader (28 Oct). The frozen reader could
# not read 15-40% of the verifier's replies and then kept every finding unchecked;
# scripts/reverify.py re-runs only the verifier on a configuration's saved findings.
for _name, _c in list(CONFIGS.items()):
    CONFIGS[f"{_name}_rv"] = replace(_c, name=f"{_name}_rv", robust_verifier=True, verifier_max_tokens=4096)


def get_config(name: str) -> Config:
    if name not in CONFIGS:
        raise ValueError(f"unknown pipeline configuration {name!r}; choose from {sorted(CONFIGS)}")
    return CONFIGS[name]
