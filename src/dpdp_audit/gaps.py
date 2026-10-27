"""Gap types, difficulty levels, disclosure labels and the fixed gap-to-section table."""
from __future__ import annotations

import csv
import re
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


FOREIGN_LAW = re.compile(r"gdpr|article|ccpa|coppa|hipaa|cpra|ferpa", re.I)


def normalise_section(s: str) -> str | None:
    """Canonical DPDP unit name, or None if it is not a DPDP Act/Rules reference.

    "Section 8(7)" -> "Sec. 8(7)", "Sec 6 (1)(d)" -> "Sec. 6(1)", "Rule 3(2)" -> "Rule 3";
    "Article 6 GDPR" -> None.
    """
    s = str(s).strip()
    if not s or FOREIGN_LAW.search(s):
        return None
    if "schedule" in s.lower():
        return "Third Schedule" if "third" in s.lower() else None
    m = re.match(r"(?:sec(?:tion)?s?\.?|s\.)\s*(\d+)\s*(?:\(\s*(\d+)\s*\))?", s, re.I)
    if m:
        return f"Sec. {m.group(1)}({m.group(2)})" if m.group(2) else f"Sec. {m.group(1)}"
    m = re.match(r"rules?\s*(\d+)", s, re.I)
    if m:
        return f"Rule {m.group(1)}"
    return None


def citation_ok(gap_type: str, cited: list[str]) -> bool:
    """True if at least one cited unit is accepted for this gap type.

    Citations are normalised first, so "Rule 3(2)" counts as Rule 3 and "Section 5(1)" as Sec. 5(1).
    """
    accepted = set(gap_table()[gap_type]["accepted"])
    return any((normalise_section(c) or str(c).strip()) in accepted for c in cited)
