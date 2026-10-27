from dpdp_audit import score


def key(case_id, policy, kind, findings, labels=None):
    return {"case_id": case_id, "policy_id": policy, "kind": kind, "findings": findings,
            "flow_labels": labels or {}, "flow_gap_types": {}}


def gap(dt, gt, lvl, flow="f1"):
    return {"flow_id": flow, "data_type": dt, "gap_type": gt, "level": lvl, "sections": ["Sec. 5(1)"]}


KEYS = [
    key("p1_c", "p1", "control", [], {"f1": "clear"}),
    key("p1_v", "p1", "variant", [gap("Location", "undisclosed_sharing", "explicit")], {"f1": "incorrect"}),
    key("p2_c", "p2", "control", [], {"f1": "clear"}),
    key("p2_v", "p2", "variant", [gap("Contact", "undisclosed_collection", "vague")], {"f1": "vague"}),
]


def out(findings, labels):
    return {"findings": findings, "flow_labels": {"f1": {"label": labels, "confidence": 1.0}}}


OUTS = [
    out([], "clear"),
    out([dict(gap("Location", "undisclosed_sharing", "explicit"), sections=["Sec. 6(1)"])], "incorrect"),
    out([dict(gap("Health", "undisclosed_collection", "omission"))], "clear"),   # false alarm
    out([dict(gap("Contact", "undisclosed_collection", "vague"), uncertain=True)], "clear"),  # uncertain -> not reported
]


def test_detection_counts():
    d = score.detection(KEYS, OUTS)["overall"]
    assert (d["tp"], d["fp"], d["fn"]) == (1, 1, 1)


def test_false_alarm_rate():
    s = score.safety(KEYS, OUTS)
    assert s["false_alarm_rate"] == 0.5 and s["n_uncertain"] == 1


def test_citation_and_labels():
    assert score.grounding(KEYS, OUTS)["citation_correct"] == 1.0
    assert score.label_macro_f1(KEYS, OUTS)["accuracy"] == 0.75


def test_native_reading_drops_vague():
    k, _ = score.native_reading(KEYS[3], OUTS[3])
    assert k["findings"] == []


def test_cluster_bootstrap_paired_difference_of_identical_systems_is_zero():
    ci = score.cluster_bootstrap(KEYS, OUTS, score.f1_metric, n=50, outs_b=OUTS)
    assert ci == {"point": 0.0, "lo": 0.0, "hi": 0.0}


def test_citation_check_normalises_subclauses():
    from dpdp_audit.gaps import citation_ok
    assert citation_ok("undisclosed_sharing", ["Rule 3(2)"])
    assert citation_ok("undisclosed_collection", ["Section 6(1)(d)"])
    assert citation_ok("retention_mismatch", ["Sec 8 (7)"])
    assert not citation_ok("retention_mismatch", ["Sec. 5(1)"])
    assert not citation_ok("childrens_data", ["Article 8 GDPR"])
