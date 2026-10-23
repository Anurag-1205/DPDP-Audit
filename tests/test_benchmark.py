import pytest

from dpdp_audit.cases import BENCH, load_split
from dpdp_audit.gaps import GAP_TYPES, LABELS, LEVELS
from dpdp_audit.split import load_split as load_policy_split

pytestmark = pytest.mark.skipif(not (BENCH / "main").exists(), reason="benchmark not generated")


def test_controls_are_compliant_and_variants_have_gaps():
    cases, keys = load_split("main")
    assert len(cases) >= 100
    for k in keys:
        if k["kind"] == "control":
            assert k["findings"] == [] and set(k["flow_labels"].values()) == {"clear"}
        else:
            assert k["findings"], k["case_id"]


def test_keys_use_known_values():
    _, keys = load_split("main")
    for k in keys:
        assert set(k["flow_labels"].values()) <= set(LABELS)
        for f in k["findings"]:
            assert f["gap_type"] in GAP_TYPES and f["level"] in LEVELS and f["sections"]


def test_only_heldout_policies_are_used():
    held = {p.split("_")[0] for p in load_policy_split()["heldout"]}
    cases, _ = load_split("main")
    assert {c["policy_id"] for c in cases} <= held


def test_case_folders_do_not_leak_the_answer():
    for c, _ in zip(*load_split("main")):
        assert set(c) >= {"case_id", "policy_id"} and "kind" not in c and "planted" not in c
