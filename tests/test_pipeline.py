"""Pipeline tests with a scripted fake LLM (no API or GPU access)."""
import json
from dataclasses import replace

import pytest

from dpdp_audit.llm import LLMResponse
from dpdp_audit.pipeline import CONFIGS, get_config, run_case
from dpdp_audit.pipeline import reviewers as rv
from dpdp_audit.pipeline.aggregator import aggregate
from dpdp_audit.pipeline.claims import normalise_claim, para_hash, parse_tagger_reply
from dpdp_audit.pipeline.finder import Paragraph, find_candidates
from dpdp_audit.pipeline.verifier import normalise_section, quote_in, verify

POLICY = ("We collect your email address to create your account.\n\n"
          "We may share information with our partners.\n\n"
          "We keep your data only as long as necessary.")


class FakeLLM:
    """Returns scripted replies in order; records every prompt."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.prompts = []
        self.model = "fake"

    def complete(self, prompt, system="", seed=0):
        self.prompts.append(prompt)
        reply = self.replies.pop(0) if self.replies else '{"action": "final", "decisions": []}'
        text = reply if isinstance(reply, str) else json.dumps(reply)
        return LLMResponse(text=text, model="fake", seed=seed, token_prob=0.9, usage={"prompt": 10, "output": 5})


@pytest.fixture(autouse=True)
def no_embeddings(monkeypatch):
    fake = lambda q, k=3: [{"id": "Sec. 5(1)", "title": "Notice", "text": "notice text", "score": 1.0}]
    monkeypatch.setattr(rv, "dpdp_search", fake)


def facts(flows, child=False, deps=()):
    return {"flows": flows, "permissions": {"child_directed": child, "permissions": [], "data_types": []},
            "dependencies": list(deps)}


def claim(**kw):
    return normalise_claim(kw)


def flow(fid, d, rec="first_party", purpose="Basic service/feature", retention="Unspecified"):
    return {"flow_id": fid, "data_type": d, "recipient": rec, "purpose": purpose, "retention": retention}


# ------------------------------------------------------------------ finder
def test_finder_levels_follow_claims():
    paras = [Paragraph(0, "a", [claim(category="First Party Collection/Use", data_type="Contact",
                                      does="Does", purpose="Basic service/feature")]),
             Paragraph(1, "b", [claim(category="Third Party Sharing/Collection",
                                      data_type="Generic personal information", does="Does",
                                      third_party="Unnamed third party", purpose="Advertising")]),
             Paragraph(2, "c", [claim(category="Data Retention", data_type="Generic personal information",
                                      retention="Limited")])]
    fl = [flow("f1", "Contact"), flow("f2", "Location", "admob", "Advertising"),
          flow("f3", "Contact", retention="Indefinitely"), flow("f4", "Health")]
    cands = find_candidates(paras, facts(fl), POLICY)
    got = {(c["flow_id"], c["gap_type"]): c["suggested_level"] for c in cands}
    assert ("f1", "undisclosed_collection") not in got          # covered: no candidate
    assert got[("f2", "undisclosed_sharing")] == "vague"
    assert got[("f3", "retention_mismatch")] == "explicit"
    assert got[("f4", "undisclosed_collection")] == "omission"
    assert all(c["candidate_id"].startswith("c") for c in cands)


def test_finder_no_candidates_means_no_llm_call():
    paras = [Paragraph(0, POLICY, [claim(category="First Party Collection/Use", data_type="Contact",
                                         does="Does", purpose="Basic service/feature")])]
    assert find_candidates(paras, facts([flow("f1", "Contact")]), POLICY) == []


def test_children_candidate_needs_ad_sdk():
    fl = [flow("f1", "IP address and device IDs", "admob", "Advertising"),
          flow("f2", "IP address and device IDs", "sentry", "Service Operation and Security")]
    cands = find_candidates([Paragraph(0, "x", [])], facts(fl, child=True), POLICY)
    kids = [c for c in cands if c["gap_type"] == "childrens_data"]
    assert [c["flow_id"] for c in kids] == ["f1"] and kids[0]["suggested_level"] == "omission"


# --------------------------------------------------------------- reviewers
def _cand(cid="c1", gap="undisclosed_sharing", fid="f2", d="Location", level="vague"):
    return {"candidate_id": cid, "flow_id": fid, "data_type": d, "recipient": "admob", "purpose": "Advertising",
            "retention": "Unspecified", "gap_type": gap, "reviewer": "notice", "suggested_level": level,
            "reason": "r", "paragraphs": [1]}


def test_tool_loop_then_final():
    final = {"action": "final", "answers": [{"candidate_id": "c1",
                                             "generic_quote": "We may share information with our partners."}]}
    llm = FakeLLM([{"action": "tool", "tool": "search_policy", "query": "partners"},
                   {"action": "tool", "tool": "lookup_sdk", "query": "admob"}, final])
    cfg = get_config("full")
    r = rv.review("notice", [_cand()], {1: "We may share information with our partners."},
                  facts([]), POLICY, llm, 0, cfg)
    assert r["llm_calls"] == 3 and len(r["decisions"]) == 1
    assert (r["decisions"][0]["is_gap"], r["decisions"][0]["level"]) == (True, "vague")
    assert [t["valid"] for t in r["tool_calls"]] == [True, True]
    assert "Your previous steps" in llm.prompts[-1]


def test_unknown_tool_returns_error_and_is_logged():
    llm = FakeLLM([{"action": "tool", "tool": "delete_everything", "query": "x"},
                   {"action": "final", "decisions": []}])
    r = rv.review("notice", [_cand()], {}, facts([]), POLICY, llm, 0, get_config("full"))
    assert r["tool_calls"][0]["valid"] is False
    assert "unknown tool" in llm.prompts[-1]


def test_tool_budget_is_enforced():
    ask = {"action": "tool", "tool": "search_policy", "query": "x"}
    llm = FakeLLM([ask] * 10)
    r = rv.review("notice", [_cand()], {}, facts([]), POLICY, llm, 0, get_config("full"))
    assert r["llm_calls"] == 4                      # 3 tool calls + 1 forced final turn
    assert "No tool calls are left" in llm.prompts[-1]
    assert r["decisions"] == [] and r["parse_error"]


def test_non_json_reply_ends_loop():
    llm = FakeLLM(["I think there is a gap."])
    r = rv.review("notice", [_cand()], {}, facts([]), POLICY, llm, 0, get_config("full"))
    assert r["decisions"] == [] and r["parse_error"] and r["llm_calls"] == 1


def test_a2_hides_retrieval_tool():
    tools = rv.Tools(POLICY, retrieval=False, dpdp_k=3)
    assert "retrieve_dpdp" not in tools.names
    ok, msg = tools.call({"tool": "retrieve_dpdp", "query": "x"})
    assert not ok and "unknown tool" in msg


def test_prompt_stays_within_budget():
    long_paras = {i: "word " * 2000 for i in range(20)}
    cands = [dict(_cand(cid=f"c{i}"), paragraphs=list(range(20))) for i in range(5)]
    cfg = get_config("full")
    prompt = rv.build_prompt("notice", cands, long_paras, facts([]), [], rv.Tools(POLICY, True, 3), cfg)
    assert len(prompt) <= cfg.prompt_char_budget


# -------------------------------------------------------------- aggregator
def test_aggregator_labels_merge_and_purpose_rule():
    fl = [flow("f1", "Location", "admob", "Advertising"), flow("f2", "Location", "mixpanel", "Advertising"),
          flow("f3", "Contact")]
    cands = [_cand("c1", fid="f1"), _cand("c2", fid="f2"),
             dict(_cand("c3", gap="purpose_mismatch", fid="f1"), reviewer="purpose"),
             dict(_cand("c4", gap="undisclosed_collection", fid="f3", d="Contact", level="omission"))]
    reviews = [{"decisions": [{"candidate_id": "c1", "is_gap": True, "level": "vague", "sections": ["Sec. 5(1)"],
                               "evidence": "We may share information with our partners."},
                              {"candidate_id": "c2", "is_gap": "true", "level": "vague"},
                              {"candidate_id": "c9", "is_gap": True}], "token_prob": 0.8},
               {"decisions": [{"candidate_id": "c3", "is_gap": True, "level": "omission"}], "token_prob": 0.7}]
    agg = aggregate(fl, cands, reviews, merge=True)
    keys = [(f["data_type"], f["gap_type"]) for f in agg["findings"]]
    assert keys == [("Location", "undisclosed_sharing")]          # merged; purpose dropped
    assert agg["findings"][0]["merged_flows"] == ["f1", "f2"]
    assert agg["flow_labels"]["f1"]["label"] == "vague"
    assert agg["flow_labels"]["f3"] == {"label": "omitted", "confidence": None, "source": "finder"}
    assert agg["undecided"] == ["c4"] and agg["unknown_decisions"] == ["c9"]
    no_merge = aggregate(fl, cands, reviews, merge=False)
    assert len(no_merge["findings"]) == 3                          # A3: no aggregation


# ---------------------------------------------------------------- verifier
def test_normalise_section():
    assert normalise_section("Section 8(7)") == "Sec. 8(7)"
    assert normalise_section("Sec 6 (1)(d)") == "Sec. 6(1)"
    assert normalise_section("Rule 3(2)") == "Rule 3"
    assert normalise_section("the Third Schedule") == "Third Schedule"
    assert normalise_section("Article 6 GDPR") is None
    assert normalise_section("Sec. 5(1) DPDP") == "Sec. 5(1)"


def test_quote_check():
    assert quote_in("We may share information with our partners", POLICY)
    assert quote_in("“We collect your email address ... create your account.”", POLICY)
    assert quote_in("[P1] We may share information with our partners.", POLICY)
    assert not quote_in("We sell your data to anyone.", POLICY)
    assert not quote_in("", POLICY)


def _finding(**kw):
    base = {"flow_id": "f1", "data_type": "Location", "gap_type": "undisclosed_sharing", "level": "vague",
            "sections": ["Section 5(1)"], "evidence": "We may share information with our partners.",
            "uncertain": False, "supported": None}
    return dict(base, **kw)


def test_verifier_drops_and_marks_uncertain():
    findings = [_finding(),                                                   # kept, LLM says no
                _finding(data_type="Contact", evidence="We sell everything."),  # quote not found
                _finding(data_type="Health", sections=["Article 6 GDPR"]),       # no valid section
                _finding(data_type="Financial", level="omission", evidence="")]  # omission, empty quote ok
    llm = FakeLLM([{"checks": [{"finding_id": 0, "supported": False, "reason": "covered"},
                               {"finding_id": 1, "supported": True}]}])
    out = verify(findings, POLICY, [], llm, 0)
    assert [f["data_type"] for f in out["findings"]] == ["Location", "Financial"]
    assert out["findings"][0]["uncertain"] and out["findings"][0]["sections"] == ["Sec. 5(1)"]
    assert not out["findings"][1]["uncertain"] and out["findings"][1]["supported"]
    assert {d["drop_reason"] for d in out["dropped"]} == {"quote not found in the policy", "no valid DPDP section"}


def test_verifier_fails_open_on_bad_reply():
    out = verify([_finding()], POLICY, [], FakeLLM(["not json"]), 0)
    assert len(out["findings"]) == 1 and not out["findings"][0]["uncertain"] and out["error"]


# ----------------------------------------------------------------- tagger
def test_parse_tagger_reply_coerces_vocabulary():
    r = parse_tagger_reply('```json\n{"categories": ["data retention", "bogus"], "claims": ['
                           '{"category": "Third Party Sharing/Collection", "data_type": "location", '
                           '"does": "does not", "third_party": "named third party", "purpose": "advertising"},'
                           '{"category": "Policy Change"}]}\n```')
    assert r["categories"] == ["Data Retention", "Third Party Sharing/Collection"]
    assert r["claims"] == [{"category": "Third Party Sharing/Collection", "data_type": "Location",
                            "does": "Does Not", "third_party": "Named third party", "third_party_text": "",
                            "purpose": "Advertising", "retention": "", "audience": ""}]
    assert parse_tagger_reply("no json here")["parse_error"]


# --------------------------------------------------------------- end to end
def test_configs_are_switches_of_one_implementation():
    full = CONFIGS["full"]
    for name, field_, value in [("A1", "verifier", False), ("A2", "retrieval", False),
                                ("A3", "specialists", False), ("A4", "tagger", "prompted"),
                                ("A5", "tagger", "oracle")]:
        cfg = CONFIGS[name]
        assert getattr(cfg, field_) == value
        assert replace(cfg, name="full", **{field_: getattr(full, field_)}) == full
    with pytest.raises(ValueError):
        get_config("A9")


def test_run_case_end_to_end(tmp_path):
    app = tmp_path / "app"
    app.mkdir()
    (app / "dataflows.json").write_text(json.dumps([flow("f1", "Contact"),
                                                    flow("f2", "Location", "admob", "Advertising")]))
    (app / "build.gradle").write_text("dependencies {\n implementation 'com.google.android.gms:play-services-ads:23.0.0'\n}\n")
    case = {"case_id": "t1", "policy": POLICY, "app_dir": app}
    paragraphs = POLICY.split("\n\n")
    index = {para_hash(paragraphs[0]): {"claims": [claim(category="First Party Collection/Use",
                                                         data_type="Contact", does="Does",
                                                         purpose="Basic service/feature")]},
             para_hash(paragraphs[1]): {"claims": [claim(category="Third Party Sharing/Collection",
                                                         data_type="Generic personal information",
                                                         does="Does", third_party="Unnamed third party")]}}
    reviewer = FakeLLM([{"action": "final", "answers": [
        {"candidate_id": "c1", "disclosing_quote": "", "denial_quote": "",
         "generic_quote": "We may share information with our partners.", "sections": ["Sec. 5(1)"],
         "rationale": "partners is generic"}]}])
    verifier = FakeLLM([{"checks": [{"finding_id": 0, "supported": True}]}])
    out = run_case(case, reviewer, 0, get_config("full"), claims_index=index, verifier_llm=verifier)
    assert out["flow_labels"]["f1"]["label"] == "clear" and out["flow_labels"]["f2"]["label"] == "vague"
    assert [(f["data_type"], f["gap_type"], f["supported"]) for f in out["findings"]] == \
        [("Location", "undisclosed_sharing", True)]
    assert out["trace"]["llm_calls"] == 2 and out["trace"]["untagged_paragraphs"] == 1
    # an invented quote is not evidence: with nothing verified the flow is an omission, without a quote
    invented = {"action": "final", "answers": [{"candidate_id": "c1", "generic_quote": "We sell it to everyone.",
                                                "sections": ["Sec. 5(1)"]}]}
    out = run_case(case, FakeLLM([invented]), 0, get_config("A1"), claims_index=index)   # verifier off
    assert [(f["level"], f["evidence"]) for f in out["findings"]] == [("omission", "")]
    assert out["trace"]["llm_calls"] == 1 and out["flow_labels"]["f2"]["label"] == "omitted"


def test_prompts_never_contain_case_id(tmp_path):
    """The case id names the case kind ("_control", "_v1"); no prompt may contain it."""
    app = tmp_path / "app"
    app.mkdir()
    (app / "dataflows.json").write_text(json.dumps([flow("f1", "Health"), flow("f2", "Location", "admob",
                                                                                "Advertising")]))
    case = {"case_id": "1028_control", "policy": POLICY, "app_dir": app}
    reviewer = FakeLLM([{"action": "tool", "tool": "search_policy", "query": "x"}] * 2 + [
        {"action": "final", "decisions": [{"candidate_id": "c1", "is_gap": True, "level": "omission",
                                           "sections": ["Sec. 5(1)"], "evidence": ""}]}] * 3)
    verifier = FakeLLM([{"checks": [{"finding_id": 0, "supported": True}]}])
    run_case(case, reviewer, 0, get_config("full"), claims_index={}, verifier_llm=verifier)
    prompts = reviewer.prompts + verifier.prompts
    assert prompts and not any("1028" in p or "control" in p.lower() for p in prompts)
    from dpdp_audit import baselines
    (app / "build.gradle").write_text("dependencies {}\n")
    assert "1028" not in baselines.prompt_b1(case)


def test_verifier_snaps_near_verbatim_quotes_and_strips_prefixes():
    from dpdp_audit.pipeline.verifier import snap_quote
    policy = "Intro.\n\nWe may share information with our trusted partners for advertising purposes. Other text."
    assert quote_in("P2 We may share information with our trusted partners for advertising purposes.", policy)
    snapped = snap_quote("We may share your information with our trusted partners for advertising.", policy)
    assert snapped == "We may share information with our trusted partners for advertising purposes."
    assert snap_quote("We sell data to brokers for money every day.", policy) is None
    out = verify([_finding(evidence="We may share your information with our trusted partners for advertising.")],
                 policy, [], FakeLLM([{"checks": [{"finding_id": 0, "supported": True}]}]), 0)
    assert out["findings"][0]["evidence_snapped"] and out["findings"][0]["evidence"] in policy
    omit = verify([_finding(level="omission", evidence="an invented sentence that is not there")], policy, [],
                  FakeLLM([{"checks": [{"finding_id": 0, "supported": True}]}]), 0)
    assert omit["findings"][0]["evidence"] == "" and omit["findings"][0]["evidence_removed"]


def test_decide_follows_verified_quotes():
    from dpdp_audit.pipeline.decide import derive
    policy = ("We collect your email address and phone number to run your account. "
              "We may share information with our partners. We do not share your location with third parties. "
              "We share your location with Google to show ads. We keep data only as long as necessary.")
    coll = dict(_cand(gap="undisclosed_collection", d="Contact"), recipient="first_party")
    share = _cand(d="Location")
    assert not derive(coll, {"disclosing_quote": "We collect your email address and phone number to run your "
                                                 "account."}, policy)["is_gap"]
    # a "disclosing" quote that does not name the data type does not count
    d = derive(coll, {"disclosing_quote": "We may share information with our partners."}, policy)
    assert (d["is_gap"], d["level"]) == (True, "omission")
    assert derive(share, {"denial_quote": "We do not share your location with third parties."}, policy)["level"] \
        == "explicit"
    assert not derive(share, {"disclosing_quote": "We share your location with Google to show ads."}, policy)["is_gap"]
    assert derive(share, {"generic_quote": "We may share information with our partners."}, policy)["level"] == "vague"
    assert derive(share, {"generic_quote": "Invented text that is nowhere."}, policy)["level"] == "omission"
    # a sentence naming the data type counts as disclosure even when filed as "generic"
    assert not derive(coll, {"generic_quote": "We collect your email address and phone number to run your "
                                              "account."}, policy)["is_gap"]
    ret = dict(_cand(gap="retention_mismatch", d="Contact"), recipient="first_party")
    assert derive(ret, {"retention_quote": "We keep data only as long as necessary.", "retention": "limited"},
                  policy)["level"] == "explicit"
    kids = _cand(gap="childrens_data", d="IP address and device IDs")
    assert derive(kids, {"children_quote": ""}, policy)["level"] == "omission"


def test_reviewer_prompt_explains_data_types():
    prompt = rv.build_prompt("notice", [_cand(d="Contact")], {1: "x"}, facts([]), [], rv.Tools(POLICY, True, 3),
                             get_config("full"))
    assert "email address" in prompt and "purpose \"Advertising\"" in prompt


# ------------------------------------------------------------------- v2
def test_v2_verifier_checks_only_chosen_gap_types():
    findings = [_finding(gap_type="childrens_data", level="omission", evidence=""),
                _finding(gap_type="undisclosed_collection", data_type="Contact")]
    llm = FakeLLM([{"checks": [{"finding_id": 0, "supported": False}]}])
    out = verify(findings, POLICY, [], llm, 0, llm_gaps=("undisclosed_collection", "purpose_mismatch"))
    kids, coll = out["findings"]
    assert not kids["uncertain"] and kids["supported"] is None        # not sent to the model
    assert coll["uncertain"] and coll["supported"] is False           # finding_id 0 is the collection one
    assert "childrens_data" not in llm.prompts[0]
    # nothing of the chosen types: no LLM call at all
    llm2 = FakeLLM([])
    assert verify(findings[:1], POLICY, [], llm2, 0, llm_gaps=("purpose_mismatch",))["llm_calls"] == 0
    assert llm2.prompts == []


def test_v2_purpose_quote_counts_by_paragraph():
    from dpdp_audit.pipeline.decide import derive
    policy = "We ask for your email address when you register. This information is used to measure use of the site."
    cand = dict(_cand(gap="purpose_mismatch", d="Contact"), recipient="first_party", purpose="Analytics/Research")
    raw = {"purpose_quote": "This information is used to measure use of the site."}
    assert derive(cand, raw, policy)["is_gap"]                                   # frozen rule: sentence only
    assert not derive(cand, raw, policy, purpose_paragraph=True)["is_gap"]       # v2: its paragraph names email
    other = "We ask for your email address when you register.\n\nThis information is used to measure use."
    assert derive(cand, {"purpose_quote": "This information is used to measure use."}, other,
                  purpose_paragraph=True)["is_gap"]                              # another paragraph: still a gap


def test_v2_finder_purpose_switches():
    paras = [Paragraph(0, "a", [claim(category="First Party Collection/Use", data_type="Generic personal information",
                                      does="Does", purpose="Basic service/feature")])]
    fl = [flow("f1", "Contact", purpose="Advertising")]
    base = find_candidates(paras, facts(fl), POLICY)
    assert [c["gap_type"] for c in base] == ["undisclosed_collection"]
    both = find_candidates(paras, facts(fl), POLICY, purpose_always=True)
    assert [c["gap_type"] for c in both] == ["undisclosed_collection", "purpose_mismatch"]
    assert both[1]["reviewer"] == "purpose"


def test_v2_configs_leave_frozen_configs_unchanged():
    full = CONFIGS["full"]
    assert full.llm_check_gaps is None and not full.purpose_paragraph and not full.purpose_search
    assert not full.purpose_always and full.review_batch == 0 and full.max_paragraphs == 8
    assert CONFIGS["v2_read"].max_paragraphs == 16 and CONFIGS["v2_batch"].review_batch == 1


def test_v2_retention_quote_must_be_about_keeping_data():
    from dpdp_audit.pipeline.decide import derive
    policy = ("We collect this information in the following ways: forms and cookies. "
              "Usage logs are kept indefinitely. We keep your account data while your account is open.")
    ret = dict(_cand(gap="retention_mismatch", d="Contact"), recipient="first_party", retention="Indefinitely")
    echo = {"retention_quote": "We collect this information in the following ways: forms and cookies.",
            "retention": "indefinitely"}
    assert not derive(ret, echo, policy)["is_gap"]                              # frozen rule is fooled
    assert derive(ret, echo, policy, retention_check=True)["level"] == "omission"  # not about retention
    limited = {"retention_quote": "We keep your account data while your account is open.", "retention": "indefinitely"}
    assert derive(ret, limited, policy, retention_check=True)["is_gap"]         # says no "indefinitely"
    real = {"retention_quote": "Usage logs are kept indefinitely.", "retention": "indefinitely"}
    assert not derive(ret, real, policy, retention_check=True)["is_gap"]


def test_full_v2_is_the_chosen_combination():
    v2 = CONFIGS["full_v2"]
    assert v2.llm_check_gaps == ("undisclosed_collection", "purpose_mismatch") and v2.purpose_paragraph
    assert v2.max_paragraphs == 16 and v2.purpose_search and v2.review_batch == 1 and v2.retention_check
    assert not v2.purpose_always and v2.tagger == "prompted"
    assert replace(CONFIGS["full_v2_finetuned"], name="full_v2", tagger="prompted") == v2


def test_v2_ablations_change_one_switch_of_full_v2_finetuned():
    base = CONFIGS["full_v2_finetuned"]
    for name, field_, value in [("A1_v2", "verifier", False), ("A2_v2", "retrieval", False),
                                ("A3_v2", "specialists", False), ("A5_v2", "tagger", "oracle")]:
        cfg = CONFIGS[name]
        assert getattr(cfg, field_) == value
        assert replace(cfg, name=base.name, **{field_: getattr(base, field_)}) == base
