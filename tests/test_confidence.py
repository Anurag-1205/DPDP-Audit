"""Per-flow confidence over seeds (AC-04.13)."""
from dpdp_audit.confidence import combine, flow_votes


def test_majority_and_agreement():
    r = combine([("vague", 0.9), ("vague", 0.7), ("clear", 0.99)])
    assert r["label"] == "vague" and abs(r["agreement"] - 2 / 3) < 1e-9 and abs(r["token_prob"] - 0.8) < 1e-9


def test_three_way_tie_is_broken_by_probability_then_label_order():
    assert combine([("vague", 0.6), ("clear", 0.9), ("omitted", 0.8)])["label"] == "clear"
    assert combine([("omitted", None), ("vague", None), ("incorrect", None)])["label"] == "vague"


def test_pipeline_flows_use_their_reply_probability_and_baselines_the_case_reply():
    pipeline = {"trace": {}, "token_prob": 0.5,
                "flow_labels": {"f1": {"label": "vague", "confidence": 0.8}, "f2": {"label": "clear", "confidence": None}}}
    assert flow_votes(pipeline) == {"f1": ("vague", 0.8), "f2": ("clear", None)}
    baseline = {"token_prob": 0.7, "flow_labels": {"f1": {"label": "omitted", "confidence": None}}}
    assert flow_votes(baseline) == {"f1": ("omitted", 0.7)}
