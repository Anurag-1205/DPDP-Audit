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


def test_tuple_f1():
    from dpdp_audit.tagger_eval import evaluate_tuples
    c1 = {"category": "Third Party Sharing/Collection", "data_type": "Location", "does": "Does",
          "third_party": "Named third party"}
    c2 = dict(c1, does="Does Not")
    gold = [{"policy_id": "1", "segment_id": 0, "claims": [c1]}]
    assert evaluate_tuples(gold, gold)["tuple_does"]["f1"] == 1.0
    r = evaluate_tuples(gold, [{"policy_id": "1", "segment_id": 0, "claims": [c2]}])
    assert r["tuple_does"]["f1"] == 0.0 and r["tuple_third_party"]["f1"] == 1.0


def test_claims_training_data_is_disjoint_from_heldout():
    import pytest
    from dpdp_audit.opp115 import OPP_DIR
    if not OPP_DIR.exists():
        pytest.skip("OPP-115 not downloaded")
    from dpdp_audit.split import load_split
    from dpdp_audit.tagger_data import claims_examples
    train, held = claims_examples("train"), claims_examples("heldout")
    split = load_split()
    train_ids = {p.split("_")[0] for p in split["train"]}
    held_ids = {p.split("_")[0] for p in split["heldout"]}
    assert {r["policy_id"] for r in train} <= train_ids
    assert {r["policy_id"] for r in held} <= held_ids
    assert not ({r["policy_id"] for r in train} & {r["policy_id"] for r in held})
    assert len(held) == 1140 and all(r["claims"] or r["categories"] for r in train)
