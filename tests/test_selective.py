"""Selective accuracy (SPEC-07)."""
import numpy as np

from dpdp_audit.selective import auc, bootstrap_r95, curve, review_needed, rung_confidence, summary


def flow(ok, agreement, prob=None, policy="p1", case="c", rung=None):
    return {"label": "vague", "gold": "vague" if ok else "clear", "agreement": agreement,
            "token_prob": prob, "policy_id": policy, "case_id": case, "rung": rung}


def test_known_r95_when_the_least_confident_flows_are_the_wrong_ones():
    # 20 flows, 2 wrong ones are the least confident: after reviewing 1 of 20 (5%), 1 wrong of 19
    # is left (94.7%); after 2 (10%) none is left
    rows = [flow(False, 1 / 3, 0.5), flow(False, 1 / 3, 0.6)] + [flow(True, 1.0, 0.9)] * 18
    share, acc = curve(rows)
    assert acc[0] == 0.9 and abs(acc[1] - 18 / 19) < 1e-12 and acc[2] == 1.0
    assert review_needed(share, acc) == 0.1
    s = summary(rows, match=0.9)
    assert s["r95"] == 0.1 and s["review_to_match"] == 0.0 and s["accuracy"] == 0.9


def test_probability_breaks_ties_inside_an_agreement_level():
    rows = [flow(True, 2 / 3, 0.4), flow(False, 2 / 3, 0.3), flow(True, 1.0, 0.1)]
    _, acc = curve(rows)
    assert acc[1] == 1.0          # the wrong flow (lower probability) is reviewed first


def test_ties_give_the_expected_curve_whatever_the_listing_order():
    a = [flow(True, 1.0), flow(False, 1.0), flow(True, 1.0), flow(True, 1.0)]
    _, acc = curve(a)
    _, acc_rev = curve(a[::-1])
    assert np.allclose(acc, acc_rev)
    # one group of 4 with 3 correct: reviewing 1 leaves 3 flows with 2.25 correct expected
    assert np.allclose(acc, [0.75, 0.75, 0.75, 0.75, 1.0])


def test_missing_probability_ranks_above_its_agreement_level():
    rows = [flow(True, 2 / 3, None), flow(False, 2 / 3, 0.99)]
    _, acc = curve(rows)
    assert acc[1] == 1.0          # the flow with a probability is reviewed first


def test_perfect_system_needs_no_review_and_has_auc_one():
    rows = [flow(True, 1.0, 0.9)] * 5
    share, acc = curve(rows)
    assert review_needed(share, acc) == 0.0 and abs(auc(share, acc) - 1.0) < 1e-12


def test_bootstrap_interval_contains_the_point_and_paired_difference_of_a_system_with_itself_is_zero():
    rows = [flow(i % 4 != 0, 1 / 3 if i % 4 == 0 else 1.0, policy=f"p{i % 5}") for i in range(40)]
    b = bootstrap_r95(rows, n=200)
    assert b["lo"] <= b["point"] <= b["hi"]
    d = bootstrap_r95(rows, n=200, rows_b=rows)
    assert d["point"] == d["lo"] == d["hi"] == 0.0


def test_rung_confidence_pairs_rungs_of_the_same_ladder():
    rows = [flow(True, 1.0, 0.9, case="L1_r2", rung="explicit"), flow(True, 1 / 3, 0.5, case="L1_r3", rung="vague"),
            flow(True, 1.0, 0.8, case="L2_r2", rung="explicit"), flow(True, 1.0, 0.8, case="L2_r3", rung="vague"),
            flow(True, 1.0, 0.8, case="L3_r2", rung="explicit")]          # L3 has no vague rung
    r = rung_confidence(rows, n=100)
    assert r["n_ladders"] == 2
    assert abs(r["agreement"]["mean_difference"] - (-1 / 3)) < 1e-12
    assert (r["agreement"]["lower"], r["agreement"]["equal"]) == (1, 1)
