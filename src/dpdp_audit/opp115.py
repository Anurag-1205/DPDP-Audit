"""Load OPP-115 consolidated annotations and sanitized policy text.

Layout of the release (OPP-115_v1_0.zip):
  OPP-115/sanitized_policies/<policy_uid>_<domain>.html   segments separated by "|||"
  OPP-115/consolidation/threshold-0.75-overlap-similarity/<policy_uid>_<domain>.csv
CSV columns (no header): annotation_id, batch_id, annotator_id, policy_id,
segment_id, category, attributes (JSON), date, policy_url.
"""
from __future__ import annotations

import csv
import html
import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .paths import RAW

OPP_DIR = RAW / "OPP-115"
CONSOLIDATION = "threshold-0.75-overlap-similarity"

# Attribute names used by the generator
DATA_TYPE = "Personal Information Type"
DOES = "Does/Does Not"
THIRD_PARTY = "Third Party Entity"
PURPOSE = "Purpose"
RET_PERIOD = "Retention Period"
AUDIENCE = "Audience Type"

GENERIC_TYPES = {"Generic personal information", "Unspecified", "Other"}
SPECIFIC_TYPES = [
    "Computer information", "Contact", "Cookies and tracking elements", "Demographic", "Financial",
    "Health", "IP address and device IDs", "Location", "Personal identifier", "Social media data",
    "Survey data", "User online activities", "User profile",
]


@dataclass
class Practice:
    policy_id: str
    segment_id: int
    category: str
    attrs: dict[str, str]                       # attribute -> value
    spans: dict[str, str] = field(default_factory=dict)  # attribute -> selected text

    def get(self, name: str, default: str = "") -> str:
        return self.attrs.get(name, default)


@dataclass
class Policy:
    policy_id: str
    name: str
    segments: list[str]
    practices: list[Practice]

    def text(self) -> str:
        return "\n\n".join(self.segments)


def _clean_segment(raw: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", raw, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines() if line.strip())


def policy_files() -> list[Path]:
    return sorted((OPP_DIR / "sanitized_policies").glob("*.html"))


def _uid(path: Path) -> tuple[str, str]:
    uid, _, name = path.stem.partition("_")
    return uid, name


def load_policy(html_path: Path, consolidation: str = CONSOLIDATION) -> Policy:
    uid, name = _uid(html_path)
    segments = [_clean_segment(s) for s in html_path.read_text(encoding="utf-8", errors="replace").split("|||")]
    csv_path = OPP_DIR / "consolidation" / consolidation / f"{html_path.stem}.csv"
    practices = []
    with csv_path.open(encoding="utf-8", errors="replace") as f:
        for row in csv.reader(f):
            if len(row) < 7:
                continue
            attrs, spans = {}, {}
            for key, val in json.loads(row[6]).items():
                if isinstance(val, dict):
                    attrs[key] = val.get("value", "")
                    if val.get("selectedText") and val.get("selectedText") != "null":
                        spans[key] = val["selectedText"]
            practices.append(Practice(uid, int(row[4]), row[5], attrs, spans))
    return Policy(uid, name, segments, practices)


@lru_cache(maxsize=1)
def load_all() -> tuple[Policy, ...]:
    return tuple(load_policy(p) for p in policy_files())
