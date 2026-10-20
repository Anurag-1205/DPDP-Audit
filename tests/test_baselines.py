from pathlib import Path

from dpdp_audit import baselines

APP = Path(__file__).parent / "fixtures" / "app_basic"
CASE = {"case_id": "t1", "policy": "We do not share your location with third parties.", "app_dir": APP}


def test_prompts_contain_inputs():
    assert "play-services-ads" in baselines.prompt_b1(CASE)
    p2 = baselines.prompt_b2(CASE)
    assert '"sdk_id": "admob"' in p2 and "Sec. 5" in p2


def test_normalise_drops_unknown_gap_types_and_defaults_labels():
    reply = {"flow_labels": {"f1": "incorrect"},
             "findings": [{"flow_id": "f1", "data_type": "Location", "gap_type": "undisclosed_sharing",
                           "level": "explicit", "sections": ["Sec. 5(1)"]},
                          {"gap_type": "made_up"}]}
    out = baselines.normalise(reply, ["f1", "f2"])
    assert len(out["findings"]) == 1
    assert out["flow_labels"]["f2"]["label"] == "clear"
