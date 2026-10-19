"""Split the DPDP Act, 2023 and DPDP Rules, 2025 into citable units.

Input is the plain text produced by `pdftotext` (no -layout) from the
official Gazette PDFs. Output is one record per sub-section (Act) or per
rule (Rules), e.g. {"id": "Sec. 8(7)", "source": "act", ...}.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

# Marginal headings of the Act are lost in plain-text extraction, so the
# sections used by the benchmark are named here.
ACT_TITLES = {
    2: "Definitions",
    3: "Application of Act",
    4: "Grounds for processing personal data",
    5: "Notice",
    6: "Consent",
    7: "Certain legitimate uses",
    8: "General obligations of Data Fiduciary",
    9: "Processing of personal data of children",
    10: "Additional obligations of Significant Data Fiduciary",
    11: "Right to access information about personal data",
    12: "Right to correction and erasure of personal data",
    13: "Right of grievance redressal",
    14: "Right to nominate",
    15: "Duties of Data Principal",
    16: "Processing of personal data outside India",
    17: "Exemptions",
    33: "Penalties",
}

_SECTION_START = re.compile(r"^(\d{1,2})\. (?=\(1\) |[A-Z])", re.M)
_SUBSECTION = re.compile(r"(?:^|\s)\((\d{1,2})\) (?=[A-Z])", re.M)
_RULE_START = re.compile(r"^(\d{1,2})\. ([A-Z][^—–\n]{2,120}(?:\n[^—–\n]{1,120})?)\s*[—–]", re.M)
_PAGE_NOISE = re.compile(
    r"^\s*(THE GAZETTE OF INDIA.*|\[PART II.*|SEC\. 1\].*|\d+\s*)$", re.M
)


def _clean(text: str) -> str:
    text = _PAGE_NOISE.sub("", text)
    text = re.sub(r"-\n(?=[a-z])", "", text)  # re-join hyphenated words
    text = re.sub(r"\s*\n\s*", " ", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def split_act(raw: str) -> list[dict]:
    """Return one record per sub-section of the Act (sections 1-44)."""
    body = raw[raw.find("1. (1) This Act may be called"):]
    end = body.find("THE SCHEDULE")
    if end > 0:
        body = body[:end]
    starts = [m for m in _SECTION_START.finditer(body)]
    # keep the first, strictly increasing run 1..44 (drops list items that look like sections)
    seq, expected = [], 1
    for m in starts:
        if int(m.group(1)) == expected:
            seq.append(m)
            expected += 1
    records = []
    for i, m in enumerate(seq):
        num = int(m.group(1))
        stop = seq[i + 1].start() if i + 1 < len(seq) else len(body)
        text = body[m.end():stop]
        title = ACT_TITLES.get(num, "")
        subs = list(_SUBSECTION.finditer(text))
        if not subs or subs[0].group(1) != "1":
            records.append(_record(f"Sec. {num}", "act", num, None, title, text))
            continue
        for j, s in enumerate(subs):
            sub_stop = subs[j + 1].start() if j + 1 < len(subs) else len(text)
            records.append(
                _record(f"Sec. {num}({s.group(1)})", "act", num, int(s.group(1)), title,
                        text[s.end():sub_stop])
            )
    return records


def split_rules(raw: str) -> list[dict]:
    """Return one record per rule (English text only) plus the Third Schedule."""
    start = raw.find("1. Short title and commencement.")
    body = raw[start:]
    first_schedule = body.find("FIRST SCHEDULE")
    rules_part = body[:first_schedule] if first_schedule > 0 else body
    matches, expected = [], 1
    for m in _RULE_START.finditer(rules_part):
        n = int(m.group(1))
        if n >= expected and n <= expected + 2:  # tolerate a heading the regex missed
            matches.append(m)
            expected = n + 1
    records = []
    for i, m in enumerate(matches):
        stop = matches[i + 1].start() if i + 1 < len(matches) else len(rules_part)
        num = int(m.group(1))
        records.append(_record(f"Rule {num}", "rules", num, None, " ".join(m.group(2).split()).strip(" .—–-"),
                               rules_part[m.end():stop]))
    third = body.find("THIRD SCHEDULE")
    fourth = body.find("FOURTH SCHEDULE")
    if third > 0:
        records.append(_record("Third Schedule", "rules", None, None,
                               "Time periods for erasure of personal data",
                               body[third + len("THIRD SCHEDULE"):fourth]))
    return records


def _record(cid, source, number, sub, title, text):
    return {"id": cid, "source": source, "number": number, "sub": sub,
            "title": title, "text": _clean(text)}


def build(act_txt: Path, rules_txt: Path, out: Path) -> list[dict]:
    records = split_act(act_txt.read_text()) + split_rules(rules_txt.read_text())
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as f:
        for r in records:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return records
