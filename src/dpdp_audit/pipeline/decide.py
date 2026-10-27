"""From a reviewer's quotes to a decision (stage 4, deterministic part).

The reviewer agent finds evidence; this module decides. A quote counts only if it is in the
policy (verbatim, or near-verbatim and snapped to the policy sentence). A disclosing quote must
name the data type (pipeline.vocab.KEYWORDS) and, for sharing, the SDK or its company:

  notice     a positive quote (disclosing or generic) that names the data type -- and, for
             sharing, the SDK or its company -> no gap (models sometimes file such a sentence as
             "generic"); else a denial naming the data type -> explicit; else a generic quote, or a
             sharing quote naming the data but not the recipient -> vague; else omission
  purpose    quote stating the app's purpose for the data (v2: or a quote whose paragraph names the
             data, as in "this information is used to ...") -> no gap; else vague if the policy
             uses the data only for unspecified purposes (with a quote), else omission
  retention  the policy keeps data indefinitely -> no gap; a stated period or limit -> explicit;
             retention mentioned without a period -> vague; nothing -> omission. v2: the quote
             counts only if it is about keeping data, and "indefinitely" only if it says so (the
             model tends to echo the app's own "Indefinitely")
  children   a child-directed app sending data to an ad/tracking SDK is always a gap:
             explicit with a children statement, omission without
"""
from __future__ import annotations

import re

from ..gaps import LEVEL_TO_LABEL
from ..tools import lookup_sdk
from ..tools.policy_search import split_paragraphs
from .verifier import _norm, quote_in, snap_quote
from .vocab import mentions_data


def verified(quote, policy_text: str) -> str:
    """The quote as it appears in the policy, or "" if it is not there."""
    q = str(quote or "").strip()
    if not q:
        return ""
    if quote_in(q, policy_text):
        return q
    return snap_quote(q, policy_text) or ""


def names_recipient(text: str, recipient: str) -> bool:
    sdk = lookup_sdk(recipient)
    low = text.lower()
    return bool(sdk) and (sdk["vendor"].lower() in low or sdk["name"].lower() in low)


RETENTION_WORDS = re.compile(r"\b(retain|retention|keep|kept|store|stored|storing|maintain|preserv|archiv|delet"
                             r"|destroy|purg|dispos|as long as|period of|days|months|years|indefinite|permanent"
                             r"|forever|perpetu)", re.I)
INDEFINITE_WORDS = re.compile(r"\b(indefinite|permanent|forever|perpetu|no (set|fixed|specific) (period|time|limit))",
                              re.I)


def paragraph_of(quote: str, policy_text: str) -> str:
    """The policy paragraph that contains a verified quote ("" if none does)."""
    q = _norm(quote)
    return next((p for p in split_paragraphs(policy_text) if q and q in _norm(p)), "")


def _yes(v) -> bool:
    return v.strip().lower() in ("true", "yes", "1") if isinstance(v, str) else bool(v)


def derive(c: dict, raw: dict, policy_text: str, purpose_paragraph: bool = False,
           retention_check: bool = False) -> dict:
    """A decision {candidate_id, is_gap, level, label, sections, evidence, rationale, raw}."""
    gap, d = c["gap_type"], c["data_type"]
    level, evidence = None, ""
    if gap in ("undisclosed_collection", "undisclosed_sharing"):
        cover = verified(raw.get("disclosing_quote"), policy_text)
        deny = verified(raw.get("denial_quote"), policy_text)
        generic = verified(raw.get("generic_quote"), policy_text)
        sharing = gap == "undisclosed_sharing"
        positive = [q for q in (cover, generic) if q and mentions_data(q, d)]
        specific = [q for q in positive if not sharing or names_recipient(q, c["recipient"])]
        if specific:
            level, evidence = None, specific[0]
        elif deny and mentions_data(deny, d) and not positive:
            level, evidence = "explicit", deny
        elif generic or positive:
            level, evidence = "vague", generic or positive[0]
        else:
            level = "omission"
    elif gap == "purpose_mismatch":
        stated = verified(raw.get("purpose_quote"), policy_text)
        unspecified = verified(raw.get("unspecified_purpose_quote"), policy_text)
        if stated and (mentions_data(stated, d)
                       or purpose_paragraph and mentions_data(paragraph_of(stated, policy_text), d)):
            level, evidence = None, stated
        elif unspecified and _yes(raw.get("only_unspecified_purposes")):
            level, evidence = "vague", unspecified
        else:
            level = "omission"
    elif gap == "retention_mismatch":
        quote = verified(raw.get("retention_quote"), policy_text)
        kind = str(raw.get("retention") or "none").strip().lower()
        if retention_check and quote and not RETENTION_WORDS.search(quote):
            quote = ""                                  # not about keeping data
        if retention_check and quote and kind.startswith("indefinite") and not INDEFINITE_WORDS.search(quote):
            kind = "unspecified"                        # the quote does not say "indefinitely"
        if quote and kind.startswith("indefinite"):
            level, evidence = None, quote
        elif quote and kind in ("stated period", "limited", "period", "limit"):
            level, evidence = "explicit", quote
        elif quote:
            level, evidence = "vague", quote
        else:
            level = "omission"
    elif gap == "childrens_data":
        quote = verified(raw.get("children_quote"), policy_text)
        level, evidence = ("explicit", quote) if quote else ("omission", "")
    sections = raw.get("sections") or []
    return {"candidate_id": c["candidate_id"], "is_gap": level is not None, "level": level,
            "label": LEVEL_TO_LABEL[level], "sections": sections if isinstance(sections, list) else [sections],
            "evidence": evidence, "rationale": str(raw.get("rationale") or ""), "raw": raw}
