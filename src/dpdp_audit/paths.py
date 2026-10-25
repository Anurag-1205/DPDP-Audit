"""Project paths, resolved from the repository root.

data/      versioned inputs (benchmark, DPDP units, mappings); raw downloads in data/raw/ (ignored)
results/   versioned, curated results: system runs, scores, tool outputs, model checks
outputs/   local scratch only (ignored): LLM cache, FAISS index, logs, Kaggle staging
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
RESULTS = ROOT / "results"
OUTPUTS = ROOT / "outputs"
