"""Print the 95%-interval tables of the report from results/scores/ (WP-3.8, AC-09.5).

  python scripts/interval_tables.py > /tmp/intervals.md

Main benchmark: F1 in three views and the false-alarm rate of every system, seed 0, with the
policy-level cluster bootstrap interval stored by score_runs.py. Ladder: accuracy per accepted rung,
seed 0, with the bootstrap over ladders stored by score_ladder.py. Copy the output into the report
unchanged, so every interval comes from the score files.
"""
import json

from dpdp_audit.ladder import RUNG_ORDER
from dpdp_audit.paths import RESULTS

MAIN = [("S1 PoliCheck", "S1"), ("S2 PoliGraph", "S2"), ("B1", "B1"), ("B2", "B2"), ("B4 Gemini 3 Flash", "B4"),
        ("v1 `full_rv`", "full_rv"), ("v1 `full_finetuned_rv`", "full_finetuned_rv"),
        ("v2 `full_v2_rv`", "full_v2_rv"), ("v2 `full_v2_finetuned_rv`", "full_v2_finetuned_rv")]
LADDER = [("S1 PoliCheck", "S1"), ("S2 PoliGraph", "S2"), ("B2", "B2"), ("full", "full"),
          ("full_finetuned", "full_finetuned"), ("full_v2", "full_v2"), ("full_v2_finetuned", "full_v2_finetuned")]


def ci(c: dict) -> str:
    return f"{c['point']:.3f} [{c['lo']:.3f}, {c['hi']:.3f}]"


def main():
    m = json.loads((RESULTS / "scores" / "main.json").read_text())
    print("| System | F1 | F1 common | F1 common, native | False-alarm rate |")
    print("|---|---|---|---|---|")
    for label, s in MAIN:
        c = m[s]["ci_seed0"]
        print(f"| {label} | {ci(c['full'])} | {ci(c['common'])} | {ci(c['common_native'])} | {ci(c['false_alarm'])} |")
    print()
    lad = json.loads((RESULTS / "scores" / "ladder.json").read_text())
    print("| System | " + " | ".join(RUNG_ORDER) + " |")
    print("|---" * (len(RUNG_ORDER) + 1) + "|")
    for label, s in LADDER:
        r = lad[s]["seed0"]
        print(f"| {label} | " + " | ".join(
            f"{r['accuracy'][x]:.2f} [{r['accuracy_ci'][x][0]:.2f}, {r['accuracy_ci'][x][1]:.2f}]" for x in RUNG_ORDER) + " |")


if __name__ == "__main__":
    main()
