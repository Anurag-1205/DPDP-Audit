"""Stage 1 of the pipeline: policy paragraphs -> structured claims.

A claim is what one paragraph says about one practice, in OPP-115 vocabulary:

  {"category", "data_type", "does", "third_party", "third_party_text",
   "purpose", "retention", "audience"}

Three taggers produce claims in the same format:

  oracle      the consolidated OPP-115 annotations (ablation A5; also the training
              targets of the fine-tuned tagger)
  prompted    Qwen2.5-3B-Instruct, zero-shot (ablation A4; the full system until the
              fine-tuned tagger is ready)
  finetuned   Qwen2.5-3B with a QLoRA adapter trained on the 80 training policies

Paragraphs are keyed by a hash of their text, so a claims file serves any case whose
policy contains that paragraph (main cases, ladder rungs, dev cases).
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from ..opp115 import (AUDIENCE, DATA_TYPE, DOES, GENERIC_TYPES, PURPOSE, RET_PERIOD, SPECIFIC_TYPES,
                      THIRD_PARTY, Policy)
from ..paths import RESULTS
from ..tagger_data import CATEGORIES

CLAIMS_DIR = RESULTS / "tagger" / "claims"
FIRST_PARTY = "First Party Collection/Use"
THIRD_PARTY_SHARING = "Third Party Sharing/Collection"
RETENTION = "Data Retention"
AUDIENCES = "International and Specific Audiences"
CLAIM_CATEGORIES = [FIRST_PARTY, THIRD_PARTY_SHARING, RETENTION, AUDIENCES]

DATA_TYPES = SPECIFIC_TYPES + sorted(GENERIC_TYPES)
PURPOSES = ["Basic service/feature", "Additional service/feature", "Advertising", "Marketing",
            "Analytics/Research", "Personalization/Customization", "Service Operation and Security",
            "Legal requirement", "Merger/Acquisition", "Other", "Unspecified"]
ENTITIES = ["Named third party", "Unnamed third party", "Other part of company/affiliate", "Public",
            "Other users", "Other", "Unspecified"]
RETENTION_PERIODS = ["Stated Period", "Limited", "Indefinitely", "Other", "Unspecified"]
AUDIENCE_TYPES = ["Children", "Californians", "Citizens from other countries", "Europeans", "Other"]
FIELDS = ["category", "data_type", "does", "third_party", "third_party_text", "purpose", "retention",
          "audience"]


def para_hash(text: str) -> str:
    return hashlib.sha1(" ".join(text.split()).encode()).hexdigest()[:16]


def _canon(value: str, vocab: list[str]) -> str:
    """Map a value onto the vocabulary, ignoring case (OPP-115 spells some values two ways)."""
    low = {v.lower(): v for v in vocab}
    return low.get((value or "").strip().lower(), "")


def normalise_claim(c: dict) -> dict | None:
    """Coerce one claim onto the vocabulary; None if its category is not a claim category."""
    if not isinstance(c, dict):
        return None
    cat = _canon(str(c.get("category", "")), CATEGORIES)
    if cat not in CLAIM_CATEGORIES:
        return None
    out = {k: "" for k in FIELDS}
    out["category"] = cat
    out["data_type"] = _canon(str(c.get("data_type", "")), DATA_TYPES) or (
        "Unspecified" if cat in (FIRST_PARTY, THIRD_PARTY_SHARING, RETENTION) else "")
    if cat in (FIRST_PARTY, THIRD_PARTY_SHARING):
        out["does"] = "Does Not" if str(c.get("does", "")).strip().lower() in ("does not", "no", "false") \
            else "Does"
        out["purpose"] = _canon(str(c.get("purpose", "")), PURPOSES) or "Unspecified"
    if cat == THIRD_PARTY_SHARING:
        out["third_party"] = _canon(str(c.get("third_party", "")), ENTITIES) or "Unspecified"
        out["third_party_text"] = str(c.get("third_party_text", "") or "")[:200]
    if cat == RETENTION:
        out["retention"] = _canon(str(c.get("retention", "")), RETENTION_PERIODS) or "Unspecified"
    if cat == AUDIENCES:
        out["audience"] = _canon(str(c.get("audience", "")), AUDIENCE_TYPES) or "Other"
    return out


def _dedupe(claims: list[dict]) -> list[dict]:
    seen, out = set(), []
    for c in claims:
        key = tuple(c[k] for k in FIELDS)
        if key not in seen:
            seen.add(key)
            out.append(c)
    return out


# ------------------------------------------------------------------ oracle
def oracle_paragraphs(policy: Policy) -> list[dict]:
    """One record per non-empty segment: text, categories and claims from the annotations."""
    by_seg: dict[int, dict] = {}
    for p in policy.practices:
        rec = by_seg.setdefault(p.segment_id, {"categories": set(), "claims": []})
        if p.category in CATEGORIES:
            rec["categories"].add(p.category)
        if p.category not in CLAIM_CATEGORIES:
            continue
        c = normalise_claim({"category": p.category, "data_type": p.get(DATA_TYPE), "does": p.get(DOES, "Does"),
                             "third_party": p.get(THIRD_PARTY), "third_party_text": p.spans.get(THIRD_PARTY, ""),
                             "purpose": p.get(PURPOSE), "retention": p.get(RET_PERIOD),
                             "audience": p.get(AUDIENCE)})
        if c:
            rec["claims"].append(c)
    out = []
    for seg_id, text in enumerate(policy.segments):
        if not text.strip():
            continue
        rec = by_seg.get(seg_id, {"categories": set(), "claims": []})
        out.append({"hash": para_hash(text), "text": text, "categories": sorted(rec["categories"]),
                    "claims": _dedupe(rec["claims"])})
    return out


@lru_cache(maxsize=1)
def oracle_index() -> dict[str, dict]:
    """Paragraph hash -> oracle record, over all OPP-115 policies."""
    from ..opp115 import load_all

    index = {}
    for pol in load_all():
        for rec in oracle_paragraphs(pol):
            index.setdefault(rec["hash"], rec)
    return index


# ---------------------------------------------------------------- prompted
TAGGER_SYSTEM = "You annotate website privacy policies with the OPP-115 annotation scheme."


def tagger_prompt(paragraph: str) -> str:
    return f"""Annotate this privacy-policy paragraph.

1. "categories": every OPP-115 category the paragraph covers, from:
   {"; ".join(CATEGORIES)}.
2. "claims": one claim per practice the paragraph states, only for the categories
   "{FIRST_PARTY}", "{THIRD_PARTY_SHARING}", "{RETENTION}", "{AUDIENCES}".
   Fields (use exactly these values):
   - data_type: {"; ".join(DATA_TYPES)}
   - does: "Does" or "Does Not" (collection and sharing only)
   - third_party: {"; ".join(ENTITIES)} (sharing only)
   - third_party_text: the words naming the recipient, copied from the paragraph (sharing only)
   - purpose: {"; ".join(PURPOSES)} (collection and sharing only)
   - retention: {"; ".join(RETENTION_PERIODS)} (retention only)
   - audience: {"; ".join(AUDIENCE_TYPES)} (audiences only)
   Use "Generic personal information" when the paragraph says only "personal information" or
   "information about you", and "Unspecified" when no value is stated.

Paragraph:
<<<
{paragraph[:6000]}
>>>

Answer with JSON only:
{{"categories": ["..."], "claims": [{{"category": "...", "data_type": "...", "does": "...",
  "third_party": "...", "third_party_text": "...", "purpose": "...", "retention": "...", "audience": "..."}}]}}"""


def parse_tagger_reply(reply) -> dict:
    """Coerce a tagger reply (parsed JSON or raw text) into {"categories", "claims"}."""
    if isinstance(reply, str):
        from ..llm import parse_json
        try:
            reply = parse_json(reply)
        except ValueError:
            return {"categories": [], "claims": [], "parse_error": True}
    if isinstance(reply, list):
        reply = {"claims": reply}
    if not isinstance(reply, dict):
        return {"categories": [], "claims": [], "parse_error": True}
    cats = sorted({_canon(str(c), CATEGORIES) for c in reply.get("categories", []) or []} - {""})
    claims = _dedupe([c for c in (normalise_claim(x) for x in reply.get("claims", []) or []) if c])
    cats = sorted(set(cats) | {c["category"] for c in claims})
    return {"categories": cats, "claims": claims}


# ------------------------------------------------------------------- files
def claims_path(tagger: str) -> Path:
    return CLAIMS_DIR / f"{tagger}.jsonl"


def load_claims(tagger: str) -> dict[str, dict]:
    """Paragraph hash -> {"categories", "claims"} for a tagger ("oracle" is built in)."""
    if tagger == "oracle":
        return oracle_index()
    p = claims_path(tagger)
    if not p.exists():
        return {}
    out = {}
    for line in p.read_text().splitlines():
        if line.strip():
            r = json.loads(line)
            out[r["hash"]] = r
    return out


def save_claims(tagger: str, records: list[dict]) -> Path:
    """Append-merge records ({"hash", "categories", "claims", ...}) into the tagger's file."""
    p = claims_path(tagger)
    p.parent.mkdir(parents=True, exist_ok=True)
    existing = load_claims(tagger) if tagger != "oracle" else {}
    for r in records:
        existing[r["hash"]] = r
    p.write_text("".join(json.dumps(existing[h]) + "\n" for h in sorted(existing)))
    return p
