"""Stage 5: merge reviewer decisions into findings and one disclosure label per flow."""
from __future__ import annotations

from ..gaps import FLOW_GAP_TYPES, LEVEL_TO_LABEL, LEVELS, normalise_section


def _truthy(v) -> bool:
    if isinstance(v, str):
        return v.strip().lower() in ("true", "yes", "1")
    return bool(v)


def aggregate(flows: list[dict], candidates: list[dict], reviews: list[dict], merge: bool = True) -> dict:
    """Return {"findings", "flow_labels", "undecided", "unknown_decisions"}.

    merge=False (ablation A3) keeps every accepted decision as its own finding and skips the
    cross-reviewer consistency rule.
    """
    by_id = {c["candidate_id"]: c for c in candidates}
    decided, unknown = {}, []
    prob = {}
    for r in reviews:
        for d in r["decisions"]:
            cid = str(d.get("candidate_id", ""))
            if cid in by_id and cid not in decided:
                decided[cid] = d
                prob[cid] = r.get("token_prob")
            elif cid not in by_id:
                unknown.append(cid)

    labels = {f["flow_id"]: {"label": "clear", "confidence": None} for f in flows}
    findings, undecided = [], []
    for c in candidates:
        d = decided.get(c["candidate_id"])
        if d is None:
            undecided.append(c["candidate_id"])
            if c["gap_type"] in FLOW_GAP_TYPES:      # the label falls back on the finder's reading
                labels[c["flow_id"]] = {"label": LEVEL_TO_LABEL[c["suggested_level"]], "confidence": None,
                                        "source": "finder"}
            continue
        is_gap = _truthy(d.get("is_gap"))
        level = d.get("level") if d.get("level") in LEVELS else c["suggested_level"]
        if c["gap_type"] in FLOW_GAP_TYPES:
            labels[c["flow_id"]] = {"label": LEVEL_TO_LABEL[level] if is_gap else "clear",
                                    "confidence": prob.get(c["candidate_id"]), "source": c["reviewer"]}
        if not is_gap:
            continue
        sections = d.get("sections") or []
        if isinstance(sections, str):
            sections = [sections]
        # formatting only ("Section 8(7)" -> "Sec. 8(7)"); the verifier checks that they exist
        sections = [normalise_section(s) or str(s) for s in sections]
        sections = list(dict.fromkeys(sections))
        findings.append({
            "candidate_id": c["candidate_id"], "flow_id": c["flow_id"], "data_type": c["data_type"],
            "gap_type": c["gap_type"], "level": level, "sections": sections,
            "evidence": str(d.get("evidence") or ""), "rationale": str(d.get("rationale") or ""),
            "reviewer": c["reviewer"], "uncertain": False, "supported": None,
        })

    if merge:
        notice_gap_flows = {f["flow_id"] for f in findings if f["gap_type"] in FLOW_GAP_TYPES}
        # purpose limitation applies to a flow whose notice is clear
        findings = [f for f in findings if not (f["gap_type"] == "purpose_mismatch"
                                                and f["flow_id"] in notice_gap_flows)]
        merged, seen = [], {}
        for f in findings:
            key = (f["data_type"], f["gap_type"])
            if key in seen:
                seen[key].setdefault("merged_flows", [seen[key]["flow_id"]]).append(f["flow_id"])
                continue
            seen[key] = f
            merged.append(f)
        findings = merged
    return {"findings": findings, "flow_labels": labels, "undecided": undecided, "unknown_decisions": unknown}
