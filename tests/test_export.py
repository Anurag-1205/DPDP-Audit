import csv
from pathlib import Path

from dpdp_audit.export_policheck import export, package_name

APP = Path(__file__).parent / "fixtures" / "app_basic"


def test_export_writes_policheck_format(tmp_path):
    case = {"case_id": "1017_demo_v1", "policy": "We collect your location.", "app_dir": APP}
    cov = export([case], tmp_path)
    rows = list(csv.DictReader((tmp_path / "flows.csv").open()))
    assert rows[0]["data_type"] == "geolatlon" and rows[0]["dest_domain"] == "googleads.g.doubleclick.net"
    assert rows[1]["data_type"] == "email"          # Contact -> email (approximate)
    assert (tmp_path / "plaintext_policies" / f"{package_name('1017_demo_v1')}.txt").exists()
    assert cov == {"flows": 2, "exported": 2, "exact": 1, "approximate": 1,
                   "share_exported": 1.0, "share_exact": 0.5}
