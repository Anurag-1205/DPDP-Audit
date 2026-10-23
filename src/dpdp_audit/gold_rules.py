"""Scripted answer keys: fixed rules over OPP-115 annotation values.

For each data flow of an application, the rules decide its disclosure label and
any compliance gap, using only the policy's expert annotations (Table 4 of the
proposal):

  explicit  a specific claim the app contradicts ("Does Not", a stated
            retention period, "not for children")
  vague     covered only by generic values (Generic personal information,
            Unnamed third party, Unspecified purpose or retention)
  omission  no annotation covers the data type for that practice
  clear     explicitly and specifically covered (no gap)

No LLM and no human judgement is involved.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .gaps import LEVEL_TO_LABEL, gap_table
from .opp115 import (AUDIENCE, DATA_TYPE, DOES, GENERIC_TYPES, PURPOSE, RET_PERIOD, THIRD_PARTY,
                     Policy)
from .tools.sdk import lookup_sdk

FIRST_PARTY = "First Party Collection/Use"
THIRD_PARTY_SHARING = "Third Party Sharing/Collection"
RETENTION = "Data Retention"
AUDIENCES = "International and Specific Audiences"

SPECIFIC_ENTITIES = {"Named third party", "Other part of company/affiliate"}
GENERIC_PURPOSES = {"Unspecified", "Other", ""}
LIMITED_RETENTION = {"Stated Period", "Limited"}


@dataclass
class Coverage:
    """What one policy's annotations say, indexed for the rules."""
    collect: dict[str, set[str]] = field(default_factory=dict)       # D -> stated purposes
    collect_generic: set[str] = field(default_factory=set)           # purposes of generic-type collection
    collect_not: set[str] = field(default_factory=set)               # D with a "Does Not" collection
    share: dict[str, list[dict]] = field(default_factory=dict)       # D -> [{entity, span, purpose}]
    share_generic: list[dict] = field(default_factory=list)
    share_not: set[str] = field(default_factory=set)
    retention: dict[str, set[str]] = field(default_factory=dict)     # D or "*" -> periods
    children_claim: bool = False                                     # policy addresses children

    def segments_for(self, policy: Policy, category: str, data_type: str) -> list[int]:
        return sorted({p.segment_id for p in policy.practices
                       if p.category == category and p.get(DATA_TYPE) == data_type})


def build_coverage(policy: Policy) -> Coverage:
    cov = Coverage()
    for p in policy.practices:
        d, does, purpose = p.get(DATA_TYPE), p.get(DOES, "Does"), p.get(PURPOSE)
        if p.category == FIRST_PARTY:
            if does == "Does Not":
                if d and d not in GENERIC_TYPES:
                    cov.collect_not.add(d)
            elif d in GENERIC_TYPES:
                cov.collect_generic.add(purpose)
            elif d:
                cov.collect.setdefault(d, set()).add(purpose)
        elif p.category == THIRD_PARTY_SHARING:
            entry = {"entity": p.get(THIRD_PARTY), "span": p.spans.get(THIRD_PARTY, ""), "purpose": purpose}
            if does == "Does Not":
                if d and d not in GENERIC_TYPES:
                    cov.share_not.add(d)
            elif d in GENERIC_TYPES:
                cov.share_generic.append(entry)
            elif d:
                cov.share.setdefault(d, []).append(entry)
        elif p.category == RETENTION:
            key = "*" if (not d or d in GENERIC_TYPES) else d
            cov.retention.setdefault(key, set()).add(p.get(RET_PERIOD, "Unspecified"))
        elif p.category == AUDIENCES and p.get(AUDIENCE) == "Children":
            cov.children_claim = True
    return cov


def _names_recipient(entry: dict, recipient: str) -> bool:
    """A named third party whose annotated text names the SDK or its vendor."""
    if entry["entity"] not in SPECIFIC_ENTITIES:
        return False
    sdk = lookup_sdk(recipient)
    if sdk is None:
        return False
    span = entry["span"].lower()
    return sdk["vendor"].lower() in span or sdk["name"].lower() in span


# --------------------------------------------------------------- per flow
def collection_level(cov: Coverage, d: str) -> str | None:
    """Disclosure level of first-party collection of data type d (None = clear)."""
    if d in cov.collect:
        return None
    if d in cov.collect_not:
        return "explicit"
    if cov.collect_generic:
        return "vague"
    return "omission"


def sharing_level(cov: Coverage, d: str, recipient: str) -> str | None:
    """Disclosure level of sending data type d to a third-party recipient."""
    entries = cov.share.get(d, [])
    if any(_names_recipient(e, recipient) and e["purpose"] not in GENERIC_PURPOSES for e in entries):
        return None
    if d in cov.share_not and not entries:
        return "explicit"
    if entries or cov.share_generic:
        return "vague"
    return "omission"


def purpose_level(cov: Coverage, d: str, recipient: str, purpose: str) -> str | None:
    """Gap level for using d for `purpose` (only checked when the flow itself is clear)."""
    if recipient == "first_party":
        stated = set(cov.collect.get(d, set()))
    else:
        stated = {e["purpose"] for e in cov.share.get(d, []) if _names_recipient(e, recipient)}
    if purpose in stated:
        return None
    if stated & GENERIC_PURPOSES:
        return "vague"
    return "omission"


def retention_level(cov: Coverage, d: str, retention: str) -> str | None:
    if retention != "Indefinitely":
        return None
    periods = cov.retention.get(d, set()) | cov.retention.get("*", set())
    if periods & LIMITED_RETENTION:
        return "explicit"
    if periods:
        return "vague"
    return "omission"


def children_level(cov: Coverage, child_directed: bool, recipient: str) -> str | None:
    if not child_directed or recipient == "first_party":
        return None
    sdk = lookup_sdk(recipient)
    if sdk is None or not sdk["ad_or_tracking"]:
        return None
    return "explicit" if cov.children_claim else "omission"


def answer_key(case_id: str, policy: Policy, cov: Coverage, flows: list[dict], child_directed: bool,
               kind: str) -> dict:
    """Apply every rule to every flow and return the case's answer key."""
    findings, labels, flow_gap_types = [], {}, {}
    for f in flows:
        d, rec, fid = f["data_type"], f["recipient"], f["flow_id"]
        if rec == "first_party":
            gap_type, level = "undisclosed_collection", collection_level(cov, d)
        else:
            gap_type, level = "undisclosed_sharing", sharing_level(cov, d, rec)
        labels[fid] = LEVEL_TO_LABEL[level]
        flow_gap_types[fid] = gap_type
        flow_findings = []
        if level is not None:
            flow_findings.append((gap_type, level))
        else:
            p = purpose_level(cov, d, rec, f.get("purpose", "Unspecified"))
            if p is not None:
                flow_findings.append(("purpose_mismatch", p))
        if rec == "first_party":
            r = retention_level(cov, d, f.get("retention", "Unspecified"))
            if r is not None:
                flow_findings.append(("retention_mismatch", r))
        c = children_level(cov, child_directed, rec)
        if c is not None:
            flow_findings.append(("childrens_data", c))
        for gt, lvl in flow_findings:
            findings.append({"flow_id": fid, "data_type": d, "gap_type": gt, "level": lvl,
                             "sections": gap_table()[gt]["gold"]})
            if gt != gap_type:
                flow_gap_types[fid] = gt if level is None else flow_gap_types[fid]
    return {"case_id": case_id, "policy_id": policy.policy_id, "kind": kind,
            "findings": findings, "flow_labels": labels, "flow_gap_types": flow_gap_types}
