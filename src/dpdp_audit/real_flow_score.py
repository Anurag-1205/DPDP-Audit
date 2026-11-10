"""Real-flow metrics (SPEC-08, AC-08.3; docs/stage-4-plan.md §5).

Real flows have no compliant control apps, so the case-level false-alarm rate is undefined. Instead:
  - flow-label accuracy and macro-F1 against the settled human labels (the main real-flow number);
  - per-flow false alarms: the share of flows the labellers settled as *clear* that a system labels
    as anything else (it would raise a gap the humans would not);
  - Cohen's kappa of each system with each labeller, to set against the labellers' own kappa.
A flow a system did not label counts as *clear*, as in score.label_macro_f1.
"""
from __future__ import annotations

from collections import Counter

from .gaps import LABELS


def predicted_label(out: dict, flow_id: str) -> str:
    p = out.get("flow_labels", {}).get(flow_id, {})
    return (p.get("label", "clear") if isinstance(p, dict) else p) or "clear"


def flow_pairs(keys: list[dict], outs: list[dict]) -> list[tuple[str, str]]:
    """(settled label, system label) for every flow, in key order."""
    return [(g, predicted_label(o, fid)) for k, o in zip(keys, outs) for fid, g in k["flow_labels"].items()]


def cohen_kappa(a: list[str], b: list[str]) -> float:
    n = len(a)
    if not n:
        return float("nan")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def flow_false_alarm(keys: list[dict], outs: list[dict]) -> float:
    clear = [(g, p) for g, p in flow_pairs(keys, outs) if g == "clear"]
    return sum(p != "clear" for _, p in clear) / len(clear) if clear else float("nan")


def label_accuracy(keys: list[dict], outs: list[dict]) -> float:
    pairs = flow_pairs(keys, outs)
    return sum(g == p for g, p in pairs) / len(pairs) if pairs else float("nan")


def gap_accuracy(keys: list[dict], outs: list[dict]) -> float:
    """Binary reading: does the flow have a gap (any label but clear)?"""
    pairs = flow_pairs(keys, outs)
    return sum((g != "clear") == (p != "clear") for g, p in pairs) / len(pairs) if pairs else float("nan")


def confusion(keys: list[dict], outs: list[dict]) -> dict:
    c = Counter(flow_pairs(keys, outs))
    return {g: {p: c[(g, p)] for p in LABELS} for g in LABELS}


def labeller_agreement(keys: list[dict], outs: list[dict], labellers: dict[str, dict]) -> dict:
    """kappa of the system with each labeller; labellers: {name: {(case_id, flow_id): label}}."""
    res = {}
    for name, lab in labellers.items():
        sys_l, hum_l = [], []
        for k, o in zip(keys, outs):
            for fid in k["flow_labels"]:
                if (k["case_id"], fid) in lab:
                    sys_l.append(predicted_label(o, fid))
                    hum_l.append(lab[(k["case_id"], fid)])
        res[name] = {"kappa": cohen_kappa(sys_l, hum_l),
                     "agreement": sum(x == y for x, y in zip(sys_l, hum_l)) / len(sys_l) if sys_l else float("nan"),
                     "n": len(sys_l)}
    return res
