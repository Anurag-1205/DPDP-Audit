from pathlib import Path

from dpdp_audit.tools import get_flows, lookup_sdk, parse_deps, parse_perms, search_policy

APP = Path(__file__).parent / "fixtures" / "app_basic"


def test_lookup_sdk_by_coordinate_and_name():
    assert lookup_sdk("com.google.android.gms:play-services-ads:23.0.0")["sdk_id"] == "admob"
    assert lookup_sdk("Mixpanel")["category"] == "analytics"
    assert lookup_sdk("androidx.appcompat:appcompat") is None


def test_parse_deps_finds_sdks_across_ecosystems():
    deps = {d["package"]: d for d in parse_deps(APP)}
    assert deps["com.google.android.gms:play-services-ads"]["ad_or_tracking"]
    assert deps["com.google.firebase:firebase-crashlytics"]["sdk_id"] == "firebase_crashlytics"
    assert deps["sentry-sdk"]["category"] == "crash_reporting"
    assert deps["requests"]["sdk_id"] is None


def test_parse_perms_maps_to_opp115_types():
    perms = parse_perms(APP)
    assert perms["data_types"] == ["Contact", "Location"]
    assert perms["child_directed"] is False


def test_get_flows_fills_defaults():
    flows = get_flows(APP)
    assert flows[1]["retention"] == "Unspecified" and flows[0]["flow_id"] == "f1"


def test_search_policy_ranks_relevant_paragraph_first():
    policy = "We use cookies for analytics.\n\nWe do not share your location with third parties.\n\nContact us by email."
    assert "location" in search_policy(policy, "share location advertising")[0]["text"]
