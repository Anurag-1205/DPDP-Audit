from dpdp_audit import real_flow_score as rf

KEYS = [{"case_id": "a", "flow_labels": {"f1": "clear", "f2": "vague"}},
        {"case_id": "b", "flow_labels": {"f1": "clear", "f2": "omitted"}}]
OUTS = [{"flow_labels": {"f1": {"label": "vague"}, "f2": {"label": "vague"}}},
        {"flow_labels": {"f2": {"label": "omitted"}}}]          # b/f1 missing -> clear


def test_missing_flow_counts_as_clear():
    assert rf.flow_pairs(KEYS, OUTS) == [("clear", "vague"), ("vague", "vague"),
                                         ("clear", "clear"), ("omitted", "omitted")]


def test_accuracies_and_false_alarm():
    assert rf.label_accuracy(KEYS, OUTS) == 0.75
    assert rf.gap_accuracy(KEYS, OUTS) == 0.75
    assert rf.flow_false_alarm(KEYS, OUTS) == 0.5      # one of the two clear flows got a gap


def test_kappa_known_values():
    assert rf.cohen_kappa(["x", "y"], ["x", "y"]) == 1.0
    # po = 0.5, pe = 0.5 -> 0
    assert rf.cohen_kappa(["x", "x", "y", "y"], ["x", "y", "x", "y"]) == 0.0


def test_labeller_agreement():
    lab = {"n": {("a", "f1"): "clear", ("a", "f2"): "vague", ("b", "f1"): "clear", ("b", "f2"): "omitted"}}
    r = rf.labeller_agreement(KEYS, OUTS, lab)["n"]
    assert r["n"] == 4 and r["agreement"] == 0.75


def test_confusion_counts():
    c = rf.confusion(KEYS, OUTS)
    assert c["clear"]["vague"] == 1 and c["clear"]["clear"] == 1 and c["omitted"]["omitted"] == 1
