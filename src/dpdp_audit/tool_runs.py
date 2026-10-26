"""Run PoliCheck (Docker) on exported cases and convert its output.

PoliCheck labels convert one to one (proposal Sec. 5.3):
  incorrect / ambiguous -> explicit, vague -> vague, omitted -> omission, clear -> no finding.
Gap type follows the flow (first party -> collection, SDK -> sharing). Citations come from
the fixed gap-to-section table, so the tools are not penalised for citations they cannot produce.
"""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

from .gaps import gap_table
from .paths import RAW

REPO = RAW.parent / "external" / "PrivacyPolicyAnalysis"
IMAGE = "benandow/pol-analysis"
LABEL_TO_LEVEL = {"incorrect": "explicit", "ambiguous": "explicit", "vague": "vague", "omitted": "omission"}
# PoliCheck reports one row per matching policy statement; the worst label wins
SEVERITY = ["clear", "vague", "ambiguous", "incorrect", "omitted"]
# PoliCheck's own mapping from flow tokens to data-ontology terms (ConsistencyAnalysis.py)
POLICHECK_DATA_NAMES = {
    "aaid": "advertising identifier", "androidid": "android id", "geolatlon": "geographical location",
    "hwid": "serial number", "routerssid": "router ssid", "routermac": "mac address", "imei": "imei",
    "phone": "phone number", "email": "email address", "wifimac": "mac address",
    "package_dump": "application instal", "simid": "sim serial number", "real_name": "person name",
    "gsfid": "gsfid",
}


# PoliGraph's names for the same flow tokens (analyses/flow-consistency/convert_flow_csv.py)
POLIGRAPH_DATA_NAMES = {
    "aaid": "advertising id", "androidid": "android id", "geolatlon": "geolocation",
    "hwid": "serial number", "routerssid": "router ssid", "routermac": "mac address", "imei": "imei",
    "phone": "phone number", "email": "email address", "wifimac": "mac address",
    "package_dump": "package dump", "simid": "sim serial number", "real_name": "person name",
    "gsfid": "gsf id",
}


def prepare_ext(export_dir: Path, case_ids: list[str] | None, mode: str) -> Path:
    """Fill the tool's ext/ folder with the chosen cases."""
    ext = REPO / "ext"
    for sub in ("plaintext_policies", "output", "input", "datasets", "combined_tables"):
        shutil.rmtree(ext / sub, ignore_errors=True)
    (ext / "plaintext_policies").mkdir(parents=True)
    index = list(csv.DictReader((export_dir / "flow_index.csv").open()))
    keep = {r["package_name"] for r in index if case_ids is None or r["case_id"] in case_ids}
    for pkg in keep:
        shutil.copy(export_dir / "plaintext_policies" / f"{pkg}.txt", ext / "plaintext_policies" / f"{pkg}.txt")
    with (export_dir / "flows.csv").open() as fin, (ext / "data" / "flows.csv").open("w", newline="") as fout:
        rows = list(csv.reader(fin))
        w = csv.writer(fout)
        w.writerow(rows[0])
        w.writerows(r for r in rows[1:] if r[0] in keep)
    (ext / "run_config").write_text(mode)
    return ext


def run_docker(mode: str = "policheck", timeout: int = 6 * 3600) -> subprocess.CompletedProcess:
    if not (REPO / "ext" / "NlpFinalModel").exists():
        raise FileNotFoundError("PoliCheck NLP model missing: run scripts/tools/setup_policheck.sh")
    return subprocess.run(["docker", "run", "--rm", "-v", f"{REPO / 'ext'}:/ext", IMAGE],
                          capture_output=True, text=True, timeout=timeout)


def _first_party(dest_domain: str) -> bool:
    return dest_domain.endswith(".dpdpaudit.com")


def policheck_outputs(export_dir: Path, results: Path | None = None) -> dict[str, dict]:
    """Convert policheck_results.csv into one output per case.

    PoliCheck reports flows by resolved names: the data token is replaced by its ontology
    term (POLICHECK_DATA_NAMES) and the destination by an entity, "we" for the first party.
    Rows are matched on (package, data term, first party or not).
    """
    index = list(csv.DictReader((export_dir / "flow_index.csv").open()))
    worst: dict[tuple, str] = {}
    results = results or REPO / "ext" / "policheck_results.csv"
    for row in csv.DictReader(results.open()):
        key = (row["packageName"], row["flowData"], row["flowEntity"] == "we")
        label = row["consistencyResult"]
        if key not in worst or SEVERITY.index(label) > SEVERITY.index(worst[key]):
            worst[key] = label
    return _to_outputs(index, worst, POLICHECK_DATA_NAMES)


def poligraph_outputs(export_dir: Path, results: Path) -> dict[str, dict]:
    """Convert PoliGraph's poligraph_results.csv into one output per case.

    Uses the entity-sensitive `policheck_consistency` column (clear / vague / omitted;
    PoliGraph's flow check has no contradiction label). Rows are matched on (package,
    data term, first party or not); the purposes PoliGraph found are kept on each label.
    """
    index = list(csv.DictReader((export_dir / "flow_index.csv").open()))
    worst: dict[tuple, str] = {}
    purposes: dict[tuple, str] = {}
    for row in csv.DictReader(results.open()):
        key = (row["app_id"], row["data_type"], row["dest_entity"] == "we")
        label = row["policheck_consistency"]
        if key not in worst or SEVERITY.index(label) > SEVERITY.index(worst[key]):
            worst[key] = label
        purposes[key] = row.get("purposes", "")
    outs = _to_outputs(index, worst, POLIGRAPH_DATA_NAMES)
    for r in index:
        key = (r["package_name"], POLIGRAPH_DATA_NAMES[r["policheck_token"]], _first_party(r["dest_domain"]))
        outs[r["case_id"]]["flow_labels"][r["flow_id"]]["purposes"] = purposes.get(key, "")
    return outs


def _to_outputs(index: list[dict], worst: dict[tuple, str], data_names: dict[str, str]) -> dict[str, dict]:
    outs: dict[str, dict] = {}
    for r in index:
        out = outs.setdefault(r["case_id"], {"case_id": r["case_id"], "findings": [], "flow_labels": {}})
        key = (r["package_name"], data_names[r["policheck_token"]], _first_party(r["dest_domain"]))
        label = worst.get(key, "omitted")       # no row: the tool found no statement for the flow
        native = "incorrect" if label == "ambiguous" else label
        out["flow_labels"][r["flow_id"]] = {"label": native, "confidence": None, "native": label,
                                            "matched": key in worst}
        if label in LABEL_TO_LEVEL:
            gap = "undisclosed_collection" if "dpdpaudit.com" in r["dest_domain"] else "undisclosed_sharing"
            out["findings"].append({"flow_id": r["flow_id"], "data_type": r["opp115_type"], "gap_type": gap,
                                    "level": LABEL_TO_LEVEL[label], "sections": gap_table()[gap]["gold"],
                                    "evidence": "", "uncertain": False, "supported": None})
    return outs
