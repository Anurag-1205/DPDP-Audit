"""Pick the real-flow sample and write it as benchmark cases (SPEC-08, AC-08.1; docs/stage-4-plan.md §2-3).

  python scripts/build_real_flows.py [--max-flows 80] [--per-app 4]

Reads data/real_flows/{apps.json, flows_raw.csv, policies/} (scripts/sample_real_flows.py).
A PoliCheck flow (app, data token, destination) becomes a benchmark flow when
- its token is in data/tools/real_token_mapping.csv (else dropped), and
- its destination is the app's own company (same registered domain as the policy URL, or a name in
  the package id) -> first_party, or a domain in data/tools/sdk_domains.csv -> that SDK
  (else dropped: the pipeline only knows SDKs in its table).
Flows are de-duplicated on (data type, recipient). Per app at most --per-app, preferring first-party,
then Location, then Contact; over --max-flows, apps with the most flows lose their last ones first.
Purpose and retention are unknown for real traffic ("Unspecified"), so only collection and sharing
are tested. Apps listed in data/real_flows/excluded.csv (with the reason) are left out, and each
policy loses the website text before its first paragraph about privacy or personal data (menus,
contact lines; plan step A3). Writes data/real_flows/sample.csv (with empty label columns for the two labellers) and
data/benchmark/real_flows/cases/ + export/policheck/. Answer keys are written later, from the
settled human labels only.
"""
import argparse
import csv
import json
import re
import shutil
from collections import Counter
from urllib.parse import urlparse

from dpdp_audit.cases import BENCH
from dpdp_audit.paths import DATA

SRC = DATA / "real_flows"
OUT = BENCH / "real_flows"
PRIORITY = {"Location": 1, "Contact": 2}
PERMISSIONS = {"Location": ["android.permission.ACCESS_FINE_LOCATION"],
               "Contact": ["android.permission.GET_ACCOUNTS"],
               "IP address and device IDs": ["android.permission.READ_PHONE_STATE",
                                             "com.google.android.gms.permission.AD_ID"]}
POLICY_START = re.compile(r"privacy|personal (data|information)", re.I)
GENERIC = {"com", "net", "org", "android", "app", "apps", "mobile", "www", "free", "game", "games"}
SAMPLE_COLUMNS = ["package", "flow_id", "data_type", "policheck_token", "recipient", "dest_domain",
                  "gap_type", "labeller_1_label", "labeller_1_note", "labeller_2_label", "labeller_2_note",
                  "settled_label", "settled_note"]


def registered(domain: str) -> str:
    parts = domain.lower().strip(".").split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else domain.lower()


def trim_chrome(text: str) -> str:
    """Drop the paragraphs before the first one about privacy or personal data (site menus)."""
    paras = [x for x in text.split("\n\n") if x.strip()]
    start = next((i for i, x in enumerate(paras) if POLICY_START.search(x)), 0)
    return "\n\n".join(paras[start:])


def recipient(package: str, policy_url: str, dest: str, sdk_by_domain: dict[str, str]) -> str | None:
    reg = registered(dest)
    if reg in sdk_by_domain:
        return sdk_by_domain[reg]
    own = registered(urlparse(policy_url).hostname or "")
    names = {p for p in package.lower().split(".") if p not in GENERIC and len(p) > 2}
    if reg == own or reg.split(".")[0] in names:
        return "first_party"
    return None


def pick(package: str, policy_url: str, rows: list[list[str]], tokens: dict[str, str],
         sdk_by_domain: dict[str, str], per_app: int) -> list[dict]:
    seen, flows = set(), []
    for r in rows:
        dtype = tokens.get(r[4])
        rec = recipient(package, policy_url, r[5], sdk_by_domain) if dtype else None
        if rec is None or (dtype, rec) in seen:
            continue
        seen.add((dtype, rec))
        flows.append({"package": package, "data_type": dtype, "policheck_token": r[4], "recipient": rec,
                      "dest_domain": r[5],
                      "gap_type": "undisclosed_collection" if rec == "first_party" else "undisclosed_sharing"})
    flows.sort(key=lambda f: (f["recipient"] != "first_party", PRIORITY.get(f["data_type"], 3),
                              f["data_type"], f["recipient"]))
    return flows[:per_app]


def trim(by_app: dict[str, list[dict]], max_flows: int) -> None:
    while sum(map(len, by_app.values())) > max_flows:
        pkg = max(sorted(by_app), key=lambda p: len(by_app[p]))
        by_app[pkg].pop()


def write_case(pkg: str, app: dict, flows: list[dict], policy: str, sdk_gradle: dict[str, str]) -> None:
    case = OUT / "cases" / pkg
    (case / "app").mkdir(parents=True, exist_ok=True)
    (case / "policy.txt").write_text(policy)
    (case / "meta.json").write_text(json.dumps({"case_id": pkg, "policy_id": pkg, "policy_name": pkg,
                                                "kind": "real", "policy_url": app["policy_url"],
                                                "snapshot": app["snapshot"]}, indent=1))
    (case / "app" / "dataflows.json").write_text(json.dumps(
        [{"data_type": f["data_type"], "recipient": f["recipient"], "purpose": "Unspecified",
          "retention": "Unspecified", "flow_id": f["flow_id"]} for f in flows], indent=1))
    deps = sorted({sdk_gradle[f["recipient"]] for f in flows if sdk_gradle.get(f["recipient"])})
    (case / "app" / "build.gradle").write_text(
        "plugins {\n    id 'com.android.application'\n}\n\ndependencies {\n"
        + "".join(f"    implementation '{d}'\n" for d in deps) + "}\n")
    perms = ["android.permission.INTERNET"] + sorted({p for f in flows for p in PERMISSIONS[f["data_type"]]})
    (case / "app" / "AndroidManifest.xml").write_text(
        f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{pkg}">\n'
        + "".join(f'    <uses-permission android:name="{p}" />\n' for p in perms)
        + f'    <application android:label="{pkg}">\n'
        + '        <meta-data android:name="com.dpdpaudit.child_directed" android:value="false" />\n'
        + "    </application>\n</manifest>\n")


def write_export(sample: list[dict], apps: dict) -> None:
    """PoliCheck/PoliGraph input, in the layout of data/tools/policheck_sanity/."""
    exp = OUT / "export" / "policheck"
    (exp / "plaintext_policies").mkdir(parents=True, exist_ok=True)
    with (exp / "flows.csv").open("w", newline="") as f, (exp / "flow_index.csv").open("w", newline="") as g:
        w = csv.writer(f)
        w.writerow(["package_name", "app_name", "version_name", "version_code", "data_type", "dest_domain",
                    "dest_ip", "arb_number", "privacy_policy"])
        wi = csv.writer(g)
        wi.writerow(["package_name", "case_id", "flow_id", "opp115_type", "policheck_token", "dest_domain"])
        for s in sample:
            w.writerow([s["package"], s["package"], "1.0", "1", s["policheck_token"], s["dest_domain"], "", "1",
                        apps[s["package"]]["policy_url"]])
            wi.writerow([s["package"], s["package"], s["flow_id"], s["data_type"], s["policheck_token"],
                         s["dest_domain"]])
    for pkg in {s["package"] for s in sample}:
        (exp / "plaintext_policies" / f"{pkg}.txt").write_text(trim_chrome((SRC / "policies" / f"{pkg}.txt").read_text()))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-flows", type=int, default=80)
    ap.add_argument("--per-app", type=int, default=4)
    args = ap.parse_args()
    apps = json.loads((SRC / "apps.json").read_text())["apps"]
    excl = SRC / "excluded.csv"
    excluded = {r["package"]: r["reason"] for r in csv.DictReader(excl.open())} if excl.exists() else {}
    apps = {p: a for p, a in apps.items() if p not in excluded}
    tokens = {r["policheck_token"]: r["data_type"] for r in csv.DictReader((DATA / "tools" / "real_token_mapping.csv").open())}
    sdk_by_domain = {registered(r["domain"]): r["sdk_id"] for r in csv.DictReader((DATA / "tools" / "sdk_domains.csv").open())}
    sdk_gradle = {r["sdk_id"]: r["gradle"] for r in csv.DictReader((DATA / "tools" / "sdk_table.csv").open())}
    rows: dict[str, list] = {}
    for r in csv.reader((SRC / "flows_raw.csv").open()):
        if r[0] != "package_name":
            rows.setdefault(r[0], []).append(r)
    by_app = {}
    for pkg in sorted(apps):
        flows = pick(pkg, apps[pkg]["policy_url"], rows.get(pkg, []), tokens, sdk_by_domain, args.per_app)
        if flows:
            by_app[pkg] = flows
    trim(by_app, args.max_flows)
    old = SRC / "sample.csv"
    if old.exists() and any(r[c].strip() for r in csv.DictReader(old.open()) for c in SAMPLE_COLUMNS[7:]):
        raise SystemExit(f"{old} already has labels: not overwritten")
    if OUT.exists():
        shutil.rmtree(OUT)
    sample = []
    for pkg, flows in by_app.items():
        for i, f in enumerate(flows, 1):
            f["flow_id"] = f"f{i}"
        write_case(pkg, apps[pkg], flows, trim_chrome((SRC / "policies" / f"{pkg}.txt").read_text()), sdk_gradle)
        sample += flows
    write_export(sample, apps)
    with (SRC / "sample.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=SAMPLE_COLUMNS, restval="")
        w.writeheader()
        w.writerows(sample)
    print(f"{len(by_app)} apps ({len(apps) - len(by_app)} with no usable flow, {len(excluded)} excluded), "
          f"{len(sample)} flows")
    print("data types:", dict(Counter(s["data_type"] for s in sample)))
    print("recipients:", dict(Counter("first_party" if s["recipient"] == "first_party" else "SDK" for s in sample)))


if __name__ == "__main__":
    main()
