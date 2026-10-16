"""Read an application's dependencies, permissions and declared data flows.

An application directory may contain any of:
  build.gradle / build.gradle.kts   Android dependencies
  package.json                      npm dependencies
  requirements.txt                  Python dependencies
  AndroidManifest.xml               Android permissions
  app_config.json                   {"permissions": [...], "child_directed": bool}
  dataflows.json                    [{"data_type", "recipient", "purpose", "retention"}, ...]
"""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from .sdk import lookup_sdk

# Android permission -> OPP-115 personal-information type
PERMISSION_DATA_TYPES = {
    "android.permission.ACCESS_FINE_LOCATION": "Location",
    "android.permission.ACCESS_COARSE_LOCATION": "Location",
    "android.permission.ACCESS_BACKGROUND_LOCATION": "Location",
    "android.permission.READ_CONTACTS": "Contact",
    "android.permission.GET_ACCOUNTS": "Personal identifier",
    "android.permission.READ_PHONE_STATE": "IP address and device IDs",
    "com.google.android.gms.permission.AD_ID": "IP address and device IDs",
    "android.permission.ACTIVITY_RECOGNITION": "Health",
    "android.permission.BODY_SENSORS": "Health",
    "android.permission.READ_CALENDAR": "User profile",
    "android.permission.RECORD_AUDIO": "Other",
    "android.permission.CAMERA": "Other",
}

_GRADLE_DEP = re.compile(
    r"""(?:implementation|api|compile|runtimeOnly)\s*\(?\s*['"]([\w.\-]+:[\w.\-]+)(?::[\w.\-+]+)?['"]"""
)
_ANDROID_NS = "{http://schemas.android.com/apk/res/android}"


def parse_deps(app_dir: str | Path) -> list[dict]:
    """List declared dependencies, each with the SDK it matches (if any)."""
    app_dir = Path(app_dir)
    deps: list[tuple[str, str]] = []
    for name in ("build.gradle", "build.gradle.kts"):
        p = app_dir / name
        if p.exists():
            deps += [("gradle", m.group(1)) for m in _GRADLE_DEP.finditer(p.read_text())]
    p = app_dir / "package.json"
    if p.exists():
        pkg = json.loads(p.read_text())
        for section in ("dependencies", "devDependencies"):
            deps += [("npm", n) for n in pkg.get(section, {})]
    p = app_dir / "requirements.txt"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                deps.append(("pypi", re.split(r"[<>=!~\[; ]", line, maxsplit=1)[0]))
    out = []
    for ecosystem, coord in deps:
        sdk = lookup_sdk(coord)
        out.append({
            "ecosystem": ecosystem,
            "package": coord,
            "sdk_id": sdk["sdk_id"] if sdk else None,
            "sdk_name": sdk["name"] if sdk else None,
            "category": sdk["category"] if sdk else None,
            "ad_or_tracking": sdk["ad_or_tracking"] if sdk else False,
        })
    return out


def parse_perms(app_dir: str | Path) -> dict:
    """Permissions, the OPP-115 data types they expose, and the child-directed flag."""
    app_dir = Path(app_dir)
    perms: list[str] = []
    child_directed = False
    manifest = app_dir / "AndroidManifest.xml"
    if manifest.exists():
        root = ET.parse(manifest).getroot()
        for el in root.iter("uses-permission"):
            name = el.get(_ANDROID_NS + "name") or el.get("name")
            if name:
                perms.append(name)
        for el in root.iter("meta-data"):
            if (el.get(_ANDROID_NS + "name") or "").endswith("child_directed"):
                child_directed = (el.get(_ANDROID_NS + "value") or "").lower() == "true"
    config = app_dir / "app_config.json"
    if config.exists():
        cfg = json.loads(config.read_text())
        perms += [p for p in cfg.get("permissions", []) if p not in perms]
        child_directed = child_directed or bool(cfg.get("child_directed", False))
    data_types = sorted({PERMISSION_DATA_TYPES[p] for p in perms if p in PERMISSION_DATA_TYPES})
    return {"permissions": perms, "data_types": data_types, "child_directed": child_directed}


def get_flows(app_dir: str | Path) -> list[dict]:
    """Declared data flows: data type -> recipient -> purpose -> retention."""
    p = Path(app_dir) / "dataflows.json"
    if not p.exists():
        return []
    flows = json.loads(p.read_text())
    for i, f in enumerate(flows):
        f.setdefault("flow_id", f"f{i + 1}")
        f.setdefault("purpose", "Unspecified")
        f.setdefault("retention", "Unspecified")
    return flows
