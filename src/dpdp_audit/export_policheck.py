"""Export benchmark cases in the input format PoliCheck (and PoliGraph) read.

  <out>/plaintext_policies/<package>.txt
  <out>/flows.csv   package_name,app_name,version_name,version_code,data_type,
                    dest_domain,dest_ip,arb_number,privacy_policy
  <out>/flow_index.csv  maps each exported row back to (case_id, flow_id)
  <out>/coverage.json   share of collection/sharing flows the mapping can express

Only collection and sharing flows are exported: those are the gap types the
tools model. First-party flows go to a domain owned by the app itself.
"""
from __future__ import annotations

import csv
import json
import re
from functools import lru_cache
from pathlib import Path

from .paths import DATA
from .tools import get_flows


@lru_cache(maxsize=1)
def datatype_map() -> dict[str, dict]:
    with (DATA / "tools" / "datatype_mapping.csv").open() as f:
        return {r["opp115_type"]: r for r in csv.DictReader(f)}


@lru_cache(maxsize=1)
def sdk_domains() -> dict[str, str]:
    with (DATA / "tools" / "sdk_domains.csv").open() as f:
        return {r["sdk_id"]: r["domain"] for r in csv.DictReader(f)}


def package_name(case_id: str) -> str:
    return "com.dpdpaudit." + re.sub(r"[^a-z0-9]+", "_", case_id.lower()).strip("_")


def first_party_domain(case_id: str) -> str:
    return f"api.{re.sub(r'[^a-z0-9]+', '', case_id.lower())}.dpdpaudit.com"


def export(cases: list[dict], out_dir: Path) -> dict:
    pol_dir = out_dir / "plaintext_policies"
    pol_dir.mkdir(parents=True, exist_ok=True)
    rows, index = [], []
    n_flows = n_exact = n_approx = 0
    for case in cases:
        pkg = package_name(case["case_id"])
        (pol_dir / f"{pkg}.txt").write_text(case["policy"])
        for flow in get_flows(case["app_dir"]):
            n_flows += 1
            m = datatype_map().get(flow["data_type"], {"quality": "none", "policheck_token": ""})
            if m["quality"] == "none":
                continue
            n_exact += m["quality"] == "exact"
            n_approx += m["quality"] == "approximate"
            if flow["recipient"] == "first_party":
                domain = first_party_domain(case["case_id"])
            else:
                domain = sdk_domains().get(flow["recipient"], f"{flow['recipient']}.example.com")
            rows.append([pkg, case["case_id"], "1.0", "1", m["policheck_token"], domain, "", "1",
                         f"https://{first_party_domain(case['case_id'])}/privacy"])
            index.append([pkg, case["case_id"], flow["flow_id"], flow["data_type"], m["policheck_token"], domain])
    with (out_dir / "flows.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["package_name", "app_name", "version_name", "version_code", "data_type",
                    "dest_domain", "dest_ip", "arb_number", "privacy_policy"])
        w.writerows(rows)
    with (out_dir / "flow_index.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["package_name", "case_id", "flow_id", "opp115_type", "policheck_token", "dest_domain"])
        w.writerows(index)
    coverage = {"flows": n_flows, "exported": len(rows), "exact": n_exact, "approximate": n_approx,
                "share_exported": len(rows) / n_flows if n_flows else 0.0,
                "share_exact": n_exact / n_flows if n_flows else 0.0}
    (out_dir / "coverage.json").write_text(json.dumps(coverage, indent=1))
    return coverage
