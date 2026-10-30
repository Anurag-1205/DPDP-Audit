"""Baselines built from the pipeline's parts (30 Oct): R0 rules only, B5 one call, *_sc self-consistency."""
import json
import sys
from pathlib import Path

import pytest

from dpdp_audit.pipeline import get_config
from dpdp_audit.pipeline.claims import para_hash
from dpdp_audit.pipeline.finder import all_candidates
from dpdp_audit.pipeline.run import run_case
from test_pipeline import POLICY, FakeLLM, claim, facts, flow, no_embeddings  # noqa: F401 (fixture)

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from build_self_consistency import majority_findings  # noqa: E402


class NoLLM:
    model = "none"

    def complete(self, *a, **k):
        raise AssertionError("R0 must not call an LLM")


def make_case(tmp_path, flows, child=False):
    app = tmp_path / "app"
    app.mkdir()
    (app / "dataflows.json").write_text(json.dumps(flows))
    (app / "build.gradle").write_text("dependencies {\n implementation 'com.google.android.gms:play-services-ads:23.0.0'\n}\n")
    if child:
        (app / "AndroidManifest.xml").write_text('<manifest><application android:label="Kids"/></manifest>')
    return {"case_id": "t1", "policy": POLICY, "app_dir": app}


def test_all_candidates_follow_the_app_facts_only():
    fl = [flow("f1", "Contact", retention="Indefinitely"), flow("f2", "Location", "admob", "Advertising")]
    got = [(c["flow_id"], c["gap_type"]) for c in all_candidates(facts(fl, child=True))]
    assert got == [("f1", "undisclosed_collection"), ("f1", "purpose_mismatch"), ("f1", "retention_mismatch"),
                   ("f2", "undisclosed_sharing"), ("f2", "purpose_mismatch"), ("f2", "childrens_data")]
    assert all(c["suggested_level"] is None and c["paragraphs"] == [] for c in all_candidates(facts(fl)))


def test_r0_reports_every_candidate_without_an_llm(tmp_path):
    case = make_case(tmp_path, [flow("f1", "Contact"), flow("f2", "Location", "admob", "Advertising")])
    index = {para_hash(POLICY.split("\n\n")[0]): {"claims": [claim(category="First Party Collection/Use",
                                                                   data_type="Contact", does="Does",
                                                                   purpose="Basic service/feature")]}}
    out = run_case(case, NoLLM(), 0, get_config("R0"), claims_index=index)
    assert [(f["data_type"], f["gap_type"], f["level"]) for f in out["findings"]] == \
        [("Location", "undisclosed_sharing", "omission")]
    assert out["findings"][0]["sections"] and out["flow_labels"]["f2"]["label"] == "omitted"
    assert out["flow_labels"]["f1"]["label"] == "clear" and out["trace"]["llm_calls"] == 0


def test_b5_reads_the_whole_policy_in_one_call(tmp_path):
    case = make_case(tmp_path, [flow("f1", "Contact"), flow("f2", "Location", "admob", "Advertising")])
    reviewer = FakeLLM([{"action": "final", "answers": [
        {"candidate_id": "c1", "disclosing_quote": "We collect your email address to create your account.",
         "denial_quote": "", "generic_quote": "", "sections": ["Sec. 5(1)"], "rationale": "named"},
        {"candidate_id": "c2", "purpose_quote": "We collect your email address to create your account.",
         "unspecified_purpose_quote": "", "only_unspecified_purposes": False, "sections": ["Sec. 5(1)"],
         "rationale": "account"},
        {"candidate_id": "c3", "disclosing_quote": "", "denial_quote": "",
         "generic_quote": "We may share information with our partners.", "sections": ["Sec. 5(1)"],
         "rationale": "generic"},
        {"candidate_id": "c4", "purpose_quote": "", "unspecified_purpose_quote": "",
         "only_unspecified_purposes": True, "sections": ["Sec. 5(1)"], "rationale": "none"}]}])
    verifier = FakeLLM([{"checks": [{"finding_id": 0, "supported": True}]}])
    out = run_case(case, reviewer, 0, get_config("B5"), claims_index={}, verifier_llm=verifier)
    assert len(reviewer.prompts) == 1   # one call, no tools
    prompt = reviewer.prompts[0]
    assert all(f"[P{i}] " in prompt for i in range(3)) and "search_policy" not in prompt
    assert "Relevant DPDP text:\n(not provided)" in prompt
    # the purpose finding of f2 is dropped because its notice gap stands (aggregator rule kept)
    assert [(f["data_type"], f["gap_type"], f["level"]) for f in out["findings"]] == \
        [("Location", "undisclosed_sharing", "vague")]
    assert out["trace"]["paragraphs_shown"] == [3] and out["trace"]["paragraphs_total"] == 3


def test_self_consistency_keeps_findings_of_most_seeds():
    f = lambda d, g, lvl, ev="": {"flow_id": "f1", "data_type": d, "gap_type": g, "level": lvl, "evidence": ev,
                                  "sections": ["Sec. 5(1)"]}
    runs = [{"findings": [f("Contact", "undisclosed_collection", "vague", "a"), f("Location", "purpose_mismatch", "omission")]},
            {"findings": [f("Contact", "undisclosed_collection", "omission", "b")]},
            {"findings": [f("Contact", "undisclosed_collection", "omission", "c")]}]
    got = majority_findings(runs)
    assert len(got) == 1 and got[0]["level"] == "omission" and got[0]["evidence"] == "b" and got[0]["votes"] == 3


def test_robust_reviewer_reader_keeps_complete_answers():
    from dpdp_audit.pipeline.reviewers import parse_reply_robust
    cut = '{"action": "final", "answers": [{"candidate_id": "c1", "x": "a\\\'b"}, {"candidate_id": "c2"}, {"candidate_id": "c3", "disc'
    reply, mode = parse_reply_robust(cut)
    assert mode == "salvaged" and [a["candidate_id"] for a in reply["answers"]] == ["c1", "c2"]
    two = '{"action": "final", "answers": [{"candidate_id": "c1"}]}\n{"action": "final", "answers": [{"candidate_id": "c2"}]}'
    assert [a["candidate_id"] for a in parse_reply_robust(two)[0]["answers"]] == ["c1", "c2"]
    assert parse_reply_robust('{"action": "final", "answers": []}')[1] == "json"
    with pytest.raises(ValueError):
        parse_reply_robust("I cannot answer.")
