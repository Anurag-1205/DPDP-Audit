"""Split OPP-115 by policy: ~80 policies train the tagger, ~35 are held out.

The held-out policies supply both the tagger test set and every evaluation
case, so no evaluation policy is seen in training.
"""
from __future__ import annotations

import json
import random

from .opp115 import policy_files
from .paths import DATA

SEED = 13
N_HELDOUT = 35
SPLIT_FILE = DATA / "splits.json"


def make_split(seed: int = SEED, n_heldout: int = N_HELDOUT) -> dict:
    ids = sorted(p.stem for p in policy_files())
    rng = random.Random(seed)
    heldout = sorted(rng.sample(ids, n_heldout))
    train = sorted(set(ids) - set(heldout))
    split = {"seed": seed, "train": train, "heldout": heldout}
    SPLIT_FILE.write_text(json.dumps(split, indent=1))
    return split


def load_split() -> dict:
    return json.loads(SPLIT_FILE.read_text())
