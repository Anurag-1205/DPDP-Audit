"""Single-pass baselines.

B1  one prompt, raw inputs (policy text + the app's files as they are)
B2  one prompt, the same information our pipeline has: policy text, parsed app
    facts from the tools, and the DPDP sections retrieved for those facts
B4  B2's prompt sent to a stronger model (configured through the LLM backend)
"""
from __future__ import annotations

import json

from .cases import raw_app_files
from .gaps import GAP_TYPES, LABELS, LEVELS, gap_table
from .llm import LLM
from .retrieval import search
from .tools import get_flows, parse_deps, parse_perms

SYSTEM = (
    "You are a privacy compliance reviewer for India's Digital Personal Data Protection "
    "Act, 2023 and DPDP Rules, 2025. You compare what an application actually does with "
    "what its privacy policy discloses, and report compliance gaps, not legal violations."
)

TASK = f"""Task
1. For EVERY data flow of the application, give a disclosure label:
   - "clear": the policy explicitly and specifically covers this data type, recipient and purpose
   - "vague": covered only by generic wording (e.g. "personal information", "partners", unspecified purpose)
   - "omitted": the policy does not mention this data type for this practice at all
   - "incorrect": the policy explicitly says the opposite (e.g. "we do not share your location")
2. Report every compliance gap as a finding. Gap types: {", ".join(GAP_TYPES)}.
   Levels: {", ".join(LEVELS)} (explicit = policy contradicts the app; vague = only generic
   wording covers it; omission = not mentioned). Cite DPDP sections (e.g. "Sec. 5(1)", "Rule 3")
   and quote the policy sentence you rely on as evidence ("" for an omission).
   A clear flow has no finding. Do not report gaps that are not supported by the inputs.

Answer with JSON only:
{{"flow_labels": {{"<flow_id>": "<{'|'.join(LABELS)}>"}},
  "findings": [{{"flow_id": "...", "data_type": "...", "gap_type": "...", "level": "...",
                "sections": ["..."], "evidence": "..."}}]}}"""


def _gap_reference() -> str:
    rows = [f"- {g}: {v['description']} -> {', '.join(v['gold'])}" for g, v in gap_table().items()]
    return "Gap types and the DPDP sections they usually engage:\n" + "\n".join(rows)


def app_facts(app_dir) -> dict:
    return {"dependencies": [d for d in parse_deps(app_dir) if d["sdk_id"]],
            "permissions": parse_perms(app_dir),
            "flows": get_flows(app_dir)}


def dpdp_context(facts: dict, k: int = 3) -> str:
    """Retrieve DPDP units relevant to the app's flows (deduplicated)."""
    seen, units = set(), []
    queries = [f"{f['data_type']} shared with {f['recipient']} for {f['purpose']}, retained {f['retention']}"
               for f in facts["flows"]]
    if facts["permissions"]["child_directed"]:
        queries.append("app directed at children sends data to advertising or tracking")
    queries.append("notice must describe the personal data and the purpose of processing")
    for q in queries:
        for u in search(q, k):
            if u["id"] not in seen:
                seen.add(u["id"])
                units.append(u)
    return "\n".join(f"[{u['id']}] {u['title']}: {u['text'][:700]}" for u in units)


def prompt_b1(case: dict) -> str:
    return (f"Privacy policy:\n<<<\n{case['policy']}\n>>>\n\n"
            f"Application files:\n<<<\n{raw_app_files(case['app_dir'])}\n>>>\n\n{TASK}")


def prompt_b2(case: dict) -> str:
    facts = app_facts(case["app_dir"])
    return (f"Privacy policy:\n<<<\n{case['policy']}\n>>>\n\n"
            f"Application facts (parsed by tools):\n{json.dumps(facts, indent=1)}\n\n"
            f"Relevant DPDP text:\n{dpdp_context(facts)}\n\n{_gap_reference()}\n\n{TASK}")


def normalise(reply: dict, flow_ids: list[str]) -> dict:
    """Coerce a model reply into the scorer's output format."""
    labels = reply.get("flow_labels", {}) if isinstance(reply, dict) else {}
    findings = []
    for f in (reply.get("findings", []) if isinstance(reply, dict) else []):
        if not isinstance(f, dict) or f.get("gap_type") not in GAP_TYPES:
            continue
        findings.append({
            "flow_id": f.get("flow_id"),
            "data_type": f.get("data_type", ""),
            "gap_type": f["gap_type"],
            "level": f.get("level") if f.get("level") in LEVELS else None,
            "sections": [str(s) for s in f.get("sections", [])],
            "evidence": f.get("evidence", ""),
        })
    flow_labels = {}
    for fid in flow_ids:
        lab = labels.get(fid)
        flow_labels[fid] = {"label": lab if lab in LABELS else "clear", "confidence": None}
    return {"findings": findings, "flow_labels": flow_labels}


def run(system: str, case: dict, llm: LLM, seed: int = 0) -> dict:
    prompt = prompt_b1(case) if system == "B1" else prompt_b2(case)
    resp = llm.complete(prompt, system=SYSTEM, seed=seed)
    flow_ids = [f["flow_id"] for f in get_flows(case["app_dir"])]
    try:
        reply = resp.json()
        parse_error = None
    except ValueError as exc:
        reply, parse_error = {}, str(exc)
    out = normalise(reply, flow_ids)
    out.update(case_id=case["case_id"], system=system, seed=seed, model=resp.model,
               token_prob=resp.token_prob, usage=resp.usage, parse_error=parse_error)
    return out
