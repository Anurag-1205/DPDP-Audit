import csv

from dpdp_audit.tool_runs import policheck_outputs


def test_policheck_rows_map_back_to_flows(tmp_path):
    with (tmp_path / "flow_index.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["package_name", "case_id", "flow_id", "opp115_type", "policheck_token", "dest_domain"])
        w.writerow(["com.x", "c1", "f1", "Location", "geolatlon", "api.c1.dpdpaudit.com"])
        w.writerow(["com.x", "c1", "f2", "Location", "geolatlon", "googleads.g.doubleclick.net"])
        w.writerow(["com.x", "c1", "f3", "Contact", "email", "api.c1.dpdpaudit.com"])
    results = tmp_path / "policheck_results.csv"
    with results.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["packageName", "flowEntity", "flowData", "consistencyResult"])
        w.writerow(["com.x", "we", "geographical location", "clear"])
        w.writerow(["com.x", "google ads", "geographical location", "ambiguous"])
    out = policheck_outputs(tmp_path, results)["c1"]
    labels = {k: v["native"] for k, v in out["flow_labels"].items()}
    assert labels == {"f1": "clear", "f2": "ambiguous", "f3": "omitted"}
    assert [(f["flow_id"], f["level"]) for f in out["findings"]] == [("f2", "explicit"), ("f3", "omission")]


def test_poligraph_rows_map_back_to_flows(tmp_path):
    from dpdp_audit.tool_runs import poligraph_outputs
    with (tmp_path / "flow_index.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["package_name", "case_id", "flow_id", "opp115_type", "policheck_token", "dest_domain"])
        w.writerow(["com.x", "c1", "f1", "Location", "geolatlon", "api.c1.dpdpaudit.com"])
        w.writerow(["com.x", "c1", "f2", "Location", "geolatlon", "googleads.g.doubleclick.net"])
        w.writerow(["com.x", "c1", "f3", "Contact", "email", "googleads.g.doubleclick.net"])
    results = tmp_path / "poligraph_results.csv"
    with results.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["app_id", "data_type", "dest_entity", "policheck_consistency", "purposes"])
        w.writerow(["com.x", "geolocation", "we", "clear", "services"])
        w.writerow(["com.x", "geolocation", "google", "clear", "advertising"])
        w.writerow(["com.x", "geolocation", "google", "vague", "advertising"])   # the worst label wins
    out = poligraph_outputs(tmp_path, results)["c1"]
    labels = {k: v["label"] for k, v in out["flow_labels"].items()}
    assert labels == {"f1": "clear", "f2": "vague", "f3": "omitted"}
    assert out["flow_labels"]["f2"]["purposes"] == "advertising"
    assert not out["flow_labels"]["f3"]["matched"]
    assert [(f["flow_id"], f["gap_type"], f["level"]) for f in out["findings"]] == \
        [("f2", "undisclosed_sharing", "vague"), ("f3", "undisclosed_sharing", "omission")]
