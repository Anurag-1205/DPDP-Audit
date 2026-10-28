"""Score the v2 development choice on the pooled dev splits (dev + dev2, 102 cases from training policies).

  python scripts/score_dev_pooled.py

Prints and writes results/scores/dev_pooled.json: F1, false-alarm rate and label macro-F1 of every
dev configuration (as run and re-verified, `_rv`), and paired policy-level bootstrap intervals for the
comparisons in docs/pipeline.md#v2. `full_v2` was not run on dev: its row re-derives v2_batch's saved
reviewer replies with the retention rule (deterministic; with the rule off the re-derivation reproduces
v2_batch exactly, which is checked here).
"""
import copy
import json

from dpdp_audit import score
from dpdp_audit.baselines import app_facts
from dpdp_audit.cases import case_dirs, load_case, load_key
from dpdp_audit.paths import RESULTS
from dpdp_audit.pipeline import get_config
from dpdp_audit.pipeline.aggregator import aggregate
from dpdp_audit.pipeline.decide import derive
from dpdp_audit.pipeline.verifier import verify
from dpdp_audit.runs import load_runs

SPLITS = ("dev", "dev2")
SYSTEMS = ["full", "v2_gate", "v2_read", "v2_purpose", "v2_batch"]
PAIRS = [("v2_gate", "full"), ("v2_read", "v2_gate"), ("v2_purpose", "v2_read"), ("v2_batch", "v2_read"),
         ("full_v2", "full"), ("full_v2", "v2_read"), ("full_v2_rv", "full_rv")]


def rederive(run: dict, case: dict, cfg, retention_check: bool) -> dict:
    """Re-apply the deterministic stages to saved reviewer replies (LLM verdicts are kept)."""
    run = copy.deepcopy(run)
    facts = app_facts(case["app_dir"])
    cands = {c["candidate_id"]: c for c in run["trace"]["candidates"]}
    reviews = [dict(r, decisions=[derive(cands[d["candidate_id"]], d["raw"], case["policy"],
                                         purpose_paragraph=cfg.purpose_paragraph, retention_check=retention_check)
                                  if d["candidate_id"] in cands else d for d in r["decisions"]])
               for r in run["trace"]["reviews"]]
    agg = aggregate(facts["flows"], run["trace"]["candidates"], reviews, merge=cfg.specialists)
    ver = verify(agg["findings"], case["policy"], facts["flows"], None, 0, use_llm=False)
    old = {f["candidate_id"]: f for f in run["findings"]}
    for f in ver["findings"]:
        if f["candidate_id"] in old and f["gap_type"] != "retention_mismatch":
            f["uncertain"] = old[f["candidate_id"]].get("uncertain", False)
            f["supported"] = old[f["candidate_id"]].get("supported")
    return dict(run, findings=ver["findings"], flow_labels=agg["flow_labels"])


def main():
    cases, keys = {}, []
    for split in SPLITS:
        for d in case_dirs(split):
            c = load_case(d)
            cases[c["case_id"]] = c
            keys.append(load_key(split, c["case_id"]))
    ids = [k["case_id"] for k in keys]

    def load(system):
        out = []
        for split in SPLITS:
            runs = load_runs(split, system, 0, [c for c in ids if (split == "dev") == (c in dev_ids)])
            if runs is None:
                raise SystemExit(f"{split}/{system}: runs missing")
            out += runs
        return out

    dev_ids = {load_case(d)["case_id"] for d in case_dirs("dev")}
    outs = {}
    for s in SYSTEMS:
        outs[s] = load(s)
        outs[f"{s}_rv"] = load(f"{s}_rv")
    for suffix in ("", "_rv"):
        cfg = get_config(f"v2_batch{suffix}")
        same = [rederive(o, cases[o["case_id"]], cfg, retention_check=False) for o in outs[f"v2_batch{suffix}"]]
        if score.evaluate(keys, same) != score.evaluate(keys, outs[f"v2_batch{suffix}"]):
            raise SystemExit("re-derivation with the rule off does not reproduce v2_batch")
        outs[f"full_v2{suffix}"] = [rederive(o, cases[o["case_id"]], cfg, retention_check=True)
                                    for o in outs[f"v2_batch{suffix}"]]

    metrics = lambda ks, oo: score.evaluate(ks, oo)
    result = {"cases": len(keys), "gold_gaps": sum(len(k["findings"]) for k in keys),
              "controls": sum(k["kind"] == "control" for k in keys), "systems": {}, "paired": {}}
    for s, oo in outs.items():
        ev = metrics(keys, oo)
        result["systems"][s] = {"f1": ev["detection"]["overall"]["f1"],
                                "false_alarm_rate": ev["safety"]["false_alarm_rate"],
                                "label_macro_f1": ev["labels"]["macro_f1"]}
    for a, b in PAIRS:
        result["paired"][f"{a}-{b}"] = {
            "f1": score.cluster_bootstrap(keys, outs[a], score.f1_metric, outs_b=outs[b]),
            "false_alarm": score.cluster_bootstrap(keys, outs[a], score.false_alarm_metric, outs_b=outs[b]),
            "label_macro_f1": score.cluster_bootstrap(keys, outs[a], lambda k, o: score.label_macro_f1(k, o)["macro_f1"],
                                                      outs_b=outs[b])}
    (RESULTS / "scores" / "dev_pooled.json").write_text(json.dumps(result, indent=1))
    print(f"pooled dev: {result['cases']} cases, {result['gold_gaps']} gold gaps, {result['controls']} controls")
    for s, r in result["systems"].items():
        print(f"{s:15} F1 {r['f1']:.3f}  false-alarm {r['false_alarm_rate']:.3f}  label macro-F1 {r['label_macro_f1']:.3f}")
    for k, r in result["paired"].items():
        print(f"{k}: " + "; ".join(f"{m} {v['point']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}]" for m, v in r.items()))


if __name__ == "__main__":
    main()
