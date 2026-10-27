"""Stage 6: the evidence verifier.

1. The quote must appear word for word in the policy (an empty quote is allowed only for an
   omission). A near-verbatim quote (>= 85% of its words in one policy sentence) is replaced by
   that sentence; an omission's unverifiable quote is removed. Otherwise the finding is dropped.
2. At least one cited section must exist among the DPDP units, after normalisation
   ("Section 8(7)" -> "Sec. 8(7)"; "Article 6 GDPR" is rejected). Otherwise it is dropped.
3. One LLM call per case asks whether the cited text supports calling each finding a gap.
   An unsupported finding is kept but marked uncertain (human review).
"""
from __future__ import annotations

import json
import re
from functools import lru_cache

from ..gaps import normalise_section  # noqa: F401  (re-exported)
from ..llm import parse_json
from ..retrieval import load_units


@lru_cache(maxsize=1)
def unit_ids() -> frozenset[str]:
    return frozenset(u["id"] for u in load_units())


@lru_cache(maxsize=1)
def unit_text() -> dict[str, str]:
    out = {}
    for u in load_units():
        out.setdefault(u["id"], f"{u['title']}: {u['text']}".strip(": "))
    return out


def section_exists(s: str) -> bool:
    ids = unit_ids()
    return s in ids or any(i.startswith(s + "(") for i in ids)


_QUOTES = str.maketrans({"‘": "'", "’": "'", "“": '"', "”": '"', "–": "-", "—": "-"})


def _norm(text: str) -> str:
    return " ".join(text.translate(_QUOTES).lower().split())


def _strip_prefix(quote: str) -> str:
    """Drop a paragraph tag ("[P3]", "P3:") and surrounding quote marks."""
    q = (quote or "").translate(_QUOTES).strip()
    q = re.sub(r"^\[?P\d+\]?[:.]?\s+", "", q)
    return q.strip().strip('"\'')


_SENT = re.compile(r"[^.!?\n]+[.!?]*")
SNAP_OVERLAP = 0.85


def snap_quote(quote: str, source: str) -> str | None:
    """The policy sentence a near-verbatim quote copies (>= 85% of its words, in a sentence of
    similar length), or None. The returned text is verbatim from the policy."""
    words = re.findall(r"[a-z0-9']+", _norm(_strip_prefix(quote)))
    if len(words) < 5:
        return None
    best, best_score = None, 0.0
    for m in _SENT.finditer(source):
        sent = m.group().strip()
        sw = re.findall(r"[a-z0-9']+", _norm(sent))
        if not sw or len(sw) < 0.5 * len(words):
            continue
        bag = set(sw)
        score = sum(1 for w in words if w in bag) / len(words)
        if score > best_score:
            best, best_score = sent, score
    return best if best_score >= SNAP_OVERLAP else None


def quote_in(quote: str, source: str) -> bool:
    """Every part of the quote (split on ellipses) appears in the source, ignoring case and spacing."""
    q = _strip_prefix(quote)
    parts = [p.strip(" .,;:\"'") for p in re.split(r"\.{3}|…", q)]
    parts = [p for p in parts if len(p.split()) >= 1]
    src = _norm(source)
    return bool(parts) and all(_norm(p) in src for p in parts)


VERIFIER_SYSTEM = ("You check the findings of a privacy compliance audit under India's DPDP Act, 2023. "
                   "You are strict: a finding is supported only if its evidence and the cited DPDP text "
                   "justify it.")


def support_prompt(findings: list[dict], flows: dict[str, dict]) -> str:
    items = []
    for i, f in enumerate(findings):
        flow = flows.get(f["flow_id"], {})
        items.append({
            "finding_id": i, "gap_type": f["gap_type"], "level": f["level"], "data_type": f["data_type"],
            "app_flow": {k: flow.get(k) for k in ("recipient", "purpose", "retention")},
            "policy_evidence": f["evidence"] or "(none: the policy is said not to mention it)",
            "cited": {s: unit_text().get(s, "")[:400] for s in f["sections"]},
            "rationale": f.get("rationale", ""),
        })
    return f"""For each finding, decide whether the policy evidence and the cited DPDP text support
calling it a compliance gap of that type and level. A finding is NOT supported when the evidence
actually discloses the app's practice, when the evidence is about something else, or when the cited
DPDP text has nothing to do with the gap.

Findings:
{json.dumps(items, indent=1)}

Answer with JSON only:
{{"checks": [{{"finding_id": 0, "supported": true, "reason": "..."}}]}}"""


def verify(findings: list[dict], policy_text: str, flows: list[dict], llm, seed: int,
           use_llm: bool = True) -> dict:
    """Return {"findings": kept, "dropped": [...], "llm_calls", "error"}."""
    kept, dropped = [], []
    for f in findings:
        secs = [n for n in (normalise_section(s) for s in f["sections"]) if n]
        secs = list(dict.fromkeys(s for s in secs if section_exists(s)))
        quote_ok = bool(f["evidence"].strip()) and quote_in(f["evidence"], policy_text)
        if f["evidence"].strip() and not quote_ok:
            snapped = snap_quote(f["evidence"], policy_text)
            if snapped:
                f = dict(f, evidence=snapped, evidence_snapped=True)
                quote_ok = True
        if not quote_ok and f["level"] == "omission":
            # an omission needs no quote: an unverifiable one is removed, not the finding
            f = dict(f, evidence="", evidence_removed=bool(f["evidence"].strip()))
            quote_ok = True
        if not quote_ok:
            dropped.append(dict(f, drop_reason="quote not found in the policy"))
        elif not secs:
            dropped.append(dict(f, drop_reason="no valid DPDP section"))
        else:
            kept.append(dict(f, sections=secs))
    result = {"findings": kept, "dropped": dropped, "llm_calls": 0, "error": None, "usage": {}}
    if not kept or not use_llm:
        return result
    flow_map = {f["flow_id"]: f for f in flows}
    try:
        resp = llm.complete(support_prompt(kept, flow_map), system=VERIFIER_SYSTEM, seed=seed)
        result["llm_calls"] = 1
        result["usage"] = resp.usage or {}
        reply = parse_json(resp.text)
        checks = {int(c["finding_id"]): c for c in reply.get("checks", [])
                  if isinstance(c, dict) and str(c.get("finding_id", "")).lstrip("-").isdigit()}
    except (ValueError, AttributeError, TypeError) as exc:
        # fail open: the deterministic checks stand, the LLM check is recorded as missing
        result["error"] = str(exc)[:300]
        return result
    for i, f in enumerate(kept):
        c = checks.get(i)
        if c is None:
            continue
        ok = c.get("supported")
        ok = ok.strip().lower() in ("true", "yes") if isinstance(ok, str) else bool(ok)
        f["supported"] = ok
        f["uncertain"] = not ok
        f["verifier_reason"] = str(c.get("reason", ""))[:300]
    return result
