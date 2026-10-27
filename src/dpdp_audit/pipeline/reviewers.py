"""Stage 4: specialist reviewer agents.

Each reviewer gets the candidates of its gap types, the policy paragraphs linked to them, the
retrieved DPDP units and up to `max_tool_calls` tool calls. It looks for evidence: for every
candidate it copies the policy sentences that disclose, deny or only generically cover the flow
(or state a purpose, a retention period, a children's policy). pipeline.decide turns the
verified quotes into the decision

  {"candidate_id", "is_gap", "level", "label", "sections", "evidence", "rationale"}

so a gap is reported because of what the policy text shows, not because the model says so.

Protocol: every reply is one JSON object, either
  {"action": "tool", "tool": "<name>", "query": "..."}   or
  {"action": "final", "answers": [...]}
A reply that is not JSON ends the loop with no decisions. Unknown tools get an error
message. Every tool call is logged with its validity.
"""
from __future__ import annotations

import json

from ..baselines import SYSTEM as BASE_SYSTEM
from ..llm import parse_json
from ..retrieval import search as dpdp_search
from ..tools import lookup_sdk, search_policy
from .config import Config
from .decide import derive
from .vocab import glossary

# What the reviewer must look for, per gap type (the fields of its answer)
EVIDENCE = {
    "undisclosed_collection": """For a collection candidate (recipient "first_party"):
  "disclosing_quote": the sentence saying the company collects or uses this data type (it names the
      data, e.g. "email address" for Contact), or "" if there is none
  "denial_quote": a sentence saying it does NOT collect this data type, or ""
  "generic_quote": a sentence that covers it only generically ("personal information",
      "information you provide"), or \"\"""",
    "undisclosed_sharing": """For a sharing candidate (recipient is an SDK):
  "disclosing_quote": the sentence saying this data type is shared with the SDK's company or the
      SDK by name (e.g. "Google", "Mixpanel"), or "" if there is none
  "denial_quote": a sentence saying it does NOT share this data type with third parties, or ""
  "generic_quote": a sentence that covers the sharing only generically (unnamed "partners" or
      "third parties", or "personal information"), or \"\"""",
    "purpose_mismatch": """For a purpose candidate:
  "purpose_quote": the sentence saying this data type is used for the app's purpose (or an
      equivalent one, see the purposes above), or "" if there is none
  "unspecified_purpose_quote": a sentence that mentions this data type without any purpose, or ""
  "only_unspecified_purposes": true if the policy never gives a purpose for this data type""",
    "retention_mismatch": """For a retention candidate (the app keeps the data indefinitely):
  "retention_quote": the sentence about how long data is kept, or "" if the policy says nothing
  "retention": "stated period" (a number of days, months, years), "limited" ("as long as
      necessary", "until you delete your account"), "indefinitely", or "unspecified\"""",
    "childrens_data": """For a children's-data candidate (child-directed app, ad or tracking SDK):
  "children_quote": a sentence about children (e.g. "not directed at children under 13"), or \"\"""",
}
ROLES = {
    "notice": {"title": "notice and consent", "gaps": ["undisclosed_collection", "undisclosed_sharing"],
               "focus": "Sec. 5 and Sec. 6 of the Act and Rule 3: the notice must give an itemised description "
                        "of the personal data and the purpose; consent covers only what the notice describes."},
    "purpose": {"title": "purpose limitation", "gaps": ["purpose_mismatch"],
                "focus": "Sec. 5(1) and Sec. 6(1): data may be processed only for the purpose stated in the "
                         "notice."},
    "retention": {"title": "retention", "gaps": ["retention_mismatch"],
                  "focus": "Sec. 8(7), Rule 8 and the Third Schedule: data must be erased once the purpose is "
                           "served."},
    "children": {"title": "children's data", "gaps": ["childrens_data"],
                 "focus": "Sec. 9 and Rule 10: no tracking, behavioural monitoring or targeted advertising "
                          "directed at children, and verifiable parental consent."},
}
GENERALIST = {"title": "generalist", "gaps": list(EVIDENCE),
              "focus": "notice and consent, purpose limitation, retention and children's data under the Act."}
TOOL_RESULT_CHARS = 2500


def role_for(name: str) -> dict:
    return GENERALIST if name == "generalist" else ROLES[name]


class Tools:
    """The three tools a reviewer may call."""

    def __init__(self, policy_text: str, retrieval: bool, dpdp_k: int):
        self.policy_text = policy_text
        self.retrieval = retrieval
        self.dpdp_k = dpdp_k

    @property
    def names(self) -> list[str]:
        return ["search_policy", "lookup_sdk"] + (["retrieve_dpdp"] if self.retrieval else [])

    def call(self, request: dict) -> tuple[bool, str]:
        name = request.get("tool")
        query = str(request.get("query") or request.get("name") or "").strip()
        if name not in self.names:
            return False, f"error: unknown tool {name!r}; available tools: {', '.join(self.names)}"
        if not query:
            return False, "error: the tool call needs a non-empty \"query\""
        if name == "search_policy":
            hits = search_policy(self.policy_text, query, k=3)
            return True, "\n".join(f"[P{h['paragraph']}] {h['text'][:800]}" for h in hits) or "no paragraph matches"
        if name == "retrieve_dpdp":
            return True, "\n".join(f"[{u['id']}] {u['title']}: {u['text'][:500]}"
                                   for u in dpdp_search(query, self.dpdp_k))
        sdk = lookup_sdk(query)
        return True, json.dumps(sdk) if sdk else f"no SDK named {query!r} in the table"


def dpdp_units_for(candidates: list[dict], k: int) -> list[dict]:
    seen, units = set(), []
    for c in candidates:
        q = (f"{c['gap_type'].replace('_', ' ')}: {c['data_type']} sent to {c['recipient']} for {c['purpose']}, "
             f"retained {c['retention']}")
        for u in dpdp_search(q, k):
            if u["id"] not in seen:
                seen.add(u["id"])
                units.append(u)
    return units


def select_paragraphs(candidates: list[dict], cap: int) -> list[int]:
    """The first linked paragraph of every candidate, then the others in order, up to the cap."""
    first = []
    for c in candidates:
        if c["paragraphs"] and c["paragraphs"][0] not in first:
            first.append(c["paragraphs"][0])
    rest = []
    for c in candidates:
        rest += [i for i in c["paragraphs"] if i not in first and i not in rest]
    return (first + rest)[: max(cap, len(first))]


TOOL_LINES = {
    "search_policy": '{"action": "tool", "tool": "search_policy", "query": "..."} returns the 3 policy '
                     "paragraphs most similar to the query",
    "retrieve_dpdp": '{"action": "tool", "tool": "retrieve_dpdp", "query": "..."} returns DPDP Act/Rules units',
    "lookup_sdk": '{"action": "tool", "tool": "lookup_sdk", "query": "<sdk name>"} returns the SDK vendor and '
                  "category",
}


def build_prompt(role_name: str, candidates: list[dict], paragraphs: dict[int, str], facts: dict,
                 dpdp_units: list[dict], tools: Tools, cfg: Config) -> str:
    role = role_for(role_name)
    # the finder's suggested level and reason are not shown: the reviewer reads the policy afresh
    cand_view = []
    for c in candidates:
        sdk = lookup_sdk(c["recipient"]) if c["recipient"] != "first_party" else None
        recipient = f"{sdk['name']} ({sdk['vendor']}, {sdk['category']})" if sdk else c["recipient"]
        cand_view.append({"candidate_id": c["candidate_id"], "gap_type": c["gap_type"], "data_type": c["data_type"],
                          "recipient": recipient, "purpose": c["purpose"], "retention": c["retention"],
                          "paragraphs": c["paragraphs"]})
    dpdp = "\n".join(f"[{u['id']}] {u['title']}: {u['text'][:500]}" for u in dpdp_units) \
        if dpdp_units else "(not provided)"
    gaps = sorted({c["gap_type"] for c in candidates}, key=list(EVIDENCE).index)
    head = f"You are the {role['title']} reviewer. Focus: {role['focus']}\n\n"
    body = f"""Application: child_directed = {facts['permissions']['child_directed']}

What the data types and purposes cover (a policy discloses a data type when it names any of these
examples; it need not use the category name):
{glossary([c['data_type'] for c in candidates], [c['purpose'] for c in candidates])}

Candidates to check, one per data flow of the application:
{json.dumps(cand_view, indent=1)}

Relevant DPDP text:
{dpdp}

Your job is to find evidence in the policy, not to guess. For every candidate, read the
paragraphs (and search the policy if they do not settle it) and answer with these fields, copying
sentences from the policy word for word:
{chr(10).join(EVIDENCE[g] for g in gaps)}
Every answer also has "sections" (the DPDP units the duty comes from, e.g. ["Sec. 5(1)", "Rule 3"])
and "rationale" (one short sentence).

You may first call tools (at most {cfg.max_tool_calls} calls in total), one per reply:
{chr(10).join(TOOL_LINES[t] for t in tools.names)}
Then give the final answer:
{{"action": "final", "answers": [{{"candidate_id": "...", ..., "sections": ["..."], "rationale": "..."}}]}}
Reply with one JSON object only."""
    # policy paragraphs fill what is left of the budget, keeping room for tool results
    budget = cfg.prompt_char_budget - len(head) - len(body) - cfg.max_tool_calls * TOOL_RESULT_CHARS
    shown = []
    for i in select_paragraphs(candidates, cfg.max_paragraphs):
        text = paragraphs.get(i, "")
        if text and len(text) + 8 <= budget:
            shown.append(f"[P{i}] {text}")
            budget -= len(text) + 8
    return (f"{head}Policy paragraphs linked to the candidates ([P<n>] = paragraph number):\n<<<\n"
            f"{chr(10).join(shown) or '(none)'}\n>>>\n\n{body}")


def system_prompt(role_name: str) -> str:
    return f"{BASE_SYSTEM} You are the {role_for(role_name)['title']} reviewer of a multi-agent audit."


def review(role_name: str, candidates: list[dict], paragraphs: dict[int, str], facts: dict, policy_text: str,
           llm, seed: int, cfg: Config) -> dict:
    """Run one reviewer's tool loop. Returns decisions, tool-call log, LLM call count and token prob."""
    tools = Tools(policy_text, cfg.retrieval, cfg.dpdp_k)
    units = dpdp_units_for(candidates, cfg.dpdp_k) if cfg.retrieval else []
    base = build_prompt(role_name, candidates, paragraphs, facts, units, tools, cfg)
    system = system_prompt(role_name)
    by_id = {c["candidate_id"]: c for c in candidates}
    transcript, log, calls = [], [], 0
    usage = {"prompt": 0, "output": 0}
    result = {"reviewer": role_name, "decisions": [], "tool_calls": log, "parse_error": None, "token_prob": None,
              "unknown_answers": []}
    for step in range(cfg.max_tool_calls + 1):
        prompt = base
        if transcript:
            prompt += "\n\nYour previous steps:\n" + "\n".join(transcript)
            if step == cfg.max_tool_calls:
                prompt += "\n\nNo tool calls are left. Give the final answer now."
        resp = llm.complete(prompt, system=system, seed=seed)
        calls += 1
        for k in usage:
            usage[k] += (resp.usage or {}).get(k, 0) or 0
        try:
            reply = parse_json(resp.text)
        except ValueError as exc:
            result["parse_error"] = str(exc)[:300]
            break
        if not isinstance(reply, dict):
            result["parse_error"] = "reply is not a JSON object"
            break
        if reply.get("action") == "tool" and step < cfg.max_tool_calls:
            ok, out = tools.call(reply)
            log.append({"reviewer": role_name, "step": step, "tool": reply.get("tool"),
                        "query": str(reply.get("query") or reply.get("name") or "")[:200], "valid": ok})
            transcript.append(f"- call {json.dumps({k: reply.get(k) for k in ('tool', 'query')})}\n  result:\n"
                              + "\n".join("    " + line for line in out[:TOOL_RESULT_CHARS].splitlines()))
            continue
        if reply.get("action") == "tool":   # out of calls and still asking
            log.append({"reviewer": role_name, "step": step, "tool": reply.get("tool"), "query": "",
                        "valid": False, "error": "tool budget exhausted"})
            result["parse_error"] = "no final answer after the tool budget"
            break
        answers = reply.get("answers", reply.get("decisions", []))
        if isinstance(answers, list):
            answers = [a for a in answers if isinstance(a, dict)]
            result["decisions"] = [derive(by_id[str(a.get("candidate_id"))], a, policy_text,
                                          purpose_paragraph=cfg.purpose_paragraph,
                                          retention_check=cfg.retention_check)
                                   for a in answers if str(a.get("candidate_id")) in by_id]
            result["unknown_answers"] = [str(a.get("candidate_id")) for a in answers
                                         if str(a.get("candidate_id")) not in by_id]
        result["token_prob"] = resp.token_prob
        break
    result["llm_calls"] = calls
    result["usage"] = usage
    return result
