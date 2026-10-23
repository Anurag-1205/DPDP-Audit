"""Which gap type x level cells each held-out policy can host.

A candidate is a single planted flow whose answer-key level, computed by the
rules in gold_rules, falls in that cell. A policy counts at most once per cell.
"""
from __future__ import annotations

from collections import defaultdict

from . import gold_rules as g
from .opp115 import SPECIFIC_TYPES, Policy

# The recipients used for planted third-party flows
AD_SDK = "admob"
ANALYTICS_SDK = "mixpanel"
CHILD_TRACKING_SDK = "admob"
PLANT_PURPOSE = "Advertising"


def candidates(policy: Policy, cov: g.Coverage | None = None) -> list[dict]:
    """Every single-flow plant the policy supports, with its gold level."""
    cov = cov or g.build_coverage(policy)
    out = []
    for d in SPECIFIC_TYPES:
        if d not in cov.collect:
            lvl = g.collection_level(cov, d)
            out.append({"gap_type": "undisclosed_collection", "level": lvl,
                        "flow": {"data_type": d, "recipient": "first_party",
                                 "purpose": "Basic service/feature", "retention": "Unspecified"}})
        for sdk in (AD_SDK, ANALYTICS_SDK):
            lvl = g.sharing_level(cov, d, sdk)
            if lvl is not None:
                purpose = "Advertising" if sdk == AD_SDK else "Analytics/Research"
                out.append({"gap_type": "undisclosed_sharing", "level": lvl,
                            "flow": {"data_type": d, "recipient": sdk, "purpose": purpose,
                                     "retention": "Unspecified"}})
                break
    for d, purposes in cov.collect.items():
        if PLANT_PURPOSE not in purposes:
            lvl = g.purpose_level(cov, d, "first_party", PLANT_PURPOSE)
            out.append({"gap_type": "purpose_mismatch", "level": lvl,
                        "flow": {"data_type": d, "recipient": "first_party", "purpose": PLANT_PURPOSE,
                                 "retention": "Unspecified"}})
        lvl = g.retention_level(cov, d, "Indefinitely")
        out.append({"gap_type": "retention_mismatch", "level": lvl,
                    "flow": {"data_type": d, "recipient": "first_party",
                             "purpose": sorted(purposes - g.GENERIC_PURPOSES or purposes)[0],
                             "retention": "Indefinitely"}})
    out.append({"gap_type": "childrens_data", "level": g.children_level(cov, True, CHILD_TRACKING_SDK),
                "flow": {"data_type": "IP address and device IDs", "recipient": CHILD_TRACKING_SDK,
                         "purpose": "Advertising", "retention": "Unspecified"},
                "child_directed": True})
    return [c for c in out if c["level"] is not None]


def count_cells(policies: list[Policy]) -> dict[tuple[str, str], list[str]]:
    """(gap_type, level) -> ids of policies that can host a case in that cell."""
    cells = defaultdict(set)
    for pol in policies:
        for c in candidates(pol):
            cells[(c["gap_type"], c["level"])].add(pol.policy_id)
    return {k: sorted(v) for k, v in sorted(cells.items())}
