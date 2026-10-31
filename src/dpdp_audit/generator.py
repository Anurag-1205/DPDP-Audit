"""Generate benchmark cases: one compliant control and two variants per held-out policy.

Control: flows the policy explicitly and specifically covers, checked by the
rules to have no finding. Variants: the control plus 1-2 planted flows chosen
to fill the rarest gap-type x level cells first. Answer keys are always the
rules applied to the whole application (gold_rules.answer_key).
"""
from __future__ import annotations

import json
import random
import shutil
from collections import Counter

from . import gold_rules as g
from .cases import BENCH
from .cells import candidates
from .opp115 import Policy, load_all
from .split import load_split
from .tools.sdk import lookup_sdk

# OPP-115 data type -> Android permission that exposes it
TYPE_PERMISSION = {
    "Location": "android.permission.ACCESS_FINE_LOCATION",
    "Contact": "android.permission.READ_CONTACTS",
    "IP address and device IDs": "com.google.android.gms.permission.AD_ID",
    "Personal identifier": "android.permission.GET_ACCOUNTS",
    "Health": "android.permission.ACTIVITY_RECOGNITION",
}
# Purposes to SDKs that serve them, for clearly disclosed control sharing flows
PURPOSE_SDKS = {
    "Advertising": ["admob", "facebook_audience"],
    "Analytics/Research": ["google_analytics", "firebase_analytics"],
    "Marketing": ["facebook_sdk"],
    "Personalization/Customization": ["firebase_analytics"],
    "Service Operation and Security": ["firebase_crashlytics"],
    "Basic service/feature": ["firebase_analytics"],
    "Additional service/feature": ["facebook_sdk"],
}
BASE_LIBS = ["androidx.appcompat:appcompat:1.6.1", "androidx.core:core-ktx:1.12.0",
             "com.squareup.retrofit2:retrofit:2.9.0", "com.google.code.gson:gson:2.10.1"]
SDK_VERSIONS = {"admob": "23.0.0", "facebook_audience": "6.16.0", "google_analytics": "18.0.4",
                "firebase_analytics": "21.5.0", "facebook_sdk": "16.3.0", "firebase_crashlytics": "18.6.2",
                "mixpanel": "7.3.1"}
MAX_CONTROL_COLLECT = 3
MAX_CONTROL_SHARE = 2


def control_flows(policy: Policy, cov: g.Coverage, rng: random.Random) -> list[dict]:
    flows = []
    # only data types collected for a specific purpose: a real app always uses data for something
    collect = sorted(((d, p - g.GENERIC_PURPOSES) for d, p in cov.collect.items() if p - g.GENERIC_PURPOSES),
                     key=lambda kv: (kv[0] not in TYPE_PERMISSION, kv[0]))
    for d, specific in collect[:MAX_CONTROL_COLLECT]:
        purpose = rng.choice(sorted(specific))
        flows.append({"data_type": d, "recipient": "first_party", "purpose": purpose, "retention": "Unspecified"})
    shared = 0
    for d, entries in sorted(cov.share.items()):
        if shared >= MAX_CONTROL_SHARE:
            break
        for e in entries:
            sdk = next((s for s in PURPOSE_SDKS.get(e["purpose"], []) if g._names_recipient(e, s)), None)
            if sdk:
                flows.append({"data_type": d, "recipient": sdk, "purpose": e["purpose"], "retention": "Unspecified"})
                shared += 1
                break
    # keep only flows the rules agree are compliant
    key = g.answer_key("probe", policy, cov, _number(flows), False, "control")
    bad = {f["flow_id"] for f in key["findings"]}
    return [f for f in _number(flows) if f["flow_id"] not in bad]


def _number(flows: list[dict]) -> list[dict]:
    return [dict(f, flow_id=f"f{i + 1}") for i, f in enumerate(flows)]


def choose_plants(policy: Policy, cov: g.Coverage, usage: Counter, rng: random.Random,
                  n_variants: int = 2) -> list[list[dict]]:
    """Pick 1-2 plants per variant, preferring the least-used cells."""
    cands = candidates(policy, cov)
    rng.shuffle(cands)
    variants = []
    used_types = set()
    for v in range(n_variants):
        plants = []
        size = 1 if rng.random() < 0.5 else 2
        while len(plants) < size:
            pool = [c for c in cands if (c["gap_type"], c["flow"]["data_type"]) not in used_types
                    and not any(p.get("child_directed") and c.get("child_directed") for p in plants)]
            if not pool:
                break
            pick = min(pool, key=lambda c: usage[(c["gap_type"], c["level"])])
            plants.append(pick)
            used_types.add((pick["gap_type"], pick["flow"]["data_type"]))
            usage[(pick["gap_type"], pick["level"])] += 1
        variants.append(plants)
    return variants


# ---------------------------------------------------------------- app files
def gradle(flows: list[dict], rng: random.Random) -> str:
    libs = list(BASE_LIBS[: rng.randint(2, len(BASE_LIBS))])
    for f in flows:
        sdk = lookup_sdk(f["recipient"]) if f["recipient"] != "first_party" else None
        if sdk:
            coord = f"{sdk['gradle']}:{SDK_VERSIONS.get(sdk['sdk_id'], '1.0.0')}"
            if coord not in libs:
                libs.append(coord)
    lines = "\n".join(f"    implementation '{lib}'" for lib in libs)
    return f"plugins {{\n    id 'com.android.application'\n}}\n\ndependencies {{\n{lines}\n}}\n"


def manifest(package: str, flows: list[dict], child_directed: bool) -> str:
    perms = ["android.permission.INTERNET"] + sorted({TYPE_PERMISSION[f["data_type"]]
                                                       for f in flows if f["data_type"] in TYPE_PERMISSION})
    perm_lines = "\n".join(f'    <uses-permission android:name="{p}" />' for p in perms)
    return (f'<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="{package}">\n'
            f"{perm_lines}\n    <application android:label=\"{package}\">\n"
            f'        <meta-data android:name="com.dpdpaudit.child_directed" '
            f'android:value="{str(child_directed).lower()}" />\n    </application>\n</manifest>\n')


def write_case(split_dir, case_id: str, policy: Policy, flows: list[dict], child_directed: bool,
               key: dict, rng: random.Random):
    case_dir = split_dir / "cases" / case_id
    app = case_dir / "app"
    app.mkdir(parents=True, exist_ok=True)
    (case_dir / "policy.txt").write_text(policy.text())
    (case_dir / "meta.json").write_text(json.dumps({"case_id": case_id, "policy_id": policy.policy_id,
                                                    "policy_name": policy.name}, indent=1))
    package = "com.example." + "".join(ch for ch in policy.name.split(".")[0].lower() if ch.isalnum())
    (app / "build.gradle").write_text(gradle(flows, rng))
    (app / "AndroidManifest.xml").write_text(manifest(package, flows, child_directed))
    (app / "dataflows.json").write_text(json.dumps(flows, indent=1))
    keys_dir = split_dir / "answer_keys"
    keys_dir.mkdir(parents=True, exist_ok=True)
    (keys_dir / f"{case_id}.json").write_text(json.dumps(key, indent=1))


def generate(seed: int = 0, split: str = "main", policy_set: str = "heldout", n_policies: int | None = None,
             exclude_splits: tuple[str, ...] = ()) -> dict:
    """policy_set "heldout" builds an evaluation split; "train" builds a development split from
    training policies (for prompt checks and pilots that must not touch evaluation cases).
    exclude_splits: leave out the policies already used by these splits."""
    rng = random.Random(seed)
    held = set(load_split()[policy_set])
    used = {json.loads(f.read_text())["policy_id"] for s in exclude_splits
            for f in (BENCH / s / "answer_keys").glob("*.json")}
    policies = [p for p in load_all() if f"{p.policy_id}_{p.name}" in held and str(p.policy_id) not in used]
    if n_policies is not None:
        policies = sorted(random.Random(seed).sample(policies, n_policies), key=lambda p: p.policy_id)
    split_dir = BENCH / split
    if split_dir.exists():
        shutil.rmtree(split_dir)
    usage: Counter = Counter()
    stats = Counter()
    for policy in policies:
        cov = g.build_coverage(policy)
        base = control_flows(policy, cov, rng)
        if not base:
            stats["skipped_no_control"] += 1
            continue
        pid = policy.policy_id
        key = g.answer_key(f"{pid}_control", policy, cov, base, False, "control")
        assert not key["findings"], f"control for {pid} is not compliant"
        write_case(split_dir, f"{pid}_control", policy, base, False, key, rng)
        stats["control"] += 1
        for v, plants in enumerate(choose_plants(policy, cov, usage, rng), start=1):
            if not plants:
                continue
            flows = _number(base + [p["flow"] for p in plants])
            child = any(p.get("child_directed") for p in plants)
            case_id = f"{pid}_v{v}"
            key = g.answer_key(case_id, policy, cov, flows, child, "variant")
            key["planted"] = [{"gap_type": p["gap_type"], "level": p["level"],
                               "data_type": p["flow"]["data_type"]} for p in plants]
            write_case(split_dir, case_id, policy, flows, child, key, rng)
            stats["variant"] += 1
    return {"stats": dict(stats), "plant_cells": {f"{k[0]}/{k[1]}": n for k, n in sorted(usage.items())}}
