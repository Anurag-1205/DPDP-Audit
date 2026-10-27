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


def get_config(name: str) -> Config:
    if name not in CONFIGS:
        raise ValueError(f"unknown pipeline configuration {name!r}; choose from {sorted(CONFIGS)}")
    return CONFIGS[name]
