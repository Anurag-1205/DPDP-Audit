"""Selective accuracy and the H5 verdict (SPEC-07).

  python scripts/selective_accuracy.py --split main
  python scripts/selective_accuracy.py --split ladder

Reads results/confidence/<split>.json (scripts/export_confidence.py). Per three-seed system:
accuracy, area under the curve, R@95 with a 95% policy-level interval, the review needed to match the
best tool, and the paired R@95 difference against B2 (H5). Tools and one-seed systems are single
points at 0% review (AC-07.4, AC-07.7). On the ladder only accepted rungs are used, and the target
flow's confidence on vague vs explicit rungs is compared per ladder (AC-07.5).
Writes results/scores/selective_<split>.json and results/figures/selective_<split>.png.
"""
import argparse
import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from dpdp_audit.paths import RESULTS  # noqa: E402
from dpdp_audit.selective import TARGET, accuracy, bootstrap_r95, curve, rung_confidence, summary  # noqa: E402

BASELINE = "B2"
# figure: the system, the frozen v1, the same-input baseline and the stronger model (fixed hue order)
PLOTTED = {"full_v2_finetuned": ("v2 (QLoRA tagger)", "#2a78d6"), "B2": ("B2", "#eb6834"),
           "B4": ("B4 Gemini", "#1baf7a"), "full": ("v1", "#eda100")}
LABEL_DY = {"full_v2_finetuned": 6, "B2": 6, "B4": 6, "full": -12}   # direct label above / below its line
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#898781", "#e4e3df", "#fcfcfb"


def plot(split: str, curves: dict, points: dict, path):
    fig, ax = plt.subplots(figsize=(6.4, 4.2), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)
    for s, (name, color) in PLOTTED.items():
        if s not in curves:
            continue
        # the last point (every flow reviewed, accuracy 1 by definition) is left out of the drawing
        share, acc = curves[s][0][:-1], curves[s][1][:-1]
        ax.plot(share * 100, acc, color=color, lw=2, label=name, solid_capstyle="round")
        i = int(0.08 * (len(share) - 1))
        ax.annotate(name, (share[i] * 100, acc[i]), xytext=(0, LABEL_DY[s]), textcoords="offset points",
                    fontsize=8, color=INK)
    for s, acc in points.items():
        ax.plot([0], [acc], marker="o", ms=7, color=MUTED, mec=SURFACE, mew=2, ls="none")
        ax.annotate(s, (0, acc), xytext=(6, -3), textcoords="offset points", fontsize=8, color=INK)
    ax.axhline(TARGET, color=MUTED, lw=1, ls=(0, (3, 3)))
    ax.annotate("95% target", (0, TARGET), xytext=(2, 3), textcoords="offset points", fontsize=8, color=MUTED)
    ax.set_xlim(-2, 102)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("flows reviewed by a person (%)", color=INK, fontsize=9)
    ax.set_ylabel("accuracy of the flows not reviewed", color=INK, fontsize=9)
    ax.set_title(f"Selective accuracy, {split} (tools as points at 0%)", color=INK, fontsize=10, loc="left")
    ax.grid(True, color=GRID, lw=0.8)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
    ax.tick_params(colors=MUTED, labelsize=8)
    ax.legend(frameon=False, fontsize=8, loc="lower right", labelcolor=INK)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="main")
    ap.add_argument("--bootstrap", type=int, default=1000)
    args = ap.parse_args()
    conf = json.loads((RESULTS / "confidence" / f"{args.split}.json").read_text())
    rows = {s: [r for r in v["flows"] if r.get("accepted", True)] for s, v in conf.items()}
    multi = [s for s, v in conf.items() if len(v["seeds"]) >= 3]
    single = [s for s in conf if s not in multi]
    points = {s: accuracy(rows[s]) for s in single}
    best_tool = max(points.values()) if points else None
    out = {"split": args.split, "target": TARGET, "best_tool_accuracy": best_tool,
           "points": points, "systems": {}}
    curves = {}
    for s in multi:
        res = summary(rows[s], match=best_tool)
        res["r95_ci"] = bootstrap_r95(rows[s], n=args.bootstrap)
        if s != BASELINE and BASELINE in multi:
            res[f"r95_minus_{BASELINE}"] = bootstrap_r95(rows[s], n=args.bootstrap, rows_b=rows[BASELINE])
        if args.split == "ladder":
            res["vague_vs_explicit"] = rung_confidence(rows[s], n=args.bootstrap)
        share, acc = curve(rows[s])
        res["curve"] = {"share": [round(x, 4) for x in share], "accuracy": [round(x, 4) for x in acc]}
        curves[s] = (share, acc)
        out["systems"][s] = res
    (RESULTS / "scores" / f"selective_{args.split}.json").write_text(json.dumps(out, indent=1))
    plot(args.split, curves, points, RESULTS / "figures" / f"selective_{args.split}.png")

    print(f"{args.split}: {len(rows[multi[0]]) if multi else 0} flows; tools at 0% review: "
          + ", ".join(f"{s} {a:.3f}" for s, a in points.items()))
    print(f"| system | accuracy | AUC | R@95 [95% CI] | review to match best tool | R@95 − {BASELINE} [95% CI] |")
    print("|---|---|---|---|---|---|")
    for s, r in out["systems"].items():
        ci, d = r["r95_ci"], r.get(f"r95_minus_{BASELINE}")
        dtxt = f"{d['point']:+.3f} [{d['lo']:+.3f}, {d['hi']:+.3f}]" if d else "—"
        print(f"| {s} | {r['accuracy']:.3f} | {r['auc']:.3f} | {ci['point']:.3f} [{ci['lo']:.3f}, {ci['hi']:.3f}] "
              f"| {r['review_to_match']:.3f} | {dtxt} |")
    if args.split == "ladder":
        print("\nconfidence of the target flow, vague − explicit rung (mean [95% CI]; lower/equal/higher):")
        for s, r in out["systems"].items():
            for f in ("agreement", "token_prob"):
                v = r["vague_vs_explicit"][f]
                if v:
                    print(f"  {s:18} {f:10} {v['mean_difference']:+.3f} [{v['lo']:+.3f}, {v['hi']:+.3f}]  "
                          f"{v['lower']}/{v['equal']}/{v['higher']} of {v['n']}")


if __name__ == "__main__":
    main()
