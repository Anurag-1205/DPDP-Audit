"""Vagueness ladder (SPEC-06): the same policy and app, with exactly one sentence changed.

For each held-out policy, one target flow (collection or sharing of a data type PoliCheck can
express) gets four rungs:

  r1 clear     a templated sentence that discloses the flow specifically     gold label: clear
  r2 explicit  a templated sentence that denies it                           gold label: incorrect
  r3 vague     a templated generic sentence                                  gold label: vague
  r4 deleted   nothing inserted                                              gold label: omitted

The base policy (= r4) removes every sentence that the OPP-115 annotations mark as covering
the target practice for the target data type or for generic data, in either direction (Does
or Does Not). r1-r3 insert one sentence at the same character position of the base policy.
Gold labels come from the construction, not from the rules or a model. Base-policy sentences
that still mention the data type next to a practice verb are flagged for the human checkers.
"""
from __future__ import annotations

import csv
import json
import random
import re
import shutil
from dataclasses import dataclass

from .cases import BENCH
from .gaps import gap_table
from .opp115 import DATA_TYPE, GENERIC_TYPES, Policy, _clean_segment, load_all
from .split import load_split
from .tools.sdk import lookup_sdk

SEED = 0
FIRST_PARTY = "First Party Collection/Use"
THIRD_PARTY_SHARING = "Third Party Sharing/Collection"
# Data types the PoliCheck export can express (data/tools/datatype_mapping.csv)
LADDER_TYPES = ["Location", "IP address and device IDs", "Contact", "Personal identifier", "Computer information"]
PHRASE = {
    "Location": "precise location",
    "IP address and device IDs": "device identifiers and IP address",
    "Contact": "email address and contact details",
    "Personal identifier": "name and other personal identifiers",
    "Computer information": "device and browser information",
}
RECIPIENTS = [  # (sdk_id, flow purpose, clause for the clear rung)
    ("admob", "Advertising", "with our advertising partner Google (AdMob) to show you relevant ads"),
    ("mixpanel", "Analytics/Research", "with our analytics provider Mixpanel to understand how the app is used"),
]
COLLECT_PURPOSE = ("Basic service/feature", "to provide and operate the features of our app")
RUNGS = [("r1", "clear", "clear", None), ("r2", "explicit", "incorrect", "explicit"),
         ("r3", "vague", "vague", "vague"), ("r4", "deleted", "omitted", "omission")]

KEYWORDS = {
    "Location": ["location", "gps", "geolocation", "geographic", "geo-location", "latitude", "whereabouts"],
    "IP address and device IDs": ["ip address", "device id", "device identifier", "advertising id", "idfa",
                                  "udid", "unique identifier", "mac address", "imei"],
    "Contact": ["email", "e-mail", "phone", "telephone", "mailing address", "postal address", "contact information",
                "contact details"],
    "Personal identifier": ["name", "social security", "passport", "driver's license", "identifier", "username"],
    "Computer information": ["browser", "operating system", "device type", "computer", "hardware", "device information"],
}
VERBS = {
    "collection": ["collect", "gather", "obtain", "receive", "record", "track", "use ", "store", "log"],
    # "provide" and "give" are left out: "you provide us with ..." is collection, not sharing
    "sharing": ["share", "disclose", "transfer", "sell", "rent", "trade", "third part", "partner",
                "advertiser", "affiliate", "vendor", "service provider"],
}
GENERIC_WORDS = ["personal information", "personally identifiable", "information about you", "your information",
                 "personal data", "user information", "information we collect", "such information"]


@dataclass
class Removal:
    segment: int
    start: int
    end: int
    text: str


def _norm_map(text: str) -> tuple[str, list[int]]:
    """Whitespace-collapsed lower-case text, and each character's offset in the original."""
    out, idx, prev_space = [], [], False
    for i, ch in enumerate(text):
        if ch.isspace():
            if prev_space or not out:
                continue
            out.append(" ")
            idx.append(i)
            prev_space = True
        else:
            out.append(ch.lower())
            idx.append(i)
            prev_space = False
    return "".join(out), idx


_SENT = re.compile(r"[^.!?\n]+(?:[.!?]+|\n|$)")


def sentences(text: str) -> list[tuple[int, int]]:
    """Character ranges of the sentences (and lines) of a segment."""
    return [(m.start(), m.end()) for m in _SENT.finditer(text) if m.group().strip()]


def covering_practices(policy: Policy, practice: str, data_type: str):
    return [p for p in policy.practices if p.category == practice
            and (p.get(DATA_TYPE) == data_type or p.get(DATA_TYPE) in GENERIC_TYPES or not p.get(DATA_TYPE))]


def removals(policy: Policy, practice: str, data_type: str) -> list[Removal]:
    """Sentences that contain any annotated span of a covering practice."""
    marked: dict[int, set[tuple[int, int]]] = {}
    for p in covering_practices(policy, practice, data_type):
        if p.segment_id >= len(policy.segments):
            continue
        seg = policy.segments[p.segment_id]
        norm, idx = _norm_map(seg)
        sents = sentences(seg)
        for span in p.spans.values():
            t = " ".join(_clean_segment(span).split()).lower()
            if not t or t == "not selected":
                continue
            pos = norm.find(t)
            if pos < 0:
                continue
            a, b = idx[pos], idx[pos + len(t) - 1] + 1
            for s, e in sents:
                if s < b and a < e:
                    marked.setdefault(p.segment_id, set()).add((s, e))
    out = []
    for seg_id, ranges in sorted(marked.items()):
        for s, e in sorted(ranges):
            out.append(Removal(seg_id, s, e, policy.segments[seg_id][s:e].strip()))
    return out


def base_segments(policy: Policy, rem: list[Removal]) -> tuple[list[str], tuple[int, int] | None]:
    """Segments with the removed sentences cut out; the insertion point is where the first one was."""
    by_seg: dict[int, list[Removal]] = {}
    for r in rem:
        by_seg.setdefault(r.segment, []).append(r)
    segs, point = [], None
    for i, seg in enumerate(policy.segments):
        cuts = sorted(by_seg.get(i, []), key=lambda r: r.start)
        if not cuts:
            segs.append(seg)
            continue
        out, last = [], 0
        for r in cuts:
            if r.end <= last:                   # already inside an earlier cut
                continue
            out.append(seg[last:max(r.start, last)])
            last = r.end
            while last < len(seg) and seg[last] == " ":
                last += 1
            if point is None:
                point = (i, len("".join(out)))
        out.append(seg[last:])
        segs.append("".join(out))
    return segs, point


def residual_flags(segs: list[str], data_type: str, kind: str) -> list[str]:
    """Base-policy sentences that still mention the data type (or generic data) next to a practice verb."""
    flags = []
    for seg in segs:
        for s, e in sentences(seg):
            low = seg[s:e].lower()
            verb = any(v in low for v in VERBS[kind])
            if not verb:
                continue
            if any(k in low for k in KEYWORDS[data_type]):
                flags.append("TYPE: " + seg[s:e].strip())
            elif kind == "sharing" and any(g in low for g in GENERIC_WORDS):
                flags.append("GENERIC: " + seg[s:e].strip())
    return flags


def rung_sentence(kind: str, data_type: str, rung: str, recipient: tuple | None) -> str:
    phrase = PHRASE[data_type]
    if kind == "sharing":
        return {"clear": f"We share your {phrase} {recipient[2]}.",
                "explicit": f"We do not share your {phrase} with third parties.",
                "vague": "We may share information with our partners.",
                "deleted": ""}[rung]
    return {"clear": f"We collect your {phrase} {COLLECT_PURPOSE[1]}.",
            "explicit": f"We do not collect your {phrase}.",
            "vague": "We may collect information about you when you use our services.",
            "deleted": ""}[rung]


def insert(segs: list[str], point: tuple[int, int] | None, sentence: str) -> list[str]:
    """Insert `sentence` + one space at the point (default: the end of the first non-empty segment)."""
    if not sentence:
        return list(segs)
    if point is None:
        i = next((k for k, s in enumerate(segs) if s.strip()), 0)
        point = (i, len(segs[i]))
    i, pos = point
    out = list(segs)
    sep_before = "" if pos == 0 or out[i][pos - 1:pos].isspace() else " "
    out[i] = out[i][:pos] + sep_before + sentence + " " + out[i][pos:]
    return out


def choose_targets(policies: list[Policy], seed: int = SEED) -> list[dict]:
    """One target per policy: ~2 sharing ladders per collection ladder, data types that the policy addresses."""
    rng = random.Random(seed)
    order = sorted(policies, key=lambda p: p.policy_id)
    kinds = ["sharing"] * round(len(order) * 2 / 3) + ["collection"] * (len(order) - round(len(order) * 2 / 3))
    rng.shuffle(kinds)
    out = []
    for n, (pol, kind) in enumerate(zip(order, kinds)):
        practice = THIRD_PARTY_SHARING if kind == "sharing" else FIRST_PARTY
        addressed = sorted({p.get(DATA_TYPE) for p in pol.practices if p.category == practice} & set(LADDER_TYPES))
        data_type = rng.choice(addressed or LADDER_TYPES)
        recipient = RECIPIENTS[n % len(RECIPIENTS)] if kind == "sharing" else None
        out.append({"policy": pol, "kind": kind, "practice": practice, "data_type": data_type,
                    "recipient": recipient, "addressed": bool(addressed)})
    return out


def build(seed: int = SEED, split: str = "ladder") -> dict:
    from .generator import gradle, manifest, write_case
    held = set(load_split()["heldout"])
    policies = [p for p in load_all() if f"{p.policy_id}_{p.name}" in held]
    split_dir = BENCH / split
    # human-check files survive a rebuild: the checkers' own sheets, the disagreement list, and the
    # merged check sheet once it holds answers (rebuilding must never erase people's work)
    kept = {}
    if split_dir.exists():
        for f in list(split_dir.glob("check_sheet_*.csv")) + list(split_dir.glob("disagreements.csv")):
            kept[f.name] = f.read_bytes()
        sheet = split_dir / "check_sheet.csv"
        if sheet.exists() and any(r.get("checker_1_ok", "").strip() or r.get("checker_2_ok", "").strip()
                                  for r in csv.DictReader(sheet.open())):
            kept["check_sheet.csv"] = sheet.read_bytes()
        shutil.rmtree(split_dir)
    rows, removed_log = [], []
    for t in choose_targets(policies, seed):
        pol, kind, d = t["policy"], t["kind"], t["data_type"]
        rem = removals(pol, t["practice"], d)
        segs, point = base_segments(pol, rem)
        flags = residual_flags(segs, d, kind)
        if t["recipient"]:
            sdk_id, purpose = t["recipient"][0], t["recipient"][1]
        else:
            sdk_id, purpose = "first_party", COLLECT_PURPOSE[0]
        flow = {"data_type": d, "recipient": sdk_id, "purpose": purpose, "retention": "Unspecified", "flow_id": "f1"}
        gap = "undisclosed_sharing" if kind == "sharing" else "undisclosed_collection"
        ladder_id = f"L{pol.policy_id}"
        app_rng = random.Random(f"{seed}-{pol.policy_id}")
        build_gradle, android = gradle([flow], app_rng), manifest(
            "com.example." + "".join(ch for ch in pol.name.split(".")[0].lower() if ch.isalnum()), [flow], False)
        removed_log.append({"ladder_id": ladder_id, "policy_id": pol.policy_id, "kind": kind, "data_type": d,
                            "removed": [r.text for r in rem], "insertion_point": point,
                            "residual_flags": flags})
        for rung_id, rung, label, level in RUNGS:
            sentence = rung_sentence(kind, d, rung, t["recipient"])
            text = "\n\n".join(insert(segs, point, sentence))
            case_id = f"{ladder_id}_{rung_id}"
            findings = [] if level is None else [{"flow_id": "f1", "data_type": d, "gap_type": gap, "level": level,
                                                  "sections": gap_table()[gap]["gold"]}]
            key = {"case_id": case_id, "policy_id": pol.policy_id, "kind": "ladder", "ladder_id": ladder_id,
                   "rung": rung, "ladder_kind": kind, "inserted": sentence, "findings": findings,
                   "flow_labels": {"f1": label}, "flow_gap_types": {"f1": gap}}
            pol_view = Policy(pol.policy_id, pol.name, text.split("\n\n"), [])
            write_case(split_dir, case_id, pol_view, [flow], False, key, app_rng)
            app = split_dir / "cases" / case_id / "app"
            (app / "build.gradle").write_text(build_gradle)       # identical app across rungs
            (app / "AndroidManifest.xml").write_text(android)
            (split_dir / "cases" / case_id / "policy.txt").write_text(text)
            rows.append({"case_id": case_id, "ladder_id": ladder_id, "policy_id": pol.policy_id, "kind": kind,
                         "data_type": d, "recipient": sdk_id, "rung": rung, "gold_label": label,
                         "inserted_sentence": sentence, "removed_sentences": len(rem),
                         "residual_flags": len(flags), "checker_1": "", "checker_1_ok": "",
                         "checker_2": "", "checker_2_ok": "", "notes": ""})
    with (split_dir / "check_sheet.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    if "check_sheet.csv" in kept:
        old = [r["case_id"] for r in csv.DictReader(kept["check_sheet.csv"].decode().splitlines())]
        if old != [r["case_id"] for r in rows]:
            raise RuntimeError("the rebuilt ladder has different rungs from the filled check sheet")
    for name, data in kept.items():
        (split_dir / name).write_bytes(data)
    (split_dir / "removed_sentences.json").write_text(json.dumps(removed_log, indent=1))
    summary = {"ladders": len(removed_log), "cases": len(rows),
               "kinds": {k: sum(1 for r in removed_log if r["kind"] == k) for k in ("sharing", "collection")},
               "data_types": {d: sum(1 for r in removed_log if r["data_type"] == d) for d in LADDER_TYPES},
               "removed_sentences": sum(len(r["removed"]) for r in removed_log),
               "ladders_with_residual_flags": sum(1 for r in removed_log if r["residual_flags"]),
               "ladders_without_removal": sum(1 for r in removed_log if not r["removed"])}
    (split_dir / "summary.json").write_text(json.dumps(summary, indent=1))
    return summary


# ------------------------------------------------------------------ checks
def _ok(v) -> bool:
    return str(v or "").strip().lower() in ("ok", "yes", "y", "1", "true")


def settled(split: str = "ladder") -> dict[str, bool]:
    """Joint answers for rungs the two checkers answered differently (disagreements.csv, column
    `agreed`); rungs not settled yet are left out."""
    p = BENCH / split / "disagreements.csv"
    if not p.exists():
        return {}
    return {r["case_id"]: _ok(r["agreed"]) for r in csv.DictReader(p.open()) if r.get("agreed", "").strip()}


def accepted_cases(split: str = "ladder") -> set[str] | None:
    """Rungs accepted by the human check; None while the check sheet is not filled in. A rung is
    accepted when both checkers marked it ok, or, where they disagreed, when they settled on ok
    together; a disagreement not settled yet counts as rejected."""
    p = BENCH / split / "check_sheet.csv"
    rows = list(csv.DictReader(p.open()))
    if not all(r["checker_1_ok"].strip() and r["checker_2_ok"].strip() for r in rows):
        return None
    joint = settled(split)
    out = set()
    for r in rows:
        a, b = _ok(r["checker_1_ok"]), _ok(r["checker_2_ok"])
        if (a and b) or (a != b and joint.get(r["case_id"], False)):
            out.add(r["case_id"])
    return out


def check_status(split: str = "ladder") -> dict:
    rows = list(csv.DictReader((BENCH / split / "check_sheet.csv").open()))
    differ = [r["case_id"] for r in rows if _ok(r["checker_1_ok"]) != _ok(r["checker_2_ok"])]
    joint = settled(split)
    return {"rungs": len(rows), "checkers_agree": len(rows) - len(differ), "disagreements": len(differ),
            "settled": sum(1 for c in differ if c in joint), "unsettled": sum(1 for c in differ if c not in joint)}


# ----------------------------------------------------------------- scoring
RUNG_ORDER = ["clear", "explicit", "vague", "deleted"]
PAIRS = [("clear", "explicit"), ("explicit", "vague"), ("vague", "deleted"), ("explicit", "deleted")]


def _flow_label(out: dict) -> str:
    lab = out.get("flow_labels", {}).get("f1", {})
    return lab.get("label", "clear") if isinstance(lab, dict) else (lab or "clear")


def mcnemar(a: list[bool], b: list[bool]) -> dict:
    """Exact McNemar test on paired correctness (b01 = only a correct, b10 = only b correct)."""
    from scipy.stats import binomtest
    only_a = sum(x and not y for x, y in zip(a, b))
    only_b = sum(y and not x for x, y in zip(a, b))
    n = only_a + only_b
    p = binomtest(only_a, n, 0.5).pvalue if n else 1.0
    return {"only_first_correct": only_a, "only_second_correct": only_b, "p_value": float(p)}


def score_ladder(keys: list[dict], outs: list[dict], accepted: set[str] | None = None) -> dict:
    """Label accuracy per rung, paired rung differences (McNemar) and the label confusion matrix."""
    from .gaps import LABELS
    by_ladder: dict[str, dict[str, bool]] = {}
    confusion = {r: {lab: 0 for lab in LABELS} for r in RUNG_ORDER}
    for k, o in zip(keys, outs):
        if accepted is not None and k["case_id"] not in accepted:
            continue
        pred = _flow_label(o)
        confusion[k["rung"]][pred if pred in LABELS else "clear"] += 1
        by_ladder.setdefault(k["ladder_id"], {})[k["rung"]] = pred == k["flow_labels"]["f1"]
    acc = {r: (sum(v[r] for v in by_ladder.values() if r in v) /
               max(1, sum(1 for v in by_ladder.values() if r in v))) for r in RUNG_ORDER}
    paired = {}
    for a, b in PAIRS:
        both = [v for v in by_ladder.values() if a in v and b in v]
        paired[f"{a}_vs_{b}"] = dict(mcnemar([v[a] for v in both], [v[b] for v in both]), n=len(both),
                                     difference=(sum(v[a] for v in both) - sum(v[b] for v in both)) / max(1, len(both)))
    return {"accuracy": acc, "n_ladders": len(by_ladder), "paired": paired, "confusion": confusion}
