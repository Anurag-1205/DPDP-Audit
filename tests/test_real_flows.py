"""Real-flow sample selection (SPEC-08, scripts/build_real_flows.py)."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "build_real_flows", Path(__file__).resolve().parents[1] / "scripts" / "build_real_flows.py")
brf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(brf)

SDK = {"doubleclick.net": "admob", "unity3d.com": "unity_ads"}
TOKENS = {"aaid": "IP address and device IDs", "androidid": "IP address and device IDs",
          "geolatlon": "Location", "email": "Contact"}


def row(token, dest):
    return ["com.ticketmaster.app", "x", "1", "1", token, dest, "", "1", "https://www.ticketmaster.com/privacy"]


def test_recipient_is_first_party_sdk_or_unknown():
    url = "https://www.ticketmaster.com/privacy"
    assert brf.recipient("com.ticketmaster.app", url, "api.ticketmaster.com", SDK) == "first_party"
    assert brf.recipient("com.ticketmaster.app", "https://legal.other.com/p", "tm.ticketmaster.net", SDK) == "first_party"
    assert brf.recipient("com.ticketmaster.app", url, "googleads.g.doubleclick.net", SDK) == "admob"
    assert brf.recipient("com.ticketmaster.app", url, "api.taplytics.com", SDK) is None


def test_pick_dedupes_drops_unknown_and_prefers_first_party_then_location():
    rows = [row("aaid", "googleads.g.doubleclick.net"), row("androidid", "pubads.g.doubleclick.net"),
            row("aaid", "api.taplytics.com"), row("imei", "api.ticketmaster.com"),
            row("email", "unity3d.com"), row("geolatlon", "x.unity3d.com"), row("email", "api.ticketmaster.com")]
    flows = brf.pick("com.ticketmaster.app", "https://www.ticketmaster.com/privacy", rows, TOKENS, SDK, per_app=3)
    got = [(f["data_type"], f["recipient"], f["gap_type"]) for f in flows]
    assert got == [("Contact", "first_party", "undisclosed_collection"),
                   ("Location", "unity_ads", "undisclosed_sharing"),
                   ("Contact", "unity_ads", "undisclosed_sharing")]


def test_trim_takes_from_the_largest_app_first():
    by_app = {"a": [1, 2, 3, 4], "b": [1, 2], "c": [1, 2, 3]}
    brf.trim(by_app, 7)
    assert [len(by_app[k]) for k in "abc"] == [2, 2, 3]     # a: 4 -> 3, then ties with c, first in order


spec_l = importlib.util.spec_from_file_location(
    "real_flow_labels", Path(__file__).resolve().parents[1] / "scripts" / "real_flow_labels.py")
rfl = importlib.util.module_from_spec(spec_l)
spec_l.loader.exec_module(rfl)


def test_kappa_perfect_chance_and_known_value():
    assert rfl.kappa(["clear", "vague"], ["clear", "vague"]) == 1.0
    # 3 of 4 agree; each labeller uses vague 3 times and clear once: pe = (3*3 + 1*1) / 16
    a, b = ["vague", "vague", "vague", "clear"], ["vague", "vague", "clear", "vague"]
    assert abs(rfl.kappa(a, b) - (0.5 - 10 / 16) / (1 - 10 / 16)) < 1e-12
