"""Download-free step: turn the Gazette PDFs in data/raw/dpdp/ into data/dpdp/sections.jsonl."""
import subprocess

from dpdp_audit.dpdp_text import build
from dpdp_audit.paths import DATA, RAW

SRC = RAW / "dpdp"


def to_text(pdf_name: str, txt_name: str):
    txt = SRC / txt_name
    if not txt.exists():
        subprocess.run(["pdftotext", str(SRC / pdf_name), str(txt)], check=True)
    return txt


if __name__ == "__main__":
    act = to_text("dpdp_act_2023.pdf", "act_raw.txt")
    rules = to_text("dpdp_rules_2025.pdf", "rules_raw.txt")
    records = build(act, rules, DATA / "dpdp" / "sections.jsonl")
    print(f"wrote {len(records)} units to data/dpdp/sections.jsonl")
