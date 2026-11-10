"""Open-source case study (SPEC-08, AC-08.4): data/case_study/ -> data/benchmark/case_study/cases/.

  python scripts/build_case_study.py

data/case_study/apps.json holds, per app, the frozen repository commit, the policy source and date,
and the data flows written by hand from the code (each with a file:line citation). The policy text
is data/case_study/policies/<case_id>.txt (cleaned with sample_real_flows.paragraphs). The cases
use the same layout as main, so run_pipeline.py and run_baselines.py run on them unchanged. There
are no answer keys: every finding is checked by hand (data/case_study/findings.csv).
"""
import json
import shutil
from xml.sax.saxutils import quoteattr

from dpdp_audit.cases import BENCH
from dpdp_audit.paths import DATA

SRC = DATA / "case_study"
OUT = BENCH / "case_study" / "cases"


def manifest(app: dict) -> str:
    perms = "\n".join(f'    <uses-permission android:name="{p}" />' for p in app["permissions"])
    child = "true" if app["child_directed"] else "false"
    return (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package={quoteattr(app["case_id"])}>\n'
            f"{perms}\n    <application android:label={quoteattr(app['case_id'])}>\n"
            f'        <meta-data android:name="com.dpdpaudit.child_directed" android:value="{child}" />\n'
            "    </application>\n</manifest>\n")


def gradle(app: dict) -> str:
    deps = "\n".join(f"    implementation '{coord}'   // {src}" for coord, src in app["gradle"])
    return "plugins {\n    id 'com.android.application'\n}\n\ndependencies {\n" + deps + "\n}\n"


def main():
    apps = json.loads((SRC / "apps.json").read_text())
    if OUT.exists():
        shutil.rmtree(OUT)
    for app in apps:
        d = OUT / app["case_id"]
        (d / "app").mkdir(parents=True)
        meta = {"case_id": app["case_id"], "policy_id": app["case_id"], "policy_name": app["name"],
                "kind": "case_study", "repo": app["repo"], "commit": app["commit"],
                "policy_url": app["policy_url"], "policy_date": app["policy_date"]}
        (d / "meta.json").write_text(json.dumps(meta, indent=1))
        shutil.copy(SRC / "policies" / f"{app['case_id']}.txt", d / "policy.txt")
        flows = [{k: f[k] for k in ("data_type", "recipient", "purpose", "retention", "flow_id")}
                 for f in app["flows"]]
        (d / "app" / "dataflows.json").write_text(json.dumps(flows, indent=1))
        (d / "app" / "AndroidManifest.xml").write_text(manifest(app))
        (d / "app" / "build.gradle").write_text(gradle(app))
        print(f"{app['case_id']}: {len(flows)} flows")


if __name__ == "__main__":
    main()
