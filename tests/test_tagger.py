from dpdp_audit.tagger_eval import evaluate


def test_perfect_and_missing_predictions():
    gold = [{"policy_id": "1", "segment_id": 0, "categories": ["Data Retention"]},
            {"policy_id": "1", "segment_id": 1, "categories": ["Data Security", "Other"]}]
    perfect = evaluate(gold, gold)
    assert perfect["per_category"]["Data Retention"]["f1"] == 1.0
    assert perfect["micro_f1"] == 1.0
    # a segment with no prediction predicts nothing: recall drops, no false positives
    half = evaluate(gold, gold[:1])
    assert half["per_category"]["Data Security"]["recall"] == 0.0
    assert half["per_category"]["Data Retention"]["f1"] == 1.0
    assert half["n_predicted"] == 1


def test_false_positive_counts():
    gold = [{"policy_id": "1", "segment_id": 0, "categories": ["Other"]}]
    pred = [{"policy_id": "1", "segment_id": 0, "categories": ["Other", "Policy Change"]}]
    r = evaluate(gold, pred)
    assert r["per_category"]["Policy Change"]["precision"] == 0.0
    assert r["per_category"]["Other"]["f1"] == 1.0
