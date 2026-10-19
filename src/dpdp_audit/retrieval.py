"""Dense retrieval over DPDP Act / Rules units (bge-small + FAISS)."""
from __future__ import annotations

import json
import threading

import faiss
import numpy as np

from .paths import DATA, OUTPUTS

MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
INDEX_DIR = OUTPUTS / "cache" / "dpdp_index"


def load_units() -> list[dict]:
    with (DATA / "dpdp" / "sections.jsonl").open() as f:
        return [json.loads(line) for line in f]


def _passage(u: dict) -> str:
    head = f"{u['id']} {u['title']}".strip()
    return f"{head}: {u['text']}"


_LOCK = threading.Lock()
_MODEL = None


def _model():
    """Load the embedding model once; parallel first calls must not race (meta-tensor errors)."""
    global _MODEL
    with _LOCK:
        if _MODEL is None:
            from sentence_transformers import SentenceTransformer

            _MODEL = SentenceTransformer(MODEL_NAME, device="cpu")
    return _MODEL


def build_index() -> faiss.Index:
    units = load_units()
    vecs = _model().encode([_passage(u) for u in units], batch_size=16,
                           normalize_embeddings=True, show_progress_bar=False)
    index = faiss.IndexFlatIP(vecs.shape[1])
    index.add(np.asarray(vecs, dtype="float32"))
    INDEX_DIR.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(INDEX_DIR / "dpdp.faiss"))
    (INDEX_DIR / "ids.json").write_text(json.dumps([u["id"] for u in units]))
    return index


_INDEX = None


def _index():
    global _INDEX
    with _LOCK:
        if _INDEX is None:
            path = INDEX_DIR / "dpdp.faiss"
            _INDEX = faiss.read_index(str(path)) if path.exists() else None
    if _INDEX is None:
        _INDEX = build_index()
    return _INDEX


def search(query: str, k: int = 4) -> list[dict]:
    """Return the k most relevant DPDP units for a query, with scores."""
    units = load_units()
    q = _model().encode([QUERY_PREFIX + query], normalize_embeddings=True)
    scores, idx = _index().search(np.asarray(q, dtype="float32"), k)
    return [dict(units[i], score=float(s)) for s, i in zip(scores[0], idx[0]) if i >= 0]
