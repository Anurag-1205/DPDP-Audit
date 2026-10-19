"""Gap types, difficulty levels, disclosure labels and the fixed gap-to-section table."""
from __future__ import annotations

import csv
from functools import lru_cache

from .paths import DATA

GAP_TYPES = [
    "undisclosed_collection",
    "undisclosed_sharing",
    "purpose_mismatch",
    "retention_mismatch",
    "childrens_data",
]
# Gap types PoliCheck / PoliGraph model (the "common subset").
FLOW_GAP_TYPES = ["undisclosed_collection", "undisclosed_sharing"]

LEVELS = ["explicit", "vague", "omission"]
LABELS = ["clear", "vague", "omitted", "incorrect"]  # PoliCheck-style disclosure labels

# level of a gap  <->  disclosure label of the flow
LEVEL_TO_LABEL = {"explicit": "incorrect", "vague": "vague", "omission": "omitted", None: "clear"}
LABEL_TO_LEVEL = {v: k for k, v in LEVEL_TO_LABEL.items()}
LABEL_TO_LEVEL["ambiguous"] = "explicit"  # PoliCheck's contradictory-policy label


@lru_cache(maxsize=1)
def gap_table() -> dict[str, dict]:
    with (DATA / "dpdp" / "gap_to_section.csv").open() as f:
        rows = list(csv.DictReader(f))
    return {
        r["gap_type"]: {
            "description": r["description"],
            "gold": r["gold_sections"].split(";"),
            "accepted": r["accepted_sections"].split(";"),
        }
        for r in rows
    }


def citation_ok(gap_type: str, cited: list[str]) -> bool:
    """True if at least one cited unit is accepted for this gap type."""
    accepted = set(gap_table()[gap_type]["accepted"])
    return any(c.strip() in accepted for c in cited)
