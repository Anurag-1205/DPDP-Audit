import json

from dpdp_audit.paths import DATA


def load():
    with (DATA / "dpdp" / "sections.jsonl").open() as f:
        return {r["id"]: r for r in map(json.loads, f)}


def test_key_units_present():
    units = load()
    for cid in ["Sec. 5(1)", "Sec. 6(1)", "Sec. 8(7)", "Sec. 9(3)", "Rule 3", "Rule 8", "Rule 10", "Third Schedule"]:
        assert cid in units, cid


def test_rule3_requires_itemised_notice():
    assert "itemised description" in load()["Rule 3"]["text"]


def test_children_no_targeted_ads():
    assert "targeted advertising" in load()["Sec. 9(3)"]["text"]
