"""Vagueness ladder: pure insertion, identical apps, expected labels (AC-06.1, 06.3, 06.4)."""
import json
from collections import defaultdict

import pytest

from dpdp_audit.cases import BENCH, case_dirs, load_case, load_key
from dpdp_audit.ladder import insert, mcnemar, score_ladder

LADDER = BENCH / "ladder"
pytestmark = pytest.mark.skipif(not (LADDER / "cases").exists(), reason="ladder not built")
GOLD = {"clear": "clear", "explicit": "incorrect", "vague": "vague", "deleted": "omitted"}


def ladders():
    out = defaultdict(dict)
    for d in case_dirs("ladder"):
        case = load_case(d)
        key = load_key("ladder", case["case_id"])
        out[key["ladder_id"]][key["rung"]] = (case, key)
    return out


def test_size_and_kinds():
    lad = ladders()
    assert len(lad) == 35 and all(len(r) == 4 for r in lad.values())
    kinds = [next(iter(r.values()))[1]["ladder_kind"] for r in lad.values()]
    assert kinds.count("sharing") == 23 and kinds.count("collection") == 12


def test_rungs_differ_from_base_by_one_inserted_sentence():
    for lid, rungs in ladders().items():
        base = rungs["deleted"][0]["policy"]
        for rung in ("clear", "explicit", "vague"):
            case, key = rungs[rung]
            text, sentence = case["policy"], key["inserted"]
            assert sentence and text.count(sentence) == 1, (lid, rung)
            i = text.index(sentence)
            before = " " if i > 0 and text[i - 1] == " " and base[i - 1:i] != " " else ""
            assert text[: i - len(before)] + text[i + len(sentence) + 1:] == base, (lid, rung)
        positions = {rungs[r][0]["policy"].index(rungs[r][1]["inserted"]) for r in ("clear", "explicit", "vague")}
        assert len(positions) == 1, lid                       # the same position on every rung


def test_app_identical_across_rungs():
    for lid, rungs in ladders().items():
        apps = {tuple((p.name, p.read_text()) for p in sorted(c["app_dir"].iterdir())) for c, _ in rungs.values()}
        assert len(apps) == 1, lid


def test_gold_labels_follow_the_rung():
    for rungs in ladders().values():
        for rung, (_, key) in rungs.items():
            assert key["flow_labels"]["f1"] == GOLD[rung]
            assert bool(key["findings"]) == (rung != "clear")


def test_check_sheet_and_export_cover_every_rung():
    import csv
    rows = list(csv.DictReader((LADDER / "check_sheet.csv").open()))
    assert len(rows) == 140 and {r["case_id"] for r in rows} == {d.name for d in case_dirs("ladder")}
    cov = json.loads((LADDER / "export" / "policheck" / "coverage.json").read_text())
    assert cov["exported"] == 140


def test_insert_helper():
    assert insert(["A. B."], (0, 3), "X.") == ["A. X. B."]
    assert insert(["", "A."], None, "X.") == ["", "A. X. "]
    assert insert(["A."], (0, 1), "") == ["A."]


def test_score_ladder_and_mcnemar():
    keys = [{"case_id": f"L1_{r}", "ladder_id": "L1", "rung": r, "flow_labels": {"f1": g}}
            for r, g in GOLD.items()]
    outs = [{"flow_labels": {"f1": {"label": g}}} for g in ("clear", "incorrect", "clear", "omitted")]
    s = score_ladder(keys, outs)
    assert s["accuracy"] == {"clear": 1.0, "explicit": 1.0, "vague": 0.0, "deleted": 1.0}
    assert s["paired"]["explicit_vs_vague"]["only_first_correct"] == 1
    assert s["confusion"]["vague"]["clear"] == 1
    assert mcnemar([True] * 10, [False] * 10)["p_value"] < 0.01


def test_accepted_rungs_use_the_joint_settlement(tmp_path, monkeypatch):
    import csv
    from dpdp_audit import ladder
    d = tmp_path / "ladder"; d.mkdir()
    rows = [("L1_r1", "ok", "ok"), ("L1_r2", "ok", "no"), ("L1_r3", "no", "ok"), ("L1_r4", "no", "no")]
    with (d / "check_sheet.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["case_id", "checker_1_ok", "checker_2_ok"]); w.writerows(rows)
    monkeypatch.setattr(ladder, "BENCH", tmp_path)
    assert ladder.accepted_cases() == {"L1_r1"}                       # disagreements count as rejected
    with (d / "disagreements.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["case_id", "agreed"]); w.writerows([("L1_r2", "ok"), ("L1_r3", "")])
    assert ladder.accepted_cases() == {"L1_r1", "L1_r2"}              # settled ok; L1_r3 still open
    assert ladder.check_status() == {"rungs": 4, "checkers_agree": 2, "disagreements": 2, "settled": 1, "unsettled": 1}


def test_rung_accuracy_interval_resamples_ladders():
    from dpdp_audit.ladder import accuracy_ci
    by_ladder = {f"L{i}": {"clear": True, "explicit": i % 2 == 0} for i in range(20)}
    ci = accuracy_ci(by_ladder, n=200)
    assert ci["clear"] == [1.0, 1.0]
    assert ci["explicit"][0] < 0.5 < ci["explicit"][1]
    assert ci["vague"] is None
