"""The DPDP-Audit pipeline: tagger -> tools -> mismatch finder -> reviewers -> aggregator -> verifier."""
from __future__ import annotations

import time

from ..baselines import app_facts
from ..gaps import LEVEL_TO_LABEL, gap_table
from ..tools.policy_search import split_paragraphs
from .aggregator import aggregate
from .claims import load_claims, para_hash
from .config import Config
from .finder import Paragraph, all_candidates, find_candidates
from .reviewers import review
from .verifier import verify

REVIEW_ORDER = ["notice", "purpose", "retention", "children"]


def tag(policy_text: str, claims_index: dict[str, dict]) -> list[Paragraph]:
    """Stage 1: look up each paragraph's claims (taggers run offline; see scripts/tag_policies.py)."""
    out = []
    for i, text in enumerate(split_paragraphs(policy_text)):
        rec = claims_index.get(para_hash(text))
        out.append(Paragraph(i, text, list(rec["claims"]) if rec else [], tagged=rec is not None))
    return out


def rules_only(candidates: list[dict]) -> dict:
    """R0: a pseudo-review that accepts every candidate at the finder's suggested level."""
    decisions = [{"candidate_id": c["candidate_id"], "is_gap": True, "level": c["suggested_level"],
                  "label": LEVEL_TO_LABEL[c["suggested_level"]], "sections": gap_table()[c["gap_type"]]["gold"],
                  "evidence": "", "rationale": c["reason"]} for c in candidates]
    return {"reviewer": "rules", "decisions": decisions, "tool_calls": [], "parse_error": None, "llm_calls": 0,
            "token_prob": None, "usage": {}}


def run_case(case: dict, llm, seed: int, cfg: Config, claims_index: dict[str, dict] | None = None,
             verifier_llm=None) -> dict:
    t0 = time.time()
    claims_index = load_claims(cfg.tagger) if claims_index is None else claims_index
    policy = case["policy"]
    paras = tag(policy, claims_index)
    facts = app_facts(case["app_dir"])
    if cfg.finder_filter:
        candidates = find_candidates(paras, facts, policy, purpose_search=cfg.purpose_search,
                                     purpose_always=cfg.purpose_always)
    else:   # B5
        candidates = all_candidates(facts)
    para_text = {p.index: p.text for p in paras}

    if cfg.single_call:   # B5: one generalist call
        groups = [("generalist", candidates)]
    elif cfg.specialists:
        groups = [(r, [c for c in candidates if c["reviewer"] == r]) for r in REVIEW_ORDER]
    else:
        groups = [("generalist", candidates)]
    if cfg.review_batch:   # v2 option: at most review_batch candidates per reviewer call
        n = cfg.review_batch
        groups = [(r, cs[i:i + n]) for r, cs in groups for i in range(0, len(cs), n)]
    if cfg.review:
        reviews = [review(name, cands, para_text, facts, policy, llm, seed, cfg) for name, cands in groups if cands]
    else:   # R0: every candidate is reported at the finder's level, with the gap's DPDP sections
        reviews = [rules_only(candidates)]

    agg = aggregate(facts["flows"], candidates, reviews, merge=cfg.specialists or cfg.single_call)
    if cfg.verifier:
        ver = verify(agg["findings"], policy, facts["flows"], verifier_llm or llm, seed,
                     llm_gaps=cfg.llm_check_gaps, robust=cfg.robust_verifier)
    else:
        ver = {"findings": agg["findings"], "dropped": [], "llm_calls": 0, "error": None, "usage": {}}

    usage = {"prompt": 0, "output": 0}
    for u in [r["usage"] for r in reviews] + [ver.get("usage") or {}]:
        for k in usage:
            usage[k] += u.get(k, 0) or 0
    probs = [r["token_prob"] for r in reviews if r.get("token_prob") is not None]
    tool_calls = [t for r in reviews for t in r["tool_calls"]]
    return {
        "case_id": case["case_id"], "system": cfg.name, "seed": seed, "model": getattr(llm, "model", None),
        "tagger": cfg.tagger,
        "findings": ver["findings"],
        "flow_labels": agg["flow_labels"],
        "dropped": ver["dropped"],
        "token_prob": sum(probs) / len(probs) if probs else None,
        "usage": usage,
        "parse_error": None,
        "trace": {
            "paragraphs": len(paras), "untagged_paragraphs": sum(1 for p in paras if not p.tagged),
            "claims": sum(len(p.claims) for p in paras),
            "candidates": candidates,
            "reviews": [{k: r[k] for k in ("reviewer", "decisions", "parse_error", "llm_calls", "token_prob")}
                        for r in reviews],
            **({"paragraphs_shown": [r.get("paragraphs_shown") for r in reviews],
                "paragraphs_total": len(paras)} if cfg.whole_policy else {}),
            **({"reviewer_parse": [r.get("parse_mode") for r in reviews],
                "reviewer_raw": [r.get("raw") for r in reviews]} if cfg.robust_reviewer else {}),
            "tool_calls": tool_calls,
            "tool_calls_valid": sum(1 for t in tool_calls if t["valid"]),
            "undecided": agg["undecided"], "unknown_decisions": agg["unknown_decisions"],
            "verifier_error": ver["error"],
            **({"verifier_parse": ver.get("parse"), "verifier_unchecked": ver.get("unchecked", 0),
                "verifier_raw": ver.get("raw")} if cfg.robust_verifier else {}),
            "llm_calls": sum(r["llm_calls"] for r in reviews) + ver["llm_calls"],
            "seconds": round(time.time() - t0, 2),
        },
    }
