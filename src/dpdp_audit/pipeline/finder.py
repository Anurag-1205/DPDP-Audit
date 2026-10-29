"""Stage 3: the mismatch finder. Claims x app facts -> candidate gaps (no LLM).

The finder is recall-oriented: a flow becomes a candidate unless the tagger's claims
show it explicitly and specifically covered. Each candidate carries the finder's reading
(a suggested level and the paragraphs that led to it); the reviewers make the decision.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..opp115 import GENERIC_TYPES
from ..tools import lookup_sdk, search_policy
from .claims import AUDIENCES, FIRST_PARTY, RETENTION, THIRD_PARTY_SHARING
from .vocab import PURPOSES, data_words

GENERIC_PURPOSES = {"unspecified", "other", ""}
LIMITED_RETENTION = {"Stated Period", "Limited"}
GAP_REVIEWER = {
    "undisclosed_collection": "notice",
    "undisclosed_sharing": "notice",
    "purpose_mismatch": "purpose",
    "retention_mismatch": "retention",
    "childrens_data": "children",
}


@dataclass
class Paragraph:
    index: int
    text: str
    claims: list[dict] = field(default_factory=list)
    tagged: bool = True


def _low(s: str) -> str:
    return (s or "").strip().lower()


def names_recipient(claim: dict, recipient: str) -> bool:
    """The claim's recipient words name the SDK or its vendor."""
    sdk = lookup_sdk(recipient)
    if sdk is None:
        return False
    text = _low(claim.get("third_party_text"))
    return bool(text) and (_low(sdk["vendor"]) in text or _low(sdk["name"]) in text)


def _hits(paras: list[Paragraph], pred) -> list[tuple[int, dict]]:
    return [(p.index, c) for p in paras for c in p.claims if pred(c)]


def _query(flow: dict, practice: str) -> str:
    rec, words = flow["recipient"], data_words(flow["data_type"])
    if rec == "first_party":
        return f"we collect {flow['data_type']} {words} {practice} {flow.get('purpose', '')}"
    sdk = lookup_sdk(rec)
    who = f"{sdk['vendor']} {sdk['name']}" if sdk else rec
    return f"share {flow['data_type']} {words} with third parties {who} {practice} {flow.get('purpose', '')}"


def _purpose_query(flow: dict) -> str:
    """v2: a purpose search in the words policies use ("statistics, research" for Analytics)."""
    purpose = flow.get("purpose", "")
    return f"we use {data_words(flow['data_type'])} information for {purpose} {PURPOSES.get(purpose, '')}"


def find_candidates(paras: list[Paragraph], facts: dict, policy_text: str, purpose_search: bool = False,
                    purpose_always: bool = False) -> list[dict]:
    """Every (flow, gap type) check the claims do not settle as compliant.

    purpose_search (v2): purpose candidates search with the purpose's everyday words, 4 hits.
    purpose_always (v2): a flow whose notice is in doubt also gets a purpose candidate, so its
    purpose is checked when the reviewer finds the notice clear (the aggregator drops the purpose
    finding when the notice gap stands).
    """
    out = []
    child = facts["permissions"]["child_directed"]

    def add(flow, gap_type, level, reason, hits, query):
        linked = sorted({i for i, _ in hits})
        k = 2
        if gap_type == "purpose_mismatch" and purpose_search:
            query, k = _purpose_query(flow), 4
        searched = [r["paragraph"] for r in search_policy(policy_text, query, k=k)]
        out.append({
            "candidate_id": f"c{len(out) + 1}",
            "flow_id": flow["flow_id"], "data_type": flow["data_type"], "recipient": flow["recipient"],
            "purpose": flow.get("purpose", "Unspecified"), "retention": flow.get("retention", "Unspecified"),
            "gap_type": gap_type, "reviewer": GAP_REVIEWER[gap_type], "suggested_level": level,
            "reason": reason, "paragraphs": linked + [i for i in searched if i not in linked],
        })

    for flow in facts["flows"]:
        d, rec, purpose = flow["data_type"], flow["recipient"], _low(flow.get("purpose"))
        if rec == "first_party":
            coll = _hits(paras, lambda c: c["category"] == FIRST_PARTY and c["does"] == "Does"
                         and c["data_type"] == d)
            coll_not = _hits(paras, lambda c: c["category"] == FIRST_PARTY and c["does"] == "Does Not"
                             and c["data_type"] == d)
            generic = _hits(paras, lambda c: c["category"] == FIRST_PARTY and c["does"] == "Does"
                            and c["data_type"] in GENERIC_TYPES)
            q = _query(flow, "collect")
            if not coll:
                if coll_not:
                    add(flow, "undisclosed_collection", "explicit",
                        f"the policy says it does not collect {d}", coll_not, q)
                elif generic:
                    add(flow, "undisclosed_collection", "vague",
                        f"{d} is covered only by generic collection statements", generic, q)
                else:
                    add(flow, "undisclosed_collection", "omission", f"no collection statement mentions {d}",
                        [], q)
                if purpose_always:
                    add(flow, "purpose_mismatch", "omission",
                        f"{d} may be collected; the app uses it for {flow.get('purpose')}", coll_not + generic,
                        _query(flow, "purpose use"))
            else:
                stated = {_low(c["purpose"]) for _, c in coll}
                if purpose not in stated:
                    level = "vague" if stated & GENERIC_PURPOSES else "omission"
                    add(flow, "purpose_mismatch", level,
                        f"{d} is collected for {sorted(stated)}, the app uses it for {flow.get('purpose')}",
                        coll, _query(flow, "purpose use"))
            if flow.get("retention") == "Indefinitely":
                ret = _hits(paras, lambda c: c["category"] == RETENTION
                            and (c["data_type"] == d or c["data_type"] in GENERIC_TYPES))
                periods = {c["retention"] for _, c in ret}
                level = "explicit" if periods & LIMITED_RETENTION else "vague" if periods else "omission"
                add(flow, "retention_mismatch", level,
                    f"the app keeps {d} indefinitely; retention statements: {sorted(periods) or 'none'}",
                    ret, f"retain keep store {d} {data_words(d)} how long delete period")
        else:
            share = _hits(paras, lambda c: c["category"] == THIRD_PARTY_SHARING and c["does"] == "Does"
                          and c["data_type"] == d)
            named = [(i, c) for i, c in share if names_recipient(c, rec)]
            specific = [(i, c) for i, c in named if _low(c["purpose"]) not in GENERIC_PURPOSES]
            share_not = _hits(paras, lambda c: c["category"] == THIRD_PARTY_SHARING and c["does"] == "Does Not"
                              and c["data_type"] == d)
            generic = _hits(paras, lambda c: c["category"] == THIRD_PARTY_SHARING and c["does"] == "Does"
                            and c["data_type"] in GENERIC_TYPES)
            q = _query(flow, "share")
            if not specific:
                if share_not and not share:
                    add(flow, "undisclosed_sharing", "explicit", f"the policy says it does not share {d}",
                        share_not, q)
                elif share or generic:
                    add(flow, "undisclosed_sharing", "vague",
                        f"sharing {d} with {rec} is covered only by unnamed recipients, unspecified purposes "
                        "or generic data", share + generic, q)
                else:
                    add(flow, "undisclosed_sharing", "omission", f"no sharing statement mentions {d}", [], q)
                if purpose_always:
                    add(flow, "purpose_mismatch", "omission",
                        f"{d} may be shared with {rec}; the app uses it for {flow.get('purpose')}",
                        share + generic, _query(flow, "purpose"))
            else:
                stated = {_low(c["purpose"]) for _, c in named}
                if purpose not in stated:
                    level = "vague" if stated & GENERIC_PURPOSES else "omission"
                    add(flow, "purpose_mismatch", level,
                        f"{d} is shared with {rec} for {sorted(stated)}, the app uses it for {flow.get('purpose')}",
                        named, _query(flow, "purpose"))
            sdk = lookup_sdk(rec)
            if child and sdk and sdk["ad_or_tracking"]:
                kids = _hits(paras, lambda c: c["category"] == AUDIENCES and c["audience"] == "Children")
                add(flow, "childrens_data", "explicit" if kids else "omission",
                    f"a child-directed app sends {d} to the {sdk['category']} SDK {sdk['name']}", kids,
                    "children under 13 child")
    return out
